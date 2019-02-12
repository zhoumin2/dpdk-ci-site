"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Render views for results database objects.
"""

import requests
import uuid

from collections import OrderedDict
from functools import partial
from logging import getLogger

from django.core.cache import cache
from rest_framework import viewsets
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType
from django_auth_ldap.backend import LDAPBackend
from django.http import Http404
from django_filters.rest_framework import DjangoFilterBackend
from guardian.shortcuts import get_perms
from guardian.utils import get_anonymous_user
from private_storage.views import PrivateStorageDetailView
from rest_framework.filters import OrderingFilter
from rest_framework.decorators import detail_route
from rest_framework.exceptions import NotFound
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.parsers import JSONParser, FormParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from .filters import EnvironmentFilter, PatchSetFilter, SubscriptionFilter, \
    DjangoObjectPermissionsFilterWithAnonPerms
from .models import Branch, Environment, Measurement, PatchSet, \
    Subscription, Tarball, TestCase, TestRun
from . import permissions
from .parsers import JSONMultiPartParser
from .serializers import BranchSerializer, EnvironmentSerializer, \
    GroupSerializer, MeasurementSerializer, \
    PatchSetSerializer, SubscriptionSerializer, TarballSerializer, \
    TestCaseSerializer, TestRunSerializer, UserSerializer
from shared.util import requests_to_response

logger = getLogger('results')


class DownloadPermissionView(PrivateStorageDetailView):
    """Check custom permissions for file access and verify file names.

    This class is meant to be extending by filling the `model` and
    `model_file_field` as described by Django Private Storage.
    """

    def can_access_file(self, private_file):
        """Check if the user can view the model.

        Also allows logged in users to access the file if AnonymousUser can
        access the file.
        """
        perm = 'view_' + self.object._meta.model_name
        return perm in get_perms(self.request.user, self.object) or \
            perm in get_perms(get_anonymous_user(), self.object)

    def get(self, request, *args, **kwargs):
        """Override `get` to pass extra args.

        Also raise PermissionDenied to show our custom template instead of
        returning a plain 403.
        """
        self.object = self.get_object(**kwargs)

        if not self.can_access_file(self.get_private_file()):
            raise PermissionDenied

        return super(PrivateStorageDetailView, self).get(request, *args, **kwargs)

    def get_object(self, uuidhex, **kwargs):
        """Override get_object to use the uuid."""
        try:
            return self.model.objects.get(uuid=uuid.UUID(uuidhex))
        except ValueError:
            raise Http404


class HardwareDescriptionDownloadView(DownloadPermissionView):
    """Allow access to the download if the user can access the environment."""

    model = Environment
    model_file_field = 'hardware_description'


class TestRunLogDownloadView(DownloadPermissionView):
    """Allow access to the download if the user can access the environment."""

    model = TestRun
    model_file_field = 'log_upload_file'

    def can_access_file(self, private_file):
        """Only the group is allowed to view the file.

        This is to avoid download of absolute values. Since anonymous user has
        permission for the object, make sure that the user is not anonymous.
        """
        perm = 'view_' + self.object._meta.model_name
        return perm in get_perms(self.request.user, self.object) and \
            not self.request.user.is_anonymous


class CacheListModelMixin:
    """List a queryset and cache the serializer if the cache parameter is set.

    Using a cached queryset is slower than just getting it from the database.
    Thus we only cache the serialized data.

    Based from:
    https://github.com/encode/django-rest-framework/blob/963ce306f3226ec64eb8990c4fbc094a77fabcba/rest_framework/mixins.py#L35
    """
    def list(self, request, *args, **kwargs):
        use_cache = request.query_params.get('cache', None)
        # The key is based on ordering the queryset, so that requests with
        # different ordering of the queryset hits the same cached page
        key = request.META['PATH_INFO'] +\
            ''.join([i[0] + i[1] for i in sorted(request.GET.items())])

        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(self._get_or_set(
                use_cache, key, partial(self._get_page_serializer_data, page)))

        return Response(self._get_or_set(
            use_cache, key, partial(self._get_serializer_data, queryset)))

    def _get_page_serializer_data(self, page):
        return self.get_serializer(page, many=True).data

    def _get_serializer_data(self, queryset):
        return self.get_serializer(queryset, many=True).data

    def _get_or_set(self, use_cache, key, get_value_method):
        if use_cache:
            value = cache.get(key)
            if value is None:
                value = get_value_method()
                # Arbitrarily cache pages for 10 minutes
                cache.set(key, value, 10 * 60)
            return value
        return get_value_method()


class PatchSetViewSet(CacheListModelMixin, viewsets.ModelViewSet):
    """Provide a read-write view of incoming patchsets.

    list:
    Lists all patchsets which match the specified query parameters, if any.
    If not query parameters are provided, list all patchsets.
    """

    permission_classes = (permissions.PatchSetPermission,)
    queryset = PatchSetSerializer.setup_eager_loading(PatchSet.objects.all())
    serializer_class = PatchSetSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filter_class = PatchSetFilter
    # All parsers are used in the dpdk ci scripts.
    # JSONMultiPartParser is used in apply_patchset.py
    # JSONParser is used in download_patchset.py
    # FormParser is used in update_all_patches_patchwork_status.py
    parser_classes = (JSONMultiPartParser, JSONParser, FormParser)
    ordering_fields = ('apply_error', 'id', 'is_public', 'tarballs',
                       'completed_timestamp', 'series_id', 'build_error')

    @detail_route(methods=['post'], url_name='rebuild',
                  url_path='rebuild/(?P<branch>.*)')
    def rebuild(self, request, pk, branch):
        """Rebuild a patchset."""
        ps = self.get_object()
        ps.apply_error = False
        ps.build_error = False
        ps.save()
        pipeline_url = f'{settings.JENKINS_URL}job/Apply-Custom-Patch-Set/' \
            'buildWithParameters/'
        message = f'{request.user} rebuilt {pipeline_url} for patchset {pk} ' \
                  f'with branch {branch}'
        logger.info(message)
        LogEntry.objects.log_action(
            request.user.id, ContentType.objects.get_for_model(PatchSet).pk, pk,
            repr(ps), CHANGE, message)
        auth = requests.auth.HTTPBasicAuth(settings.JENKINS_USER,
                                           settings.JENKINS_API_TOKEN)
        ps_url = request.build_absolute_uri(ps.get_absolute_url())
        params = dict(PATCHSET_META_URL=ps_url, BRANCH=branch)
        resp = requests.post(pipeline_url,
                             verify=settings.CA_CERT_BUNDLE,
                             auth=auth,
                             params=params)
        resp.raise_for_status()
        return Response({'status': 'pending'})


class BranchViewSet(viewsets.ModelViewSet):
    """Manage git branches used by DPDK."""

    permission_classes = (permissions.IsAdminUserOrReadOnly,)
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    filter_fields = ('name', 'last_commit_id')


class TarballViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of tarballs for testing."""

    permission_classes = (permissions.IsAdminUserOrReadOnly,)
    queryset = TarballSerializer.setup_eager_loading(Tarball.objects.all())
    serializer_class = TarballSerializer
    filter_fields = ('job_name', 'build_id', 'branch', 'commit_id', 'patchset')
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    ordering_fields = ('job_name', 'build_id', 'branch', 'commit_id', 'date')

    @detail_route(methods=['get'])
    def download(self, request, pk):
        """Download the artifact using the Jenkins user."""
        tarball = self.get_object()
        auth = requests.auth.HTTPBasicAuth(settings.JENKINS_USER,
                                           settings.JENKINS_API_TOKEN)
        r = requests.get(tarball.tarball_url,
                         verify=settings.CA_CERT_BUNDLE,
                         auth=auth)

        return requests_to_response(r)


class EnvironmentViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of environments."""

    filter_backends = (DjangoFilterBackend, OrderingFilter,
                       DjangoObjectPermissionsFilterWithAnonPerms,)
    permission_classes = (permissions.DjangoObjectPermissionsOrAnonReadOnly,)
    queryset = EnvironmentSerializer.setup_eager_loading(
        Environment.objects.all())
    serializer_class = EnvironmentSerializer
    filter_class = EnvironmentFilter

    @detail_route(methods=['post'])
    def clone(self, request, pk=None):
        """Create a clone of this object.

        The clone will be returned as part of the response.
        """
        env = self.get_object()
        clone = env.clone()
        serializer = EnvironmentSerializer(clone,
                                           context={'request': request})
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data,
                        status=status.HTTP_201_CREATED,
                        headers=headers)


class TestCaseViewSet(viewsets.ReadOnlyModelViewSet):
    """Display the available test cases."""

    queryset = TestCase.objects.all()
    serializer_class = TestCaseSerializer


class MeasurementViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide a read-only view of measurements."""

    filter_backends = (DjangoObjectPermissionsFilterWithAnonPerms,)
    permission_classes = (permissions.DjangoObjectPermissionsOrAnonReadOnly,)
    queryset = MeasurementSerializer.setup_eager_loading(
        Measurement.objects.all())
    serializer_class = MeasurementSerializer


class TestRunViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of test runs."""

    filter_backends = (DjangoObjectPermissionsFilterWithAnonPerms,)
    permission_classes = (permissions.TestRunPermission,)
    queryset = TestRunSerializer.setup_eager_loading(TestRun.objects.all())
    serializer_class = TestRunSerializer
    parser_classes = (JSONMultiPartParser,)

    @detail_route(methods=['post'])
    def rerun(self, request, pk):
        """Rerun a test run."""
        tr = self.get_object()
        pipeline_url = f'{tr.environment.pipeline_url}/buildWithParameters/'
        message = f'{request.user} reran {pipeline_url} for test run {pk}'
        logger.info(message)
        LogEntry.objects.log_action(
            request.user.id, ContentType.objects.get_for_model(TestRun).pk, pk,
            repr(tr), CHANGE, message)
        auth = requests.auth.HTTPBasicAuth(settings.JENKINS_USER,
                                           settings.JENKINS_API_TOKEN)
        tb_url = request.build_absolute_uri(tr.tarball.get_absolute_url())
        params = {'TARBALL_META_URL': tb_url}
        resp = requests.post(pipeline_url,
                             verify=settings.CA_CERT_BUNDLE,
                             auth=auth,
                             params=params)
        resp.raise_for_status()
        return Response({'status': 'pending'})


class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide a read-only view of groups."""

    permission_classes = (permissions.IsAdminUserOrReadOnly,)
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class UserViewSet(ListModelMixin, RetrieveModelMixin, viewsets.GenericViewSet):
    """Provide administrators API access to the registered users.

    list:
    Lists all users that have been populated in this instance.

    retrieve:
    Returns the user with the username given in the URL. Populates the user
    from LDAP if necessary.
    """

    lookup_field = 'username'
    permission_classes = (IsAdminUser,)
    queryset = UserSerializer.setup_eager_loading(
        User.objects.exclude(username__in=('AnonymousUser',)))
    serializer_class = UserSerializer

    def get_object(self):
        """Return the user object requested by the user.

        This method will populate the user object from LDAP if necessary.
        """
        user = LDAPBackend().populate_user(self.kwargs['username'])
        if user is None:
            raise NotFound(self.kwargs['username'])
        self.check_object_permissions(self.request, user)
        return user


class SubscriptionViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of subscriptions."""

    permission_classes = (permissions.UserProfileObjectPermission,)
    # this queryset is here to avoid the no "base_name" issue
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_class = SubscriptionFilter

    def get_queryset(self):
        """Only grab subscriptions of the user."""
        user = self.request.user
        if user.is_staff:
            return Subscription.objects.all()
        return user.results_profile.subscription_set.all()


class StatusViewSet(viewsets.ViewSet):

    def get_data(self, request):
        data = [dict({'name': x}, **y) for x, y
                in sorted(PatchSet.statuses.items())]
        for pk, elem in enumerate(data):
            elem['url'] = self.reverse_action('detail', args=[pk + 1])
        return data

    def list(self, request):
        data = self.get_data(request)
        return Response(OrderedDict([
            ('count', len(data)),
            ('next', None),
            ('previous', None),
            ('results', data)
        ]))

    def retrieve(self, request, pk=None):
        try:
            id = int(pk) - 1
            return Response(self.get_data(request)[id])
        except IndexError:
            raise Http404
