"""Render views for results database objects."""

from collections import OrderedDict
from rest_framework import viewsets
from django.contrib.auth.models import Group, User
from django_auth_ldap.backend import LDAPBackend
from django.http import Http404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, DjangoObjectPermissionsFilter
from rest_framework.decorators import detail_route
from rest_framework.exceptions import NotFound
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from .filters import EnvironmentFilter, PatchSetFilter, SubscriptionFilter
from .models import Branch, Environment, Measurement, PatchSet, Patch, \
    Subscription, Tarball, TestCase, TestRun
from . import permissions
from .serializers import BranchSerializer, EnvironmentSerializer, \
    GroupSerializer, MeasurementSerializer, PatchSerializer, \
    PatchSetSerializer, SubscriptionSerializer, TarballSerializer, \
    TestCaseSerializer, TestRunSerializer, UserSerializer


class PatchSetViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of incoming patchsets.

    list:
    Lists all patchsets which match the specified query parameters, if any.
    If not query parameters are provided, list all patchsets.
    """

    permission_classes = (permissions.IsAdminUserOrReadOnly,)
    queryset = PatchSetSerializer.setup_eager_loading(PatchSet.objects.all())
    serializer_class = PatchSetSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filter_class = PatchSetFilter
    ordering_fields = ('apply_error', 'cur_patch_count', 'id', 'is_public',
                       'message_uid', 'patch_count', 'patches', 'tarballs')


class BranchViewSet(viewsets.ModelViewSet):
    """Manage git branches used by DPDK."""

    permission_classes = (permissions.IsAdminUserOrReadOnly,)
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    filter_fields = ('name', 'last_commit_id')
    lookup_field = 'name'


class TarballViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of tarballs for testing."""

    permission_classes = (permissions.IsAdminUserOrReadOnly,)
    queryset = TarballSerializer.setup_eager_loading(Tarball.objects.all())
    serializer_class = TarballSerializer
    filter_fields = ('job_name', 'build_id', 'branch', 'commit_id', 'patchset')


class PatchViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of patches."""

    permission_classes = (permissions.IsAdminUserOrReadOnly,)
    queryset = PatchSerializer.setup_eager_loading(Patch.objects.all())
    serializer_class = PatchSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filter_fields = ('patchworks_id', 'is_rfc', 'submitter', 'pw_is_active')
    ordering_fields = ('contacts', 'date', 'id', 'is_rfc', 'message_id',
                       'patch_number', 'patchset', 'patchset_id',
                       'patchworks_id', 'pw_is_active', 'subject', 'submitter',
                       'version')


class EnvironmentViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of environments."""

    filter_backends = (DjangoFilterBackend, OrderingFilter, DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.OwnerReadCreateOnly,)
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

    filter_backends = (DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.OwnerReadCreateOnly,)
    queryset = MeasurementSerializer.setup_eager_loading(
        Measurement.objects.all())
    serializer_class = MeasurementSerializer


class TestRunViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of test runs."""

    filter_backends = (DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.OwnerReadCreateOnly,)
    queryset = TestRunSerializer.setup_eager_loading(TestRun.objects.all())
    serializer_class = TestRunSerializer


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
