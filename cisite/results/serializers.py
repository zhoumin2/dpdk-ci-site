"""Define serializers for results models."""

from rest_framework import serializers
from results.models import PatchSet, Patch, Environment, Measurement,\
    TestResult, TestRun


class PatchSetSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize PatchSet objects."""

    patches = serializers.HyperlinkedRelatedField(many=True, view_name='patch-detail', read_only=True)

    class Meta:
        """Specify fields to pull from PatchSet model."""

        model = PatchSet
        fields = ('url', 'patchworks_id', 'patch_count', 'patches')


class PatchSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize Patch objects."""

    class Meta:
        """Specify fields to pull from Patch model."""

        model = Patch
        fields = ('url', 'patchworks_id', 'submitter', 'subject',
                  'version', 'patch_number', 'date', 'patchset')


class EnvironmentSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize environment objects."""

    class Meta:
        """Specify how to serialize environment."""

        model = Environment
        fields = ('inventory_id', 'owner', 'motherboard_make',
                  'motherboard_model', 'motherboard_serial',
                  'cpu_socket_count', 'cpu_cores_per_socket',
                  'cpu_threads_per_core', 'ram_type', 'ram_size',
                  'ram_channel_count', 'ram_frequency', 'nic_make',
                  'nic_model', 'nic_device_id', 'nic_device_bustype',
                  'nic_pmd', 'nic_firmware_source_id',
                  'nic_firmware_version', 'kernel_cmdline',
                  'kernel_name', 'kernel_version', 'compiler_name',
                  'compiler_version', 'bios_version')


class MeasurementSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize measurement objects."""

    class Meta:
        """Specify how to serialize measurements."""

        model = Measurement
        fields = ('name', 'unit', 'higher_is_better', 'expected_value',
                  'delta_limit', 'environment')


class TestResultSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize test result objects."""

    class Meta:
        """Specify how to serialize test results."""

        model = TestResult
        fields = ('result', 'actual_value', 'measurement', 'run')


class TestRunSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize test run objects."""

    class Meta:
        """Specify how to serialize test runs."""

        model = TestRun
        fields = ('timestamp', 'log_output_file', 'is_official', 'patchset',
                  'results')
