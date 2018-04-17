"""Render views for results database objects."""

from rest_framework import viewsets
from django.contrib.auth.models import Group, User
from django_auth_ldap.backend import LDAPBackend
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, DjangoObjectPermissionsFilter
from rest_framework.decorators import detail_route
from rest_framework.exceptions import NotFound
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from .filters import PatchSetFilter
from .models import PatchSet, Patch, Environment, Measurement, \
    TestRun, Tarball
from . import permissions
from .serializers import PatchSetSerializer, PatchSerializer, \
    EnvironmentSerializer, MeasurementSerializer, TestRunSerializer, \
    TarballSerializer, GroupSerializer, UserSerializer


class PatchSetViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of incoming patchsets.

    list:
    Lists all patchsets which match the specified query parameters, if any.
    If not query parameters are provided, list all patchsets.
    """

    permission_classes = (permissions.IsAdminUserOrReadOnly,)
    queryset = PatchSet.objects.all()
    serializer_class = PatchSetSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filter_class = PatchSetFilter


class TarballViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of tarballs for testing."""

    permission_classes = (permissions.IsAdminUserOrReadOnly,)
    queryset = Tarball.objects.all()
    serializer_class = TarballSerializer
    filter_fields = ('job_id', 'branch', 'commit_id', 'patchset')


class PatchViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of patches."""

    permission_classes = (permissions.IsAdminUserOrReadOnly,)
    queryset = Patch.objects.all()
    serializer_class = PatchSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filter_fields = ('patchworks_id', 'is_rfc', 'submitter')


class EnvironmentViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of environments."""

    filter_backends = (DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.OwnerReadCreateOnly,)
    queryset = Environment.objects.all()
    serializer_class = EnvironmentSerializer

    @detail_route(methods=['post'])
    def clone(self, request, pk=None):
        """Create a clone of this object.

        The clone will be returned as part of the response.
        """
        env = self.get_object()
        clone = env.clone()
        serializer = EnvironmentSerializer(clone)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data,
                        status_code=status.HTTP_201_CREATED,
                        headers=headers)


class MeasurementViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of measurements."""

    filter_backends = (DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.OwnerReadCreateOnly,)
    queryset = Measurement.objects.all()
    serializer_class = MeasurementSerializer


class TestRunViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of test runs."""

    filter_backends = (DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.OwnerReadCreateOnly,)
    queryset = TestRun.objects.all()
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
    queryset = User.objects.exclude(username__in=('AnonymousUser',))
    serializer_class = UserSerializer

    def get_object(self):
        """Return the user object requested by the user.

        This method will populate the user object from LDAP if necessary.
        """
        queryset = self.get_queryset()
        user = LDAPBackend().populate_user(self.kwargs['username'])
        if user is None:
            raise NotFound(self.kwargs['username'])
        self.check_object_permissions(self.request, user)
        return user
