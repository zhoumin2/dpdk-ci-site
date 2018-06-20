"""Define test cases for results app."""

from copy import deepcopy
from datetime import datetime
import pytz
from django.contrib.auth.models import User, Group, Permission
from django.core.exceptions import ValidationError
from django.http.request import HttpRequest
from django.test import TestCase
from django.test.client import RequestFactory
from django.utils.dateparse import parse_datetime
import rest_framework.exceptions
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from .models import Patch, PatchSet, ContactPolicy, Environment, \
    Measurement, TestRun, TestResult, Tarball, Parameter, \
    Subscription, UserProfile
from .serializers import PatchSerializer, EnvironmentSerializer, \
    SubscriptionSerializer, TestRunSerializer, EnvironmentHyperlinkedField


def create_test_run(environment):
    """Create a dummy test run object for use by tests."""
    tb = Tarball.objects.create(
        branch="master", tarball_url='http://host.invalid/dpdk.tar.gz',
        commit_id="0000000000000000000000000000000000000000")
    return TestRun.objects.create(timestamp=datetime.now(tz=pytz.utc),
                                  log_output_file='/foo/bar',
                                  tarball=tb, environment=environment)


def create_test_environment(**kwargs):
    """Create an environment with given customizations."""
    env_args = dict(inventory_id='IOL-IOL-1',
                    motherboard_make="Intel", motherboard_model="ABCDEF",
                    motherboard_serial="12345", cpu_socket_count=1,
                    cpu_cores_per_socket=1, cpu_threads_per_core=1,
                    ram_type="DDR4", ram_size=65536, ram_channel_count=2,
                    ram_frequency=2400, nic_make="Intel",
                    nic_model="XL710", nic_device_id="01:00.0",
                    nic_device_bustype="PCI", nic_pmd="i40e",
                    nic_firmware_version="5.05", kernel_version="4.14",
                    compiler_name="gcc", compiler_version="7.1",
                    os_distro="Fedora26", bios_version="5.05")
    env_args.update(kwargs)
    return Environment.objects.create(**env_args)


def reverse_url(view, pk):
    """Create a url, like `http://testserver/environments/1/`."""
    request = RequestFactory().get('/')
    return reverse(view, args=(pk,), request=request)


class SerializerAssertionMixin(object):
    """Provide extra unittest assertions for serializer test cases."""

    def _assertSerializedNestedEqual(self, x_data, y_data, **kwargs):
        """Implement assertSerializedNestedEqual.

        Do not call this method directly; use ``_assertSerializedNestedEqual``
        instead.
        """
        excludes = kwargs.get('excludes', [])
        nested_lists = kwargs.get('nested_lists', [])
        if 'url' not in x_data:
            y_data.pop('url', None)
        if 'id' not in x_data:
            y_data.pop('id', None)
        for field in excludes:
            x_data.pop(field, None)
            y_data.pop(field, None)
        x_sub = dict()
        y_sub = dict()
        for field in nested_lists:
            x_sub[field] = x_data.pop(field)
            y_sub[field] = y_data.pop(field)
        self.assertDictEqual(x_data, y_data)
        for field in nested_lists:
            self.assertEqual(len(x_sub[field]), len(y_sub[field]))
            new_kwargs = {x.partition('_')[2]: y for x, y in kwargs.items()
                          if x.startswith(field + '_')}
            for x_field, y_field in zip(x_sub[field], y_sub[field]):
                self._assertSerializedNestedEqual(x_field, y_field,
                                                  **new_kwargs)

    def assertSerializedNestedEqual(self, x_data, y_data, **kwargs):
        """Assert that two serialized representations are equal.

        The order is significant; the second serialized object is assumed to
        have fields which may be missing in the first.

        Takes a few extra keyword arguments. Pass a list of fields to
        ``excludes`` in order to ignore them if they are not present in the
        first list. The ``nested_lists`` parameter takes a list of fields which
        are a nested list of dictionaries representing separate objects. For
        each field *x* in ``nested_lists`` you can pass an argument with
        *x*``_nested_lists`` or *x*``_excludes`` to indicate parameters for
        these nested objects.
        """
        self._assertSerializedNestedEqual(deepcopy(x_data), deepcopy(y_data),
                                          **kwargs)


class PatchSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        cls.test_ps = PatchSet.objects.create(patch_count=3,
            message_uid='20171023231534.90996')

    def test_create_patchset_does_not_exist(self):
        serializer = PatchSerializer(data=dict(patchworks_id=30744,
              pw_is_active=True,
              submitter='Ferruh Yigit <ferruh.yigit@intel.com>',
              message_id='20171024231534.90997-1-ferruh.yigit@intel.com',
              subject='ethdev: extract xstat basic stat count calculation',
              patchset_count=3,
              version='v2',
              patch_number=1,
              date=datetime(2017, 10, 23, 23, 15, 32, tzinfo=pytz.utc)))
        serializer.is_valid(raise_exception=True)
        p = serializer.save()
        self.assertNotEqual(p.patchset, self.__class__.test_ps)

    def test_create_patchset_exists(self):
        serializer = PatchSerializer(data=dict(patchworks_id=30741,
              pw_is_active=True,
              submitter='Ferruh Yigit <ferruh.yigit@intel.com>',
              message_id='20171023231534.90996-1-ferruh.yigit@intel.com',
              subject='ethdev: extract xstat basic stat count calculation',
              patchset_count=3,
              version='v2',
              patch_number=1,
              date=datetime(2017, 10, 23, 23, 15, 32, tzinfo=pytz.utc)))
        serializer.is_valid(raise_exception=True)
        p = serializer.save()
        self.assertEqual(p.patchset, self.__class__.test_ps)


class EnvironmentSerializerTestCase(TestCase, SerializerAssertionMixin):
    """Verify EnvironmentSerializer nested create/update works."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data for EnvironmentSerializer tests."""
        group = Group.objects.create(name="TestGroup")
        cls.group_url = reverse(
            "group-detail", args=[group.id], request=None)
        cls.initial_data = dict(
            owner=cls.group_url,
            inventory_id='test1',
            motherboard_make="Vendor",
            motherboard_model="Model T",
            motherboard_serial="ABCDEFG12345",
            cpu_socket_count=2,
            cpu_cores_per_socket=8,
            cpu_threads_per_core=1,
            ram_type="DDR4",
            ram_size=65536,
            ram_channel_count=4,
            ram_frequency=2166,
            nic_make="Vendor",
            nic_model="Model S",
            nic_speed=10000,
            nic_device_id="07:00.0",
            nic_device_bustype="PCI",
            nic_pmd="models",
            nic_firmware_source_id="",
            nic_firmware_version="1.0",
            os_distro="Fedora26",
            kernel_cmdline="ro quiet",
            kernel_name="linux",
            kernel_version="4.11.8-300.fc26.x86_64",
            compiler_name="gcc",
            compiler_version="7.2.1-2",
            bios_version="4.2",
            measurements=[dict(name="throughput_large_queue",
                               unit="Mpps",
                               higher_is_better=True,
                               parameters=[dict(name="Frame size",
                                                unit="bytes",
                                                value=64),
                                           dict(name="txd/rxd",
                                                unit="descriptors",
                                                value=2048)])],
            contact_policy=dict(email_submitter=False,
                                email_recipients=False,
                                email_owner=False,
                                email_success=True,
                                email_list='xyz@example.com'))
        # We cannot instantiate the environment here as some of our test
        # methods modify it

    def test_update_cloned(self):
        """Verify updating a field in an cloned environment fails."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        env.clone()
        env_data = EnvironmentSerializer(env, context={'request': None}).data
        env_data['nic_firmware_version'] = '2.0'
        serializer = EnvironmentSerializer(env, data=env_data)
        with self.assertRaises(rest_framework.exceptions.ValidationError):
            serializer.is_valid(raise_exception=True)
            serializer.save()

    def test_update_contactpolicy_cloned(self):
        """Verify contact policy cannot be changed for cloned environment."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        env.clone()
        env_data = EnvironmentSerializer(env, context={'request': None}).data
        env_data['contact_policy']['email_list'] = 'abc@example.com'
        serializer = EnvironmentSerializer(env, data=env_data)
        with self.assertRaises(rest_framework.exceptions.ValidationError):
            serializer.is_valid(raise_exception=True)
            serializer.save()

    def test_update_active(self):
        """Verify modifying a measurement in an active environment fails."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        create_test_run(env)
        env_data = EnvironmentSerializer(env, context={'request': None}).data
        env_data['nic_firmware_version'] = '2.0'
        serializer = EnvironmentSerializer(env, data=env_data)
        with self.assertRaises(rest_framework.exceptions.ValidationError):
            serializer.is_valid(raise_exception=True)
            serializer.save()

    def test_update_contactpolicy_active(self):
        """Verify contact policy can be changed for active environment."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        create_test_run(env)
        env_data = EnvironmentSerializer(env, context={'request': None}).data
        env_data['contact_policy']['email_list'] = 'abc@example.com'
        serializer = EnvironmentSerializer(env, data=env_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        env_data2 = EnvironmentSerializer(env, context={'request': None}).data
        self.assertSerializedNestedEqual(
            env_data, env_data2, nested_lists=['measurements'],
            excludes=['contacts', 'predecessor', 'successor'],
            measurements_excludes=['environment'],
            measurements_nested_lists=['parameters'])

    def test_rm_measurement_active(self):
        """Verify deleting a measurement from an active environment fails."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        create_test_run(env)
        env_data = EnvironmentSerializer(env, context={'request': None}).data
        env_data['measurements'].pop()
        serializer = EnvironmentSerializer(env, data=env_data)
        with self.assertRaises(rest_framework.exceptions.ValidationError):
            serializer.is_valid(raise_exception=True)
            serializer.save()

    def test_add_measurement_active(self):
        """Verify adding a measurement to an active environment fails."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        create_test_run(env)
        env_data = EnvironmentSerializer(env, context={'request': None}).data
        env_data['measurements'].append(dict(name="throughput_small_queue",
                                             unit="Mpps",
                                             higher_is_better=True,
                                             parameters=[]))
        serializer = EnvironmentSerializer(env, data=env_data)
        with self.assertRaises(rest_framework.exceptions.ValidationError):
            serializer.is_valid(raise_exception=True)
            serializer.save()

    def test_update_inactive(self):
        """Verify updating a field in an inactive environment works."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        env_data = EnvironmentSerializer(env, context={'request': None}).data
        env_data['nic_firmware_version'] = '2.0'
        serializer = EnvironmentSerializer(env, data=env_data)
        serializer.is_valid(raise_exception=True)
        env2 = serializer.save()
        self.assertEqual(env.pk, env2.pk)
        self.assertEqual(env2.nic_firmware_version, '2.0')
        env_data2 = EnvironmentSerializer(env, context={'request': None}).data
        self.assertEqual(env_data, env_data2)

    def test_update_contactpolicy_inactive(self):
        """Verify contact policy can be changed for inactive environment."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        env_data = EnvironmentSerializer(env, context={'request': None}).data
        env_data['contact_policy']['email_list'] = 'abc@example.com'
        serializer = EnvironmentSerializer(env, data=env_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        env_data2 = EnvironmentSerializer(env, context={'request': None}).data
        self.assertSerializedNestedEqual(
            env_data, env_data2, nested_lists=['measurements'],
            excludes=['contacts', 'predecessor', 'successor'],
            measurements_excludes=['environment'],
            measurements_nested_lists=['parameters'])

    def test_rm_measurement_inactive(self):
        """Verify deleting a measurement from an environment works."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        env_data = EnvironmentSerializer(env, context={'request': None}).data
        env_data['measurements'].pop()
        serializer = EnvironmentSerializer(env, data=env_data)
        serializer.is_valid(raise_exception=True)
        env2 = serializer.save()
        self.assertEqual(env.pk, env2.pk)
        env_data2 = EnvironmentSerializer(env, context={'request': None}).data
        self.assertSerializedNestedEqual(
            env_data, env_data2, nested_lists=['measurements'],
            excludes=['contacts', 'predecessor', 'successor'],
            measurements_excludes=['environment'],
            measurements_nested_lists=['parameters'])

    def test_change_measurement_inactive(self):
        """Verify modifying a measurement in an environment works."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        env_data = EnvironmentSerializer(env, context={'request': None}).data
        env_data['measurements'][0]['name'] = "throughput_biglier_queue"
        serializer = EnvironmentSerializer(env, data=env_data)
        serializer.is_valid(raise_exception=True)
        env2 = serializer.save()
        self.assertEqual(env.pk, env2.pk)
        env_data2 = EnvironmentSerializer(env, context={'request': None}).data
        self.assertEqual(len(env_data2['measurements']), 1)
        self.assertSerializedNestedEqual(
            env_data, env_data2, nested_lists=['measurements'],
            excludes=['contacts', 'predecessor', 'successor'],
            measurements_excludes=['environment'],
            measurements_nested_lists=['parameters'])

    def test_add_measurement_inactive(self):
        """Verify adding a measurement to an environment works."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        env_data = EnvironmentSerializer(env, context={'request': None}).data
        env_data['measurements'].append(dict(name="throughput_small_queue",
                                             unit="Mpps",
                                             higher_is_better=True,
                                             parameters=[
                                                 dict(name="Frame size",
                                                      unit="bytes",
                                                      value=64),
                                                 dict(name="txd/rxd",
                                                      unit="descriptors",
                                                      value=128)]))
        serializer = EnvironmentSerializer(env, data=env_data)
        serializer.is_valid(raise_exception=True)
        env2 = serializer.save()
        self.assertEqual(env.pk, env2.pk)
        env_data2 = EnvironmentSerializer(env, context={'request': None}).data
        self.assertEqual(len(env_data2['measurements']), 2)
        self.assertSerializedNestedEqual(
            env_data, env_data2, nested_lists=['measurements'],
            excludes=['contacts', 'predecessor', 'successor'],
            measurements_excludes=['environment'],
            measurements_nested_lists=['parameters'])

    def test_add_parameter_inactive(self):
        """Verify adding a measurement parameter to an environment works."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        env_data = EnvironmentSerializer(env, context={'request': None}).data
        env_data['measurements'][0]['parameters'].append(
            dict(name="CPU cores",
                 unit="cores",
                 value=1))
        serializer = EnvironmentSerializer(env, data=env_data)
        serializer.is_valid(raise_exception=True)
        env2 = serializer.save()
        self.assertEqual(env.pk, env2.pk)
        env_data2 = EnvironmentSerializer(env, context={'request': None}).data
        self.assertEqual(len(env_data2['measurements'][0]['parameters']), 3)
        self.assertSerializedNestedEqual(
            env_data, env_data2, nested_lists=['measurements'],
            excludes=['contacts', 'predecessor', 'successor'],
            measurements_excludes=['environment'],
            measurements_nested_lists=['parameters'])

    def test_change_parameter_inactive(self):
        """Verify modifying a measurement parameter from an environment works."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        env_data = EnvironmentSerializer(env, context={'request': None}).data
        env_data['measurements'][0]['parameters'][0]['unit'] = "bits"
        serializer = EnvironmentSerializer(env, data=env_data)
        serializer.is_valid(raise_exception=True)
        env2 = serializer.save()
        self.assertEqual(env.pk, env2.pk)
        env_data2 = EnvironmentSerializer(env, context={'request': None}).data
        self.assertEqual(len(env_data2['measurements'][0]['parameters']), 2)
        self.assertSerializedNestedEqual(
            env_data, env_data2, nested_lists=['measurements'],
            excludes=['contacts', 'predecessor', 'successor'],
            measurements_excludes=['environment'],
            measurements_nested_lists=['parameters'])

    def test_rm_parameter_inactive(self):
        """Verify deleting a measurement parameter from an environment works."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        env_data = EnvironmentSerializer(env, context={'request': None}).data
        env_data['measurements'][0]['parameters'].pop()
        serializer = EnvironmentSerializer(env, data=env_data)
        serializer.is_valid(raise_exception=True)
        env2 = serializer.save()
        self.assertEqual(env.pk, env2.pk)
        env_data2 = EnvironmentSerializer(env, context={'request': None}).data
        self.assertEqual(len(env_data2['measurements'][0]['parameters']), 1)
        self.assertSerializedNestedEqual(
            env_data, env_data2, nested_lists=['measurements'],
            excludes=['contacts', 'predecessor', 'successor'],
            measurements_excludes=['environment'],
            measurements_nested_lists=['parameters'])

    def test_create_environment_measurement_parameters(self):
        """Verify that deserializing and serializing an environment works."""
        serializer = EnvironmentSerializer(data=self.__class__.initial_data)
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        data = EnvironmentSerializer(env, context={'request': None}).data
        self.assertIs(data['predecessor'], None)
        self.assertIs(data['successor'], None)
        self.assertSerializedNestedEqual(
            self.__class__.initial_data, data, nested_lists=['measurements'],
            excludes=['contacts', 'predecessor', 'successor'],
            measurements_excludes=['environment'],
            measurements_nested_lists=['parameters'])


class TestRunSerializerTestCase(TestCase, SerializerAssertionMixin):
    """Test customized behavior of TestRunSerializer."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        user = User.objects.create(username='testuser', first_name='Test',
                                   last_name='User')
        group = Group.objects.create(name="TestGroup")
        user.groups.add(group)
        tarball = Tarball.objects.create(
            branch="master",
            commit_id="0000000000000000000000000000000000000000",
            tarball_url='http://host.invalid/dpdk.tar.gz')
        cls.tarball_url = reverse(
            'tarball-detail', args=[tarball.id], request=None)
        env = create_test_environment(owner=group)
        ContactPolicy.objects.create(environment=env)
        m = Measurement.objects.create(name='throughput_large_queue',
                                       unit='Mpps',
                                       higher_is_better=True,
                                       environment=env)
        Parameter.objects.create(name='Frame size', unit='bytes',
                                 value=64, measurement=m)
        Parameter.objects.create(name='txd/rxd', unit='descriptors',
                                 value=2048, measurement=m)
        cls.m_url = reverse(
            'measurement-detail', args=[m.id], request=None)
        cls.env_url = reverse(
            'environment-detail', args=[env.id], request=None)
        cls.initial_data = dict(
            tarball=cls.tarball_url,
            log_output_file='http://host.invalid/log_file.txt',
            timestamp=datetime.now(tz=pytz.utc),
            environment=cls.env_url,
            results=[dict(result='PASS',
                          difference=-0.85,
                          expected_value=None,
                          measurement=cls.m_url)])
        request = HttpRequest()
        request.user = user
        cls.context = dict(request=request)

    def test_add_test_result(self):
        """Verify that adding a test result to a run works."""
        serializer = TestRunSerializer(data=self.__class__.initial_data,
            context=self.__class__.context)
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        run_data = TestRunSerializer(run, context={'request': None}).data
        run_data['results'].append(dict(
            result='FAIL', difference=-1.25, expected_value=None,
            measurement=self.__class__.m_url))
        serializer = TestRunSerializer(run, data=run_data,
            context=self.__class__.context)
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        run_data2 = TestRunSerializer(run, context={'request': None}).data
        self.assertTrue('url' in run_data2)
        self.assertSerializedNestedEqual(run_data, run_data2,
                                         nested_lists=['results'])

    def test_remove_test_result(self):
        """Verify that deleting a test result in a run works."""
        serializer = TestRunSerializer(data=self.__class__.initial_data,
            context=self.__class__.context)
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        run_data = TestRunSerializer(run, context={'request': None}).data
        run_data['results'].pop()
        serializer = TestRunSerializer(run, data=run_data,
            context=self.__class__.context)
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        run_data2 = TestRunSerializer(run, context={'request': None}).data
        self.assertTrue('url' in run_data2)
        self.assertSerializedNestedEqual(run_data, run_data2,
                                         nested_lists=['results'])

    def test_update_test_result(self):
        """Verify that updating a test result in a run works."""
        serializer = TestRunSerializer(data=self.__class__.initial_data,
            context=self.__class__.context)
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        run_data = TestRunSerializer(run, context={'request': None}).data
        run_data['results'][0]['difference'] = -0.75
        serializer = TestRunSerializer(run, data=run_data,
            context=self.__class__.context)
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        run_data2 = TestRunSerializer(run, context={'request': None}).data
        self.assertTrue('url' in run_data2)
        self.assertSerializedNestedEqual(run_data, run_data2,
                                         nested_lists=['results'])

    def test_update_test_run(self):
        """Verify that updating a test run field works."""
        serializer = TestRunSerializer(data=self.__class__.initial_data,
            context=self.__class__.context)
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        run_data = TestRunSerializer(run, context={'request': None}).data
        run_data['log_output_file'] = 'http://host.invalid/log_file_2.txt'
        serializer = TestRunSerializer(run, data=run_data,
            context=self.__class__.context)
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        run_data2 = TestRunSerializer(run, context={'request': None}).data
        self.assertTrue('url' in run_data2)
        self.assertSerializedNestedEqual(run_data, run_data2,
                                         nested_lists=['results'])

    def test_create_test_run(self):
        """Verify that deserializing a test run creates its results."""
        serializer = TestRunSerializer(data=self.__class__.initial_data,
            context=self.__class__.context)
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        run_data = TestRunSerializer(run, context={'request': None}).data
        run_data['timestamp'] = parse_datetime(run_data['timestamp'])
        self.assertSerializedNestedEqual(
            self.__class__.initial_data, run_data, nested_lists=['results'])


class SubscriptionSerializerTestCase(TestCase):
    """Test customized behavior of SubscriptionSerializer."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        cls.user = User.objects.create(username='testuser', first_name='Test',
                                       last_name='User')
        cls.group = Group.objects.create(name="TestGroup")
        cls.env = create_test_environment(owner=cls.group)
        cls.user.groups.add(cls.group)
        cls.initial_data = dict(
            user_profile=cls.user.results_profile.id,
            environment=reverse_url('environment-detail', cls.env.id),
            email_success=False)
        request = HttpRequest()
        request.user = cls.user
        cls.context = dict(request=request)

    def test_add_subscription(self):
        """Test creating a custom subscription."""
        serializer = SubscriptionSerializer(data=self.__class__.initial_data,
                                            context=self.__class__.context)
        serializer.is_valid(raise_exception=True)
        serializer.save()


class EnvironmentHyperlinkedFieldTestCase(TestCase):
    """Test the custom environment field."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        cls.user = User.objects.create(username='testuser', first_name='Test',
                                       last_name='User')
        cls.group1 = Group.objects.create(name="TestGroup1")
        cls.group2 = Group.objects.create(name="TestGroup2")
        cls.env1 = create_test_environment(owner=cls.group1)
        cls.env2 = create_test_environment(owner=cls.group2)
        cls.user.groups.add(cls.group1)
        cls.admin = User.objects.create_superuser(
            'admin', 'ad@example.com', "AbCdEfGh3")

    def test_get_environment(self):
        """Test that only one env shows up and not both."""
        request = HttpRequest()
        request.user = self.__class__.user

        field = EnvironmentHyperlinkedField()
        field._context = dict(request=request)
        self.assertQuerysetEqual(field.get_queryset(),
            ['<Environment: IOL-IOL-1 (v0)>'])

    def test_get_environment_admin(self):
        """Test that both environments show up as an admin."""
        request = HttpRequest()
        request.user = self.__class__.admin

        field = EnvironmentHyperlinkedField()
        field._context = dict(request=request)
        self.assertQuerysetEqual(field.get_queryset(),
            ['<Environment: IOL-IOL-1 (v0)>', '<Environment: IOL-IOL-1 (v0)>'],
            ordered=False)


class PatchSetModelTestCase(TestCase):
    """Test the PatchSet and Patch models."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        cls.test_ps = PatchSet.objects.create(patch_count=3,
            message_uid='20171023231534.90996')
        Patch.objects.create(patchworks_id=30741,
              submitter='Ferruh Yigit <ferruh.yigit@intel.com>',
              message_id='20171023231534.90996-1-ferruh.yigit@intel.com',
              subject='ethdev: extract xstat basic stat count calculation',
              patchset=cls.test_ps,
              version='v2',
              patch_number=1,
              date=datetime(2017, 10, 23, 23, 15, 32, tzinfo=pytz.utc))
        Patch.objects.create(patchworks_id=30742,
              submitter='Ferruh Yigit <ferruh.yigit@intel.com>',
              message_id='20171023231534.90996-2-ferruh.yigit@intel.com',
              subject='ethdev: fix xstats get by id APIS',
              patchset=cls.test_ps,
              version='v2',
              patch_number=2,
              date=datetime(2017, 10, 23, 23, 15, 33, tzinfo=pytz.utc))

    @classmethod
    def add_last_patch(cls):
        Patch.objects.create(patchworks_id=30743,
              message_id='20171023231534.90996-3-ferruh.yigit@intel.com',
              submitter='Ferruh Yigit <ferruh.yigit@intel.com>',
              subject='ethdev: fix xstats get by id APIS',
              patchset=cls.test_ps,
              version='v2',
              patch_number=2,
              date=datetime(2017, 10, 23, 23, 15, 34, tzinfo=pytz.utc))

    def test_incomplete_property(self):
        """Test that complete returns False for an incomplete patch set."""
        self.assertFalse(self.__class__.test_ps.complete)

    def test_incomplete_query_works(self):
        """Test that the PatchSetQuerySet incomplete query works."""
        self.assertTrue(PatchSet.objects.incomplete().exists())

    def test_incomplete_complete_query(self):
        """Test that complete query does not return incomplete patch set."""
        self.assertFalse(PatchSet.objects.complete().exists())

    def test_incomplete_str(self):
        """Test string representation of incomplete patch set."""
        self.assertEqual(str(self.__class__.test_ps),
                         '20171023231534.90996 2/3')

    def test_complete_property(self):
        """Test string representation of incomplete patch set."""
        self.__class__.add_last_patch()
        self.assertTrue(self.__class__.test_ps.complete)

    def test_complete_query_works(self):
        """Test that the PatchSetQuerySet complete query works."""
        self.__class__.add_last_patch()
        self.assertTrue(PatchSet.objects.complete().exists())

    def test_complete_incomplete_query(self):
        """Test that incomplete query does not return complete patch set."""
        self.__class__.add_last_patch()
        self.assertFalse(PatchSet.objects.incomplete().exists())

    def test_complete_str(self):
        """Test string representation of complete patch set."""
        self.__class__.add_last_patch()
        self.assertEqual(str(self.__class__.test_ps),
                         '20171023231534.90996 3/3')


class OwnerTestCase(TestCase):
    """Test the owner property of test result models."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        cls.g1 = Group.objects.create(name='group1')
        cls.g2 = Group.objects.create(name='group2')
        cls.env1 = create_test_environment(owner=cls.g1)
        ContactPolicy.objects.create(environment=cls.env1)
        cls.envn = create_test_environment()
        ContactPolicy.objects.create(environment=cls.envn)

    @classmethod
    def create_measurement(self, environment):
        return Measurement.objects.create(name="throughput",
                unit="Gbps", higher_is_better=True,
                environment=environment)

    def test_measurement_owner(self):
        """Test owner property of Measurement model."""
        env = self.__class__.env1
        m = self.__class__.create_measurement(environment=env)
        self.assertEqual(m.owner, env.owner)

    def test_measurement_owner_null(self):
        """Test NULL owner of Measurement model."""
        env = self.__class__.envn
        m = self.__class__.create_measurement(environment=env)
        self.assertIsNone(m.owner)

    def test_test_result_owner(self):
        """Test owner property of TestResult model."""
        env = self.__class__.env1
        m = self.__class__.create_measurement(environment=env)
        res = TestResult(measurement=m)
        self.assertEqual(res.owner, m.owner)

    def test_test_result_owner_null(self):
        """Test NULL owner of TestResult model."""
        env = self.__class__.envn
        m = self.__class__.create_measurement(environment=env)
        res = TestResult(measurement=m)
        self.assertIsNone(res.owner)

    def test_test_run_owner(self):
        """Test owner property of TestRun model."""
        env = self.__class__.env1
        run = create_test_run(environment=env)
        for i in [-1.0, 1.0]:
            m = self.__class__.create_measurement(environment=env)
            TestResult.objects.create(result="PASS", difference=i,
                                      measurement=m, run=run)
        self.assertEqual(run.owner, env.owner)

    def test_test_run_owner_null(self):
        """Test NULL owner of TestRun model."""
        env = self.__class__.envn
        run = create_test_run(environment=env)
        m = self.__class__.create_measurement(environment=env)
        TestResult.objects.create(result="PASS", difference=-1.0,
                                  measurement=m, run=run)
        self.assertIsNone(run.owner)


class EnvironmentTestCase(TestCase):
    """Test custom functionality of environment model."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        cls.user = User.objects.create_user('joevendor',
                                            'joe@example.com', 'AbCdEfGh')
        cls.grp = Group.objects.create(name='Group1')
        cls.user.groups.add(cls.grp)

    def create_environment(self, name):
        """Create a dummy environment object for test methods.

        This is not done in setUpTestData() because test methods may modify the
        environment and this needs to be done in the per-test method transaction
        and not the class-wide transaction.
        """
        env = create_test_environment(inventory_id=name,
                                      owner=self.__class__.grp)
        ContactPolicy.objects.create(environment=env)
        return env

    def test_initial_permissions(self):
        """Verify that owner has change/delete permissions to start."""
        env = self.create_environment("test")
        self.assertTrue(
            self.__class__.user.has_perm('results.add_environment'))
        self.assertTrue(
            self.__class__.user.has_perm('results.view_environment', env))
        self.assertTrue(
            self.__class__.user.has_perm('results.change_environment', env))
        self.assertTrue(
            self.__class__.user.has_perm('results.delete_environment', env))

    def test_add_test_run_removes_permissions(self):
        """Verify that adding a test run removes change permission.

        Adding a test run to an environment needs to remove the change/delete
        permission from that environment, but preserve view permission.
        """
        env = self.create_environment("test")
        tb = Tarball.objects.create(
            tarball_url='http://example.com/dpdk.tar.gz', branch='master',
            commit_id='0000000000000000000000000000000000000000')
        TestRun.objects.create(timestamp=datetime.now(tz=pytz.utc),
                               log_output_file='http://example.com/log.tar.gz',
                               tarball=tb, environment=env)
        self.assertTrue(
            self.__class__.user.has_perm('results.view_environment', env))
        self.assertFalse(
            self.__class__.user.has_perm('results.change_environment', env))
        self.assertFalse(
            self.__class__.user.has_perm('results.delete_environment', env))

    def test_clone_works(self):
        """Verify that the clone() method works."""
        old_env = self.create_environment("test")
        new_env = old_env.clone()
        self.assertNotEqual(old_env.pk, new_env.pk)
        self.assertEqual(old_env.successor.pk, new_env.pk)
        self.assertEqual(new_env.predecessor.pk, old_env.pk)
        self.assertNotEqual(old_env.contact_policy.pk,
                            new_env.contact_policy.pk)
        self.assertEqual(old_env.contact_policy.email_submitter,
                         new_env.contact_policy.email_submitter)
        self.assertEqual(old_env.contact_policy.email_recipients,
                         new_env.contact_policy.email_recipients)
        self.assertEqual(old_env.contact_policy.email_owner,
                         new_env.contact_policy.email_owner)
        self.assertEqual(old_env.contact_policy.email_list,
                         new_env.contact_policy.email_list)

        self.assertTrue(
            self.__class__.user.has_perm('results.view_environment', new_env))
        self.assertTrue(
            self.__class__.user.has_perm('results.change_environment',
                                         new_env))
        self.assertTrue(
            self.__class__.user.has_perm('results.delete_environment',
                                         new_env))
        self.assertTrue(
            self.__class__.user.has_perm('results.view_environment', old_env))
        self.assertFalse(
            self.__class__.user.has_perm('results.change_environment',
                                         old_env))
        self.assertFalse(
            self.__class__.user.has_perm('results.delete_environment',
                                         old_env))


class TestResultTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        cls.test_tb = Tarball.objects.create(branch="master",
                commit_id="0000000000000000000000000000000000000000",
                tarball_url='http://host.invalid/dpdk.tar.gz')
        grp = Group.objects.create(name='group')
        cls.env1 = create_test_environment(owner=grp)
        ContactPolicy.objects.create(environment=cls.env1)
        cls.m1 = Measurement.objects.create(name="throughput",
                unit="Gbps", higher_is_better=True,
                environment=cls.env1)
        cls.env2 = create_test_environment(owner=grp)
        ContactPolicy.objects.create(environment=cls.env2)
        cls.m2 = Measurement.objects.create(name="throughput",
                unit="Gbps", higher_is_better=True,
                environment=cls.env2)

    def test_different_envs_fails(self):
        cls = self.__class__
        run = TestRun.objects.create(timestamp=datetime.now(tz=pytz.utc),
            log_output_file='/foo/bar', tarball=cls.test_tb,
            environment=cls.env1)
        TestResult.objects.create(result="PASS", difference=-1.0,
                                  measurement=cls.m1, run=run)
        with self.assertRaises(ValidationError):
            res2 = TestResult.objects.create(result="PASS", difference=1.0,
                                             measurement=cls.m2, run=run)
            res2.full_clean()


class SubscriptionTestCase(TestCase):
    """Test Subscription permissions."""

    def test_profile_create(self):
        """Test that a new user gets a profile."""
        user = User.objects.create(username='testuser', first_name='Test',
                                   last_name='User')
        self.assertTrue(UserProfile.objects.filter(user__pk=user.pk).exists())

    def test_unsubscribe(self):
        """Test that a user can unsubscribe himself."""
        grp = Group.objects.create(name='group')
        env = create_test_environment(owner=grp)
        user = User.objects.create(username='testuser', first_name='Test',
                                   last_name='User', email='abc@iol.unh.edu')
        user.groups.add(grp)
        sub = Subscription.objects.create(user_profile=user.results_profile,
                                          environment=env,
                                          email_success=False)
        sub.delete()
        self.assertFalse(user.email in env.contacts.values_list(
            'user_profile__user__email', flat=True))

    def test_user_in_group(self):
        """Test that a user with access can subscribe himself."""
        grp = Group.objects.create(name='group')
        env = create_test_environment(owner=grp)
        user = User.objects.create(username='testuser', first_name='Test',
                                   last_name='User', email='abc@iol.unh.edu')
        user.groups.add(grp)
        sub = Subscription(user_profile=user.results_profile,
                           environment=env,
                           email_success=False)
        sub.full_clean()
        sub.save()
        self.assertTrue(user.email in env.contacts.values_list(
            'user_profile__user__email', flat=True))

    def test_user_not_in_group(self):
        """Test that a user without access cannot subscibe himself."""
        grp = Group.objects.create(name='group')
        env = create_test_environment(owner=grp)
        user = User.objects.create(username='testuser', first_name='Test',
                                   last_name='User')
        with self.assertRaises(ValidationError):
            sub = Subscription(user_profile=user.results_profile,
                               environment=env,
                               email_success=False)
            sub.full_clean()
            sub.save()

    def test_remove_user_from_group(self):
        """Test that removing a user from a group removes subscription(s)."""
        grp = Group.objects.create(name='group')
        env = create_test_environment(owner=grp)
        user = User.objects.create(username='testuser', first_name='Test',
                                   last_name='User')
        user.groups.add(grp)
        sub = Subscription.objects.create(
            user_profile=user.results_profile, environment=env,
            email_success=False)
        grp.user_set.remove(user)
        profile = user.results_profile
        self.assertFalse(profile.subscriptions.filter(pk=sub.pk).exists())

    def test_remove_group_from_user(self):
        """Test that removing a user from a group removes subscription(s)."""
        grp = Group.objects.create(name='group')
        env = create_test_environment(owner=grp)
        user = User.objects.create(username='testuser', first_name='Test',
                                   last_name='User')
        user.groups.add(grp)
        sub = Subscription.objects.create(
            user_profile=user.results_profile, environment=env,
            email_success=False)
        user.groups.remove(grp)
        profile = user.results_profile
        self.assertFalse(profile.subscriptions.filter(pk=sub.pk).exists())

    def test_clear_group_members(self):
        """Test that clearing all members from group removes subscriptions."""
        grp = Group.objects.create(name='group')
        env = create_test_environment(owner=grp)
        user = User.objects.create(username='testuser', first_name='Test',
                                   last_name='User')
        user.groups.add(grp)
        sub = Subscription.objects.create(
            user_profile=user.results_profile, environment=env,
            email_success=False)
        grp.user_set.clear()
        profile = user.results_profile
        self.assertFalse(profile.subscriptions.filter(pk=sub.pk).exists())

    def test_clear_user_groups(self):
        """Test that clearing user's group memberships clears subscriptions."""
        grp = Group.objects.create(name='group')
        env = create_test_environment(owner=grp)
        user = User.objects.create(username='testuser', first_name='Test',
                                   last_name='User')
        user.groups.add(grp)
        profile = user.results_profile
        Subscription.objects.create(user_profile=profile, environment=env,
                                    email_success=False)
        self.assertTrue(profile.subscriptions.exists())
        user.groups.clear()
        self.assertFalse(profile.subscriptions.exists())


class SubscriptionViewSet(APITestCase):
    """Test the subscription view set."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        cls.user1 = User.objects.create_user('joevendor',
                                            'joe@example.com', 'AbCdEfGh')
        cls.user2 = User.objects.create_user('joevendor2',
                                            'joe2@example.com', 'AbCdEfGh2')
        add_subscription = Permission.objects.get(codename='add_subscription')
        cls.user1.user_permissions.add(add_subscription)
        cls.user2.user_permissions.add(add_subscription)
        cls.grp1 = Group.objects.create(name='Group1')
        cls.grp2 = Group.objects.create(name='Group2')
        cls.user1.groups.add(cls.grp1)
        cls.user2.groups.add(cls.grp2)

        cls.admin = User.objects.create_superuser(
            'admin', 'ad@example.com', "AbCdEfGh3")

    def test_get_anonymous(self):
        """Test that anonymous users can't see anything."""
        response = self.client.get(reverse('subscription-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_regular_user(self):
        """Test that regular users can't see other users subscriptions."""
        env1 = create_test_environment(owner=self.__class__.grp1)
        Subscription.objects.create(
            user_profile=self.__class__.user1.results_profile, environment=env1,
            email_success=False)

        env2 = create_test_environment(owner=self.__class__.grp2)
        Subscription.objects.create(
            user_profile=self.__class__.user2.results_profile, environment=env2,
            email_success=False)

        self.client.login(username=self.__class__.user1.username,
                          password='AbCdEfGh')
        response = self.client.get(reverse('subscription-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['environment'],
            reverse_url('environment-detail', env1.id))

        self.client.login(username=self.__class__.user2.username,
                          password='AbCdEfGh2')
        response = self.client.get(reverse('subscription-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['environment'],
            reverse_url('environment-detail', env2.id))

    def test_get_admin_user(self):
        """Test that admin can see all subscriptions."""
        env1 = create_test_environment(owner=self.__class__.grp1)
        Subscription.objects.create(
            user_profile=self.__class__.user1.results_profile,
            environment=env1, email_success=False)

        env2 = create_test_environment(owner=self.__class__.grp2)
        Subscription.objects.create(
            user_profile=self.__class__.user2.results_profile,
            environment=env2, email_success=False)

        self.client.login(username=self.__class__.admin.username,
                          password='AbCdEfGh3')
        response = self.client.get(reverse('subscription-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_post_no_perm_environment(self):
        """Test user cannot add a sub without env permissions from view."""
        env = create_test_environment(owner=self.__class__.grp2)

        self.client.login(username=self.__class__.user1.username,
                          password='AbCdEfGh')
        response = self.client.post(reverse('subscription-list'), {
            'environment': reverse_url('environment-detail', env.id),
            'email_success': None, 'how': 'to'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_perm_environment(self):
        """Test user can add a subscription from view."""
        env = create_test_environment(owner=self.__class__.grp1)

        self.client.login(username=self.__class__.user1.username,
                          password='AbCdEfGh')
        response = self.client.post(reverse('subscription-list'), {
            'environment': reverse_url('environment-detail', env.id),
            'email_success': None, 'how': 'to'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
