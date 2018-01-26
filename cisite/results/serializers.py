"""Define serializers for results models."""

import re
from django.contrib.auth.models import Group
from rest_framework import serializers
from .models import PatchSet, Tarball, Patch, Environment, Measurement, \
    TestResult, TestRun, Parameter


class TarballSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize Tarball objects."""

    class Meta:
        """Specify fields to pull from Tarball model."""

        model = Tarball
        fields = ('url', 'patchset', 'branch', 'commit_id',
                  'job_id', 'tarball_url')


class PatchSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize Patch objects."""

    patchset_count = serializers.IntegerField(default=1,
        help_text='Number of patches in the patchset')

    _messageIdPatterns = [
        re.compile(r'(?P<uid>.*-.*)-\d+-git-send-email-(.*)'),
        re.compile(r'.*\.(?P<uid>.*)\.git.(.*)'),
        re.compile(r'(?P<uid>.*\..*)-\d+-(.*)'),
    ]

    class Meta:
        """Specify fields to pull from Patch model."""

        model = Patch
        fields = ('url', 'patchworks_id', 'message_id', 'submitter', 'subject',
                  'version', 'is_rfc', 'patch_number', 'date', 'patchset',
                  'patchset_count')
        read_only_fields = ('patchset',)

    def create(self, validated_data):
        message_uid = ''
        for pattern in self.__class__._messageIdPatterns:
            m = pattern.match(validated_data['message_id'])
            if m:
                message_uid = m.group('uid')
        patchset, created = PatchSet.objects.get_or_create(message_uid=message_uid,
            defaults=dict(patch_count=validated_data.pop('patchset_count')))
        patch = Patch.objects.create(patchset=patchset, **validated_data)
        return patch


class PatchSetSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize PatchSet objects."""

    patches = PatchSerializer(many=True, read_only=True)

    class Meta:
        """Specify fields to pull from PatchSet model."""

        model = PatchSet
        fields = ('url', 'patch_count', 'patches', 'complete')
        read_only_fields = ('complete',)


class ParameterSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize parameter objects."""

    class Meta:
        """Specify how to serialize parameters."""

        model = Parameter
        fields = ('name', 'value', 'unit')
        filter_fields = ('name', 'unit')


class MeasurementSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize measurement objects."""

    parameters = ParameterSerializer(many=True, required=False)

    class Meta:
        """Specify how to serialize measurements."""

        model = Measurement
        fields = ('url', 'name', 'unit', 'higher_is_better', 'expected_value',
                  'delta_limit', 'environment', 'parameters')
        read_only_fields = ('environment', )
        filter_fields = ('name', 'unit', 'environment')


class EnvironmentSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize environment objects."""

    measurements = MeasurementSerializer(many=True)

    class Meta:
        """Specify how to serialize environment."""

        model = Environment
        fields = ('url', 'inventory_id', 'owner', 'motherboard_make',
                  'motherboard_model', 'motherboard_serial',
                  'cpu_socket_count', 'cpu_cores_per_socket',
                  'cpu_threads_per_core', 'ram_type', 'ram_size',
                  'ram_channel_count', 'ram_frequency', 'nic_make',
                  'nic_model', 'nic_device_id', 'nic_device_bustype',
                  'nic_pmd', 'nic_firmware_source_id',
                  'nic_firmware_version', 'kernel_cmdline',
                  'kernel_name', 'kernel_version', 'compiler_name',
                  'compiler_version', 'bios_version', 'measurements')

    def create(self, validated_data):
        """Create an environment based on the POST data.

        Measurements specified in the measurements list will also be
        created along with the environment.
        """
        measurements_data = validated_data.pop('measurements')
        environment = Environment.objects.create(**validated_data)
        for measurement_data in measurements_data:
            parameters_data = list()
            if 'parameters' in measurement_data:
                parameters_data = measurement_data.pop('parameters')
            measurement = Measurement.objects.create(environment=environment,
                                                     **measurement_data)
            for parameter_data in parameters_data:
                Parameter.objects.create(measurement=measurement,
                                         **parameter_data)
        return environment


class TestResultSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize test result objects."""

    class Meta:
        """Specify how to serialize test results."""

        model = TestResult
        fields = ('url', 'result', 'actual_value', 'measurement')


class TestRunSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize test run objects."""

    results = TestResultSerializer(many=True)

    class Meta:
        """Specify how to serialize test runs."""

        model = TestRun
        fields = ('url', 'timestamp', 'log_output_file', 'is_official',
                  'tarball', 'results')

    def create(self, validated_data):
        results = validated_data.pop('results')
        run = TestRun.objects.create(**validated_data)
        for result in results:
            TestResult.objects.create(run=run, **result)
        return run


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize group objects."""

    class Meta:
        """Specify metadata for group serializer."""

        model = Group
        fields = ('url', 'name')
