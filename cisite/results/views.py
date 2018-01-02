"""Render views for results database objects."""

from rest_framework import renderers, viewsets
from rest_framework.response import Response
from .models import PatchSet, Patch
from .serializers import PatchSetSerializer, PatchSerializer


class PatchSetViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of incoming patchsets."""

    queryset = PatchSet.objects.all()
    serializer_class = PatchSetSerializer


class PatchViewSet(viewsets.ModelViewSet):
    """Provide a read-write view of incoming patchsets."""

    queryset = Patch.objects.all()
    serializer_class = PatchSerializer
