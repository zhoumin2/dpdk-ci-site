"""Define serializers for results models."""

from rest_framework import serializers
from results.models import PatchSet, Patch

class PatchSetSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize PatchSet objects."""

    patches = serializers.HyperlinkedRelatedField(many=True, view_name='patch-detail', read_only=True)

    class Meta:
        model = PatchSet
        fields = ('url', 'patchworks_id', 'patch_count', 'patches')

class PatchSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize Patch objects."""

    class Meta:
        model = Patch
        fields = ('url', 'patchworks_id', 'submitter', 'subject',
                  'version', 'patch_number', 'date', 'patchset')
