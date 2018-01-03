"""Render views for results database objects."""

from rest_framework import permissions, viewsets
from .models import PatchSet, Patch
from .serializers import PatchSetSerializer, PatchSerializer


class PatchSetViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of incoming patchsets."""

    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    queryset = PatchSet.objects.all()
    serializer_class = PatchSetSerializer


class PatchViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of incoming patchsets."""

    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    queryset = Patch.objects.all()
    serializer_class = PatchSerializer
