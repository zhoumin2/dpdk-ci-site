"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Define serializers for results models.
"""
from logging import getLogger
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType
from guardian.shortcuts import get_objects_for_user, get_perms
from guardian.utils import get_anonymous_user
from rest_framework import serializers
from rest_framework.reverse import reverse

from .models import Branch, ContactPolicy, Environment, Measurement, \
    Parameter, PatchSet, Tarball, TestCase, TestResult, TestRun, \
    Subscription, UserProfile

logger = getLogger('results')


def qs_get_missing(queryset, data):
    """Return a queryset with entries missing from the user-supplied data.

    For every entry in the input queryset, include it in the output query if and only
    if the id is not present in the user-supplied data.
    """
    data_ids = [x['id'] for x in data if 'id' in x]
    qs_ids = [x['id'] for x in queryset.values('id')
              if x['id'] not in data_ids]
    return queryset.filter(pk__in=qs_ids)


class EagerLoadingMixin:
    """Set up eager loading.

    When using this mixin, the following attributes will be used:
    _SELECT_RELATED_FIELDS: Fields that the serializer uses that have a
        to-one relation.
    _PREFETCH_RELATED_FIELDS: Fields that the serializer uses that have a
        to-many relation.

    Taken from: https://ses4j.github.io/2015/11/23/optimizing-slow-django-rest-framework-performance/
    """

    @classmethod
    def setup_eager_loading(cls, queryset):
        """Set eager loading to prefetch requests.

        Call this method when getting the queryset.
        """
        if hasattr(cls, "_SELECT_RELATED_FIELDS"):
            queryset = queryset.select_related(*cls._SELECT_RELATED_FIELDS)
        if hasattr(cls, "_PREFETCH_RELATED_FIELDS"):
            queryset = queryset.prefetch_related(*cls._PREFETCH_RELATED_FIELDS)
        return queryset


class EnvironmentHyperlinkedField(serializers.HyperlinkedRelatedField):
    """Environment field to only show environments the user can access.

    This expects an HttpRequest context to get the appropriate user.
    """

    def __init__(self, **kwargs):
        """Set the default view_name since it should not change."""
        super().__init__(view_name='environment-detail', **kwargs)

    def get_queryset(self):
        """Only return environments the user can view."""
        return get_objects_for_user(self.context['request'].user,
            'view_environment',
            Environment.objects.all(),
            accept_global_perms=False)


class PatchSetSerializer(serializers.HyperlinkedModelSerializer,
                         EagerLoadingMixin):
    """Serialize PatchSet objects."""

    _SELECT_RELATED_FIELDS = ('branch',)
    _PREFETCH_RELATED_FIELDS = ('tarballs',)

    pw_series_url = serializers.SerializerMethodField()
    result_summary = serializers.SerializerMethodField()

    class Meta:
        """Specify fields to pull from PatchSet model."""

        model = PatchSet
        fields = ('url', 'id', 'is_public', 'apply_error', 'tarballs',
                  'time_to_last_test', 'series_id', 'pw_series_url',
                  'completed_timestamp', 'pw_is_active', 'build_log',
                  'result_summary', 'build_error', 'has_error',
                  'commit_id', 'commit_url', 'branch')
        read_only_fields = ('complete', 'tarballs',
                            'status', 'status_class', 'status_tooltip',
                            'time_to_last_test')

    def get_pw_series_url(self, obj):
        if obj.series_id is None:
            return None
        return urljoin(settings.PATCHWORKS_URL, f'series/{obj.series_id}')

    def get_result_summary(self, obj):
        request = self.context.get('request')
        rev = reverse('patchset-result-summary', args=[obj.id])
        return request.build_absolute_uri(rev)


class ParameterSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize parameter objects."""

    id = serializers.IntegerField(required=False)

    class Meta:
        """Specify how to serialize parameters."""

        model = Parameter
        fields = ('name', 'id', 'value', 'unit')
        filter_fields = ('name', 'unit')


class TestCaseSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize test case objects."""

    class Meta:
        """Define how to serialize test cases."""

        model = TestCase
        fields = ('url', 'id', 'name', 'description_url', 'pipeline')


class MeasurementSerializer(serializers.HyperlinkedModelSerializer,
                            EagerLoadingMixin):
    """Serialize measurement objects."""

    _PREFETCH_RELATED_FIELDS = ('parameters',)

    id = serializers.IntegerField(required=False)
    parameters = ParameterSerializer(many=True, required=False)

    class Meta:
        """Specify how to serialize measurements."""

        model = Measurement
        fields = ('url', 'id', 'name', 'unit', 'higher_is_better',
                  'environment', 'parameters', 'testcase')
        read_only_fields = ('environment', )
        filter_fields = ('name', 'unit', 'environment')


class ContactPolicySerializer(serializers.HyperlinkedModelSerializer):
    """Serialize contact policy objects."""

    class Meta:
        """Define how to setup ContactPolicySerializer."""

        model = ContactPolicy
        fields = ('email_submitter', 'email_recipients', 'email_owner',
                  'email_success', 'email_list')


class SubscriptionSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a user subscription entry.

    This serializer is designed to be used from within SubscriptionSerializer.
    """

    display_name = serializers.CharField(source='user_profile.display_name',
                                         read_only=True)
    email = serializers.EmailField(source='user_profile.user.email',
                                   read_only=True)
    environment = EnvironmentHyperlinkedField()

    class Meta:
        """Define serializer model and fields."""

        model = Subscription
        fields = ('id', 'url', 'environment', 'email_success', 'how',
                  'display_name', 'email')

    def create(self, validated_data):
        """Set the user profile to the user creating the subscription."""
        user_id = self.context['request'].user.results_profile.id
        return Subscription.objects.create(user_profile_id=user_id, **validated_data)


class EnvironmentSerializer(serializers.HyperlinkedModelSerializer,
                            EagerLoadingMixin):
    """Serialize environment objects."""

    _SELECT_RELATED_FIELDS = ('contact_policy',)
    _PREFETCH_RELATED_FIELDS = ('measurements', 'measurements__parameters',
                                'contacts')

    READONLY_FMT = "cannot {verb} {object} if environment has test runs"

    measurements = MeasurementSerializer(many=True)
    contact_policy = ContactPolicySerializer()
    contacts = SubscriptionSerializer(many=True, read_only=True)
    public = serializers.SerializerMethodField()

    class Meta:
        """Specify how to serialize environment."""

        model = Environment
        fields = ('url', 'id', 'inventory_id', 'owner', 'motherboard_make',
                  'motherboard_model', 'motherboard_serial',
                  'cpu_socket_count', 'cpu_cores_per_socket',
                  'cpu_threads_per_core', 'ram_type', 'ram_size',
                  'ram_channel_count', 'ram_frequency', 'nic_make',
                  'nic_model', 'nic_speed', 'nic_dtscodename', 'nic_device_id',
                  'nic_device_bustype', 'nic_pmd', 'nic_firmware_source_id',
                  'nic_firmware_version', 'kernel_cmdline',
                  'kernel_name', 'kernel_version', 'compiler_name',
                  'compiler_version', 'bios_version', 'os_distro',
                  'measurements', 'contacts', 'contact_policy',
                  'predecessor', 'successor', 'date', 'live_since',
                  'hardware_description', 'pipeline', 'name', 'public')
        read_only_fields = ('contacts', 'predecessor', 'successor',
                            'date')

    def validate(self, data):
        """Validate environment modification for inactive objects.

        Only allow modification of contact policy for active environments.
        """
        if not self.instance:
            return data

        if hasattr(self.instance, 'successor'):
            raise serializers.ValidationError(
                "environments are immutable once cloned; edit the clone")

        if not self.instance.runs.all().exists():
            return data

        for k, v in data.items():
            if k in ['url', 'contact_policy', 'measurements',
                     'hardware_description', 'live_since', 'nic_make',
                     'nic_model']:
                continue
            if v != getattr(self.instance, k):
                raise serializers.ValidationError(self.READONLY_FMT.format(
                    verb="change", object=k))

        # handle PATCH vs PUT requests
        if self.partial and 'measurements' not in data:
            return data

        for m_data in data['measurements']:
            if self.instance and 'id' not in m_data:
                raise serializers.ValidationError('no id')
            try:
                real_data = m_data.copy()
                real_data.pop('url', None)
                params_data = real_data.pop('parameters')
                m = self.instance.measurements.get(**real_data)
                for p_data in params_data:
                    try:
                        m.parameters.get(**p_data)
                    except Parameter.DoesNotExist:
                        raise serializers.ValidationError(
                            self.READONLY_FMT.format(
                                verb="change",
                                object="measurement parameters"))
                if qs_get_missing(m.parameters.all(), params_data).exists():
                    raise serializers.ValidationError(self.READONLY_FMT.format(
                        verb="remove", object="measurement parameters"))
            except Measurement.DoesNotExist:
                raise serializers.ValidationError(self.READONLY_FMT.format(
                    verb="change", object="measurements"))
        if qs_get_missing(self.instance.measurements.all(),
                          data['measurements']).exists():
            raise serializers.ValidationError(self.READONLY_FMT.format(
                verb="remove", object="measurements"))
        return data

    def update(self, instance, validated_data):
        """Update an environment based on the validated POST data.

        Any measurements or parameters with an ``id`` field specified are
        assumed to be already associated with ``instance``. Any such entries
        without an ``id`` field will be newly created, even if an exact
        duplicate already exists in the database.
        """
        validated_data.pop('url', None)
        # only log for http requests (not unit tests, etc)
        request = self.context.get('request')
        if request:
            user = request.user
            message = f'{user} changed environment {instance.pk} with: '

        # handle PATCH vs PUT requests
        if (self.partial and
                'contact_policy' not in validated_data and
                'measurements' not in validated_data):
            for field, v in validated_data.items():
                if request and getattr(instance, field, None) != v:
                    message += (f'[{field} from {getattr(instance, field, None)} '
                                f'to {v}] ')
                setattr(instance, field, v)

            if request:
                logger.info(message)
                LogEntry.objects.log_action(
                    user.id, ContentType.objects.get_for_model(Environment).pk,
                    instance.pk, repr(instance), CHANGE, message)

            instance.save()
            return instance

        cpolicy_data = validated_data.pop('contact_policy')
        measurements_data = validated_data.pop('measurements')

        for field, v in validated_data.items():
            if request and getattr(instance, field, None) != v:
                message += (f'[{field} from {getattr(instance, field, None)} '
                            f'to {v}] ')
            setattr(instance, field, v)

        if request:
            logger.info(message)
            LogEntry.objects.log_action(
                user.id, ContentType.objects.get_for_model(Environment).pk,
                instance.pk, repr(instance), CHANGE, message)

        instance.save()

        for field, v in cpolicy_data.items():
            setattr(instance.contact_policy, field, v)

        instance.contact_policy.save()

        for m_data in measurements_data:
            m_data.pop('url', None)
            m_data.pop('environment', None)
            params_data = m_data.pop('parameters')

            if 'id' not in m_data:
                m = Measurement.objects.create(environment=instance, **m_data)
                m_data['id'] = m.pk
            else:
                m = instance.measurements.get(pk=m_data['id'])
                for field, v in m_data.items():
                    setattr(m, field, v)
                m.save()

            for p_data in params_data:
                if 'id' not in p_data:
                    p = Parameter.objects.create(measurement=m, **p_data)
                    p_data['id'] = p.pk
                else:
                    p = m.parameters.get(pk=p_data['id'])
                    for field, v in p_data.items():
                        setattr(p, field, v)
                    p.save()

            qs_get_missing(m.parameters.all(), params_data).delete()

        qs_get_missing(instance.measurements.all(),
                       measurements_data).delete()
        return instance

    def create(self, validated_data):
        """Create an environment based on the POST data.

        Measurements specified in the measurements list will also be
        created along with the environment.
        """
        measurements_data = validated_data.pop('measurements')
        cpolicy_data = validated_data.pop('contact_policy')
        environment = Environment.objects.create(**validated_data)
        ContactPolicy.objects.create(environment=environment, **cpolicy_data)
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

    def get_public(self, obj):
        return 'view_environment' in get_perms(get_anonymous_user(), obj)


class TestResultSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize test result objects."""

    id = serializers.IntegerField(required=False)

    class Meta:
        """Specify how to serialize test results."""

        model = TestResult
        fields = ('id', 'result', 'difference', 'expected_value',
                  'measurement', 'result_class')
        read_only_fields = ('result_class',)


class TestResultSerializerGet(TestResultSerializer):
    """Serialize test result objects."""

    measurement = MeasurementSerializer()
    expected_value = serializers.SerializerMethodField()

    def get_expected_value(self, obj):
        """
        Only privileged users can see what the expected value is.
        """
        request = self.context.get('request')
        # Since view_* is used for anonymous access, just use delete_*
        if request and 'delete_testresult' in get_perms(request.user, obj):
            return obj.expected_value
        return None


class TestRunSerializer(serializers.HyperlinkedModelSerializer,
                        EagerLoadingMixin):
    """Serialize test run objects."""

    _SELECT_RELATED_FIELDS = ('environment', 'tarball')
    _PREFETCH_RELATED_FIELDS = ('results',)

    results = TestResultSerializer(many=True, allow_empty=True)
    environment = EnvironmentHyperlinkedField()
    public_download = serializers.SerializerMethodField()

    class Meta:
        """Specify how to serialize test runs."""

        model = TestRun
        fields = ('id', 'url', 'timestamp', 'log_output_file',
                  'tarball', 'results', 'environment',
                  'report_timestamp', 'log_upload_file', 'branch',
                  'commit_id', 'commit_url', 'testcase', 'public_download')

    def update(self, instance, validated_data):
        """Update a test run based on the validated POST data.

        Any test results with an ``id`` field specified are assumed to be
        already associated with ``instance``. Any entries without an ``id``
        field will be newly created, even if an exact duplicate already
        exists in the database.
        """
        validated_data.pop('url', None)
        results_data = validated_data.pop('results', [])

        for field, v in validated_data.items():
            setattr(instance, field, v)

        instance.save()

        for r_data in results_data:
            r_data.pop('url', None)
            r_data.pop('run', None)
            if 'id' not in r_data:
                r = TestResult.objects.create(run=instance, **r_data)
                r_data['id'] = r.pk
            else:
                r = instance.results.get(pk=r_data['id'])
                for field, v in r_data.items():
                    setattr(r, field, v)
                r.save()

        if results_data:
            qs_get_missing(instance.results.all(),
                           results_data).delete()
        return instance

    def create(self, validated_data):
        """Create a new test run and nested test results."""
        results = validated_data.pop('results')
        run = TestRun.objects.create(**validated_data)
        for result in results:
            TestResult.objects.create(run=run, **result)
        return run

    def get_public_download(self, obj):
        return 'download_artifacts' in get_perms(get_anonymous_user(), obj)


class TestRunSerializerGet(TestRunSerializer):
    """Serialize test run objects."""

    results = TestResultSerializerGet(many=True, allow_empty=True)


class BranchSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize branch objects for use in the REST API."""

    class Meta:
        """Specify fields to pull in for BranchSerializer."""

        model = Branch
        fields = ('url', 'id', 'name', 'repository_url', 'regexp',
                  'last_commit_id', 'web_url')


class TarballSerializer(serializers.HyperlinkedModelSerializer,
                        EagerLoadingMixin):
    """Serialize Tarball objects."""

    _SELECT_RELATED_FIELDS = ('patchset', 'branch')
    _PREFETCH_RELATED_FIELDS = ('runs',)

    runs = serializers.HyperlinkedRelatedField(many=True, read_only=True,
                                               view_name='testrun-detail')
    result_summary = serializers.SerializerMethodField()

    class Meta:
        """Specify fields to pull from Tarball model."""

        model = Tarball
        fields = ('id', 'url', 'patchset', 'branch', 'commit_id', 'job_name',
                  'build_id', 'tarball_url', 'runs', 'date', 'commit_url',
                  'result_summary',)
        read_only_fields = ('date', 'commit_url')

    def get_result_summary(self, obj):
        request = self.context.get('request')
        rev = reverse('tarball-result-summary', args=[obj.id])
        return request.build_absolute_uri(rev)


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize group objects."""

    class Meta:
        """Specify metadata for group serializer."""

        model = Group
        fields = ('url', 'name')


class UserProfileSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize user profile objects."""

    class Meta:
        """Specify metadata for user profile serializer."""

        model = UserProfile
        fields = ('display_name',)


class UserSerializer(serializers.HyperlinkedModelSerializer,
                     EagerLoadingMixin):
    """Serialize user objects."""

    _PREFETCH_RELATED_FIELDS = ('groups',)

    results_profile = UserProfileSerializer()

    class Meta:
        """Specify metadata for group serializer."""

        model = User
        fields = ('url', 'username', 'groups', 'first_name', 'last_name',
                  'email', 'results_profile')
        read_only_fields = fields
        extra_kwargs = {
            'url': {'lookup_field': 'username'},
        }
