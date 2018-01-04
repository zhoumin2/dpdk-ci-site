"""Render views for results database objects."""

from rest_framework import viewsets
from .models import PatchSet, Patch, Environment, Measurement, TestResult,\
    TestRun
from . import permissions
from .serializers import PatchSetSerializer, PatchSerializer,\
    EnvironmentSerializer, MeasurementSerializer, TestResultSerializer,\
    TestRunSerializer


class PatchSetViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of incoming patchsets."""

    permission_classes = (permissions.IsAdminUserOrReadOnly,)
    queryset = PatchSet.objects.all()
    serializer_class = PatchSetSerializer


class PatchViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of patches."""

    permission_classes = (permissions.IsAdminUserOrReadOnly,)
    queryset = Patch.objects.all()
    serializer_class = PatchSerializer


class EnvironmentViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of environments."""

    permission_classes = (permissions.OwnerReadOnly,)
    queryset = Environment.objects.all()
    serializer_class = EnvironmentSerializer


class MeasurementViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of measurements."""

    permission_classes = (permissions.OwnerReadOnly,)
    queryset = Measurement.objects.all()
    serializer_class = MeasurementSerializer


class TestResultViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of test results."""

    permission_classes = (permissions.OwnerReadOnly,)
    queryset = TestResult.objects.all()
    serializer_class = TestResultSerializer


class TestRunViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of test runs."""

    permission_classes = (permissions.OwnerReadOnly,)
    queryset = TestRun.objects.all()
    serializer_class = TestRunSerializer
