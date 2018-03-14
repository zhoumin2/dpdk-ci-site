"""Render views for results database objects."""

from rest_framework import viewsets
from django.contrib.auth.models import Group
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, DjangoObjectPermissionsFilter
from rest_framework.decorators import list_route
from rest_framework.response import Response
from .filters import PatchSetFilter
from .models import PatchSet, Patch, Environment, Measurement, TestResult,\
    TestRun, Tarball
from . import permissions
from .serializers import PatchSetSerializer, PatchSerializer,\
    EnvironmentSerializer, MeasurementSerializer, TestResultSerializer,\
    TestRunSerializer, TarballSerializer, GroupSerializer


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


class MeasurementViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of measurements."""

    filter_backends = (DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.OwnerReadCreateOnly,)
    queryset = Measurement.objects.all()
    serializer_class = MeasurementSerializer


class TestResultViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of test results."""

    filter_backends = (DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.OwnerReadCreateOnly,)
    queryset = TestResult.objects.all()
    serializer_class = TestResultSerializer


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
