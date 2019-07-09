"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Define test cases for results app.
"""

from copy import deepcopy
from datetime import datetime
from tempfile import NamedTemporaryFile

import requests_mock
import rest_framework.exceptions
from django import test
from django.conf import settings
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files import File
from django.http import Http404
from django.http.request import HttpRequest
from django.test.client import RequestFactory
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now, utc
from guardian.shortcuts import assign_perm
from guardian.utils import get_anonymous_user
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from .models import PatchSet, ContactPolicy, Environment, \
    Measurement, TestCase, TestRun, TestResult, Tarball, Parameter, \
    Subscription, UserProfile, Branch, \
    upload_model_path, upload_model_path_test_run
from .serializers import EnvironmentSerializer, \
    SubscriptionSerializer, TestRunSerializer, EnvironmentHyperlinkedField
from .urls import upload_model_path as upload_model_path_url, \
    upload_model_path_test_run as upload_model_path_test_run_url
from .views import HardwareDescriptionDownloadView, TestRunLogDownloadView


def create_branch():
    """Create a dummy branch object for use by tests."""
    return Branch.objects.create(
        name=str(Branch.objects.count()), repository_url='http://git.invalid',
        last_commit_id='0' * 40)


def create_test_run(environment, **kwargs):
    """Create a dummy test run object for use by tests."""
    tb = kwargs.pop('tarball', None)
    if not tb:
        ps = PatchSet.objects.create()
        tb = Tarball.objects.create(
            branch=create_branch(), tarball_url='http://host.invalid/dpdk.tar.gz',
            commit_id="0" * 40, patchset=ps)
    tr_kwargs = {
        'timestamp': now(),
        'log_output_file': 'http://foo.invalid/bar'
    }
    tr_kwargs.update(kwargs)
    return TestRun.objects.create(tarball=tb, environment=environment,
                                  **tr_kwargs)


def create_test_environment(**kwargs):
    """Create an environment with given customizations."""
    env_args = dict(inventory_id='IOL-IOL-1',
                    motherboard_make="Intel", motherboard_model="ABCDEF",
                    motherboard_serial="12345", cpu_socket_count=1,
                    cpu_cores_per_socket=1, cpu_threads_per_core=1,
                    ram_type="DDR4", ram_size=65536, ram_channel_count=2,
                    ram_frequency=2400, nic_make="Intel",
                    nic_model="XL710", nic_dtscodename="fortville",
                    nic_device_id="01:00.0", nic_device_bustype="PCI",
                    nic_pmd="i40e", nic_firmware_version="5.05",
                    kernel_version="4.14", compiler_name="gcc",
                    compiler_version="7.1", os_distro="Fedora26",
                    bios_version="5.05", date=now())
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


class EnvironmentSerializerTestCase(test.TestCase, SerializerAssertionMixin):
    """Verify EnvironmentSerializer nested create/update works."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data for EnvironmentSerializer tests."""
        tc = TestCase.objects.create(
            name='nic_single_core_perf',
            description_url='http://git.dpdk.org/tools/dts/tree/test_plans/nic_single_core_perf_test_plan.rst?h=next')
        cls.testcase_url = reverse("testcase-detail", args=[tc.id],
                                   request=None)
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
            nic_dtscodename="models",
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
            live_since=None,
            hardware_description=None,
            pipeline=None,
            name='Vendor Model S 10000 Mbps',
            measurements=[dict(name="throughput_large_queue",
                               unit="Mpps",
                               higher_is_better=True,
                               testcase=cls.testcase_url,
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
            excludes=['contacts', 'predecessor', 'successor', 'date'],
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
            excludes=['contacts', 'predecessor', 'successor', 'date'],
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
            excludes=['contacts', 'predecessor', 'successor', 'date'],
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
                                             testcase=self.__class__.testcase_url,
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
            excludes=['contacts', 'predecessor', 'successor', 'date'],
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
            excludes=['contacts', 'predecessor', 'successor', 'date'],
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
            excludes=['contacts', 'predecessor', 'successor', 'date'],
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
            excludes=['contacts', 'predecessor', 'successor', 'date'],
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
            excludes=['contacts', 'predecessor', 'successor', 'date'],
            measurements_excludes=['environment'],
            measurements_nested_lists=['parameters'])


class TestRunSerializerTestCase(test.TestCase, SerializerAssertionMixin):
    """Test customized behavior of TestRunSerializer."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        TestCase.objects.create(
            name='nic_single_core_perf',
            description_url='http://git.dpdk.org/tools/dts/tree/test_plans/nic_single_core_perf_test_plan.rst?h=next')
        user = User.objects.create(username='testuser', first_name='Test',
                                   last_name='User')
        group = Group.objects.create(name="TestGroup")
        user.groups.add(group)
        tarball = Tarball.objects.create(
            branch=create_branch(),
            commit_id="0000000000000000000000000000000000000000",
            tarball_url='http://host.invalid/dpdk.tar.gz')
        cls.tarball_url = reverse(
            'tarball-detail', args=[tarball.id], request=None)
        cls.env = create_test_environment(owner=group)
        ContactPolicy.objects.create(environment=cls.env)
        m = Measurement.objects.create(name='throughput_large_queue',
                                       unit='Mpps',
                                       higher_is_better=True,
                                       testcase=TestCase.objects.first(),
                                       environment=cls.env)
        Parameter.objects.create(name='Frame size', unit='bytes',
                                 value=64, measurement=m)
        Parameter.objects.create(name='txd/rxd', unit='descriptors',
                                 value=2048, measurement=m)
        cls.m_url = reverse(
            'measurement-detail', args=[m.id], request=None)
        cls.env_url = reverse(
            'environment-detail', args=[cls.env.id], request=None)
        cls.initial_data = dict(
            tarball=cls.tarball_url,
            log_output_file='http://host.invalid/log_file.txt',
            log_upload_file=None,
            timestamp=now(),
            environment=cls.env_url,
            report_timestamp=None,
            commit_id='',
            commit_url='',
            branch=None,
            testcase=None,
            results=[dict(result='PASS',
                          difference=-0.85,
                          expected_value=None,
                          measurement=cls.m_url),
                     dict(result='PASS',
                          difference=-0.71,
                          expected_value=None,
                          measurement=cls.m_url),
                     ])
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
                                         nested_lists=['results'],
                                         results_excludes=['result_class'])

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
                                         nested_lists=['results'],
                                         results_excludes=['result_class'])

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
                                         nested_lists=['results'],
                                         results_excludes=['result_class'])

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
                                         nested_lists=['results'],
                                         results_excludes=['result_class'])

    def test_create_test_run(self):
        """Verify that deserializing a test run creates its results."""
        serializer = TestRunSerializer(data=self.__class__.initial_data,
            context=self.__class__.context)
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        run_data = TestRunSerializer(run, context={'request': None}).data
        run_data['timestamp'] = parse_datetime(run_data['timestamp'])
        for r in run_data['results']:
            del r['result_class']
        self.assertSerializedNestedEqual(
            self.__class__.initial_data, run_data, nested_lists=['results'],
            results_excludes=['result_class'])

    def test_create_test_run_anon(self):
        """Verify that anon user can view test run if env is anon."""
        self.__class__.env.set_public()
        anon = get_anonymous_user()
        serializer = TestRunSerializer(data=self.__class__.initial_data,
                                       context=self.__class__.context)
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        self.assertTrue(anon.has_perm('view_testrun', run))
        for result in run.results.all():
            self.assertTrue(anon.has_perm('view_testresult', result))

        # Sanity check by setting env back to private
        self.__class__.env.set_private()
        serializer = TestRunSerializer(data=self.__class__.initial_data,
                                       context=self.__class__.context)
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        self.assertFalse(anon.has_perm('view_testrun', run))
        for result in run.results.all():
            self.assertFalse(anon.has_perm('view_testresult', result))


class SubscriptionSerializerTestCase(test.TestCase):
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


class EnvironmentHyperlinkedFieldTestCase(test.TestCase):
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
            ['<Environment: Environment 1: IOL-IOL-1 [Intel XL710 10000 Mbps] (v0) Private>'])

    def test_get_environment_admin(self):
        """Test that both environments show up as an admin."""
        request = HttpRequest()
        request.user = self.__class__.admin

        field = EnvironmentHyperlinkedField()
        field._context = dict(request=request)
        self.assertQuerysetEqual(field.get_queryset(),
            ['<Environment: Environment 1: IOL-IOL-1 [Intel XL710 10000 Mbps] (v0) Private>',
             '<Environment: Environment 2: IOL-IOL-1 [Intel XL710 10000 Mbps] (v0) Private>'],
            ordered=False)


class PatchSetModelTestCase(test.TransactionTestCase):
    """Test the PatchSet and Patch models."""

    def setUp(self):
        """Reset model properties."""
        super().setUp()
        self.env_date = datetime(2017, 1, 1, tzinfo=utc)
        TestCase.objects.create(
            name='nic_single_core_perf',
            description_url='http://git.dpdk.org/tools/dts/tree/test_plans/nic_single_core_perf_test_plan.rst?h=next')
        self.test_ps = PatchSet.objects.create()
        self.env1 = create_test_environment(
            inventory_id='IOL-IOL-1', date=self.env_date, live_since=self.env_date)
        Measurement.objects.create(name='throughput', unit='Mpps',
                                   higher_is_better=True,
                                   environment=self.env1,
                                   testcase=TestCase.objects.first())
        self.env2 = create_test_environment(
            inventory_id='IOL-IOL-2', date=self.env_date, live_since=self.env_date)
        Measurement.objects.create(name='throughput', unit='Mpps',
                                   higher_is_better=True,
                                   environment=self.env2,
                                   testcase=TestCase.objects.first())

    def tearDown(self):
        """Clear cache to fix an IntegrityError bug."""
        ContentType.objects.clear_cache()
        super().tearDown()

    def test_status_pending(self):
        """Verify that status with no tarball is Pending."""
        self.assertEqual(self.test_ps.status, 'Pending')

    def test_status_apply_error(self):
        """Verify that status shows Apply Error if that is the case."""
        ps = PatchSet.objects.create(apply_error=True)
        self.assertEqual(ps.status, 'Apply Error')

    def test_status_build_error(self):
        """Verify that status shows Build Error if that is the case."""
        ps = PatchSet.objects.create(build_error=True)
        self.assertEqual(ps.status, 'Build Error')

    def test_status_waiting(self):
        """Verify that status with tarball but no results is Waiting."""
        Tarball.objects.create(branch=create_branch(), commit_id="0" * 40,
                               tarball_url='http://host.invalid/dpdk.tar.gz',
                               patchset=self.test_ps)
        self.assertEqual(self.test_ps.status, 'Waiting')

    def test_status_incomplete(self):
        """Verify that status is Incomplete where needed."""
        run = create_test_run(self.env1)
        TestResult.objects.create(result='PASS', difference=-0.002,
                                  measurement=self.env1.measurements.first(),
                                  run=run)
        run.tarball.patchset = self.test_ps
        run.tarball.save()
        self.assertEqual(self.test_ps.status, 'Incomplete')

    def test_status_incomplete_null_date(self):
        """Verify that status is Incomplete if environment date is null."""
        self.env2.date = None
        self.env2.save()
        run = create_test_run(self.env1)
        TestResult.objects.create(result='PASS', difference=-0.002,
                                  measurement=self.env1.measurements.first(),
                                  run=run)
        run.tarball.patchset = self.test_ps
        run.tarball.save()
        self.assertEqual(self.test_ps.status, 'Incomplete')

    def test_status_ignore_incomplete(self):
        """Test that adding a new environment does not trigger Incomplete."""
        run = create_test_run(self.env1)
        run.tarball.patchset = self.test_ps
        run.tarball.save()
        TestResult.objects.create(result='PASS', difference=-0.002,
                                  measurement=self.env1.measurements.first(),
                                  run=run)
        run = create_test_run(self.env2, tarball=run.tarball)
        TestResult.objects.create(result='PASS', difference=-0.021,
                                  measurement=self.env2.measurements.first(),
                                  run=run)
        env3 = create_test_environment(inventory_id='IOL-IOL-3',
                                       date=now(), live_since=now())
        Measurement.objects.create(name='throughput', unit='Mpps',
                                   higher_is_better=True,
                                   environment=env3,
                                   testcase=TestCase.objects.first())
        self.assertEqual(self.test_ps.status, 'Pass')

    def test_status_pass(self):
        """Verify that status is Pass where needed."""
        run = create_test_run(self.env1)
        run.tarball.patchset = self.test_ps
        run.tarball.save()
        TestResult.objects.create(result='PASS', difference=-0.002,
                                  measurement=self.env1.measurements.first(),
                                  run=run)
        run = create_test_run(self.env2, tarball=run.tarball)
        TestResult.objects.create(result='PASS', difference=-0.021,
                                  measurement=self.env2.measurements.first(),
                                  run=run)
        self.assertEqual(self.test_ps.status, 'Pass')

    def test_status_fail(self):
        """Verify that status is Possible Regression where needed."""
        run = create_test_run(self.env1)
        run.tarball.patchset = self.test_ps
        run.tarball.save()
        TestResult.objects.create(result='PASS', difference=-0.002,
                                  measurement=self.env1.measurements.first(),
                                  run=run)
        run = create_test_run(self.env2, tarball=run.tarball)
        TestResult.objects.create(result='FAIL', difference=-1.576,
                                  measurement=self.env2.measurements.first(),
                                  run=run)
        self.assertEqual(self.test_ps.status, 'Possible Regression')

    def test_status_ignore_fail_null(self):
        """Verify that status is Pass for null live_since."""
        self.env2.live_since = None
        self.env2.save()
        run = create_test_run(self.env1)
        run.tarball.patchset = self.test_ps
        run.tarball.save()
        TestResult.objects.create(result='PASS', difference=-0.002,
                                  measurement=self.env1.measurements.first(),
                                  run=run)
        run = create_test_run(self.env2, tarball=run.tarball)
        TestResult.objects.create(result='FAIL', difference=-1.576,
                                  measurement=self.env2.measurements.first(),
                                  run=run)
        self.assertEqual(self.test_ps.status, 'Pass')

    def test_status_ignore_fail(self):
        """Verify that status is Pass if failing result is old."""
        run = create_test_run(self.env1)
        run.tarball.patchset = self.test_ps
        run.tarball.save()
        TestResult.objects.create(result='PASS', difference=-0.002,
                                  measurement=self.env1.measurements.first(),
                                  run=run)
        run = create_test_run(self.env2, tarball=run.tarball,
                              timestamp=datetime(2016, 1, 1, tzinfo=utc))
        TestResult.objects.create(result='FAIL', difference=-1.576,
                                  measurement=self.env2.measurements.first(),
                                  run=run)
        self.assertEqual(self.test_ps.status, 'Pass')

    def test_status_use_latest(self):
        """Verify that only uses latest test run for each environment."""
        run = create_test_run(self.env1)
        run.tarball.patchset = self.test_ps
        run.tarball.save()
        TestResult.objects.create(result='PASS', difference=-0.002,
                                  measurement=self.env1.measurements.first(),
                                  run=run)
        run = create_test_run(self.env2, tarball=run.tarball)
        TestResult.objects.create(result='FAIL', difference=-1.576,
                                  measurement=self.env2.measurements.first(),
                                  run=run)
        run = create_test_run(self.env2, tarball=run.tarball)
        TestResult.objects.create(result='PASS', difference=0.017,
                                  measurement=self.env2.measurements.first(),
                                  run=run)
        self.assertEqual(self.test_ps.status, 'Pass')

    def test_status_none(self):
        """Verify that status is Indeterminate when no test results."""
        run = create_test_run(self.env1)
        run.tarball.patchset = self.test_ps
        run.tarball.save()
        create_test_run(self.env2, tarball=run.tarball)
        self.assertEqual(self.test_ps.status, 'Indeterminate')

    def test_status_fail_none(self):
        """
        Verify that status is Possible Regression when one environment fails
        and one environment has no test results.
        """
        run = create_test_run(self.env1)
        run.tarball.patchset = self.test_ps
        run.tarball.save()
        create_test_run(self.env2, tarball=run.tarball)
        run = create_test_run(self.env2, tarball=run.tarball)
        TestResult.objects.create(result='FAIL', difference=-1.576,
                                  measurement=self.env2.measurements.first(),
                                  run=run)
        self.assertEqual(self.test_ps.status, 'Possible Regression')

    def test_not_incomplete(self):
        """
        Verify that the status is Pass instead of Incomplete if live_since is
        None for an environment.
        """
        run = create_test_run(self.env1)
        run.tarball.patchset = self.test_ps
        run.tarball.save()
        TestResult.objects.create(
            result='PASS', difference=-0.002,
            measurement=self.env1.measurements.first(), run=run)
        run = create_test_run(self.env2, tarball=run.tarball)
        TestResult.objects.create(
            result='PASS', difference=-0.021,
            measurement=self.env2.measurements.first(), run=run)
        env = create_test_environment(date=self.env_date)
        Measurement.objects.create(
            name='throughput', unit='Mpps', higher_is_better=True,
            environment=env, testcase=TestCase.objects.first())
        self.assertEqual(self.test_ps.status, 'Pass')


class OwnerTestCase(test.TestCase):
    """Test the owner property of test result models."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        TestCase.objects.create(
            name='nic_single_core_perf',
            description_url='http://git.dpdk.org/tools/dts/tree/test_plans/nic_single_core_perf_test_plan.rst?h=next')
        cls.g1 = Group.objects.create(name='group1')
        cls.g2 = Group.objects.create(name='group2')
        cls.env1 = create_test_environment(owner=cls.g1)
        ContactPolicy.objects.create(environment=cls.env1)
        cls.envn = create_test_environment()
        ContactPolicy.objects.create(environment=cls.envn)

    @classmethod
    def create_measurement(self, environment):
        return Measurement.objects.create(
            name="throughput", unit="Gbps", higher_is_better=True,
            environment=environment, testcase=TestCase.objects.first())

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


class EnvironmentTestCase(test.TestCase):
    """Test custom functionality of environment model."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        TestCase.objects.create(
            name='nic_single_core_perf',
            description_url='http://git.dpdk.org/tools/dts/tree/test_plans/nic_single_core_perf_test_plan.rst?h=next')
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
        m = Measurement.objects.create(name='throughput', unit='Mpps',
                                       higher_is_better=True, environment=env,
                                       testcase=TestCase.objects.first())
        Parameter.objects.create(name='frame_size', unit='bytes', value=64,
                                 measurement=m)
        self.sub = Subscription.objects.create(
            user_profile=self.__class__.user.results_profile,
            environment=env)

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
        self.assertTrue(
            self.__class__.user.has_perm('results.add_measurement'))
        self.assertTrue(
            self.__class__.user.has_perm('results.view_measurement',
                                         env.measurements.first()))
        self.assertTrue(
            self.__class__.user.has_perm('results.change_measurement',
                                         env.measurements.first()))
        self.assertTrue(
            self.__class__.user.has_perm('results.delete_measurement',
                                         env.measurements.first()))

    def test_add_test_run_removes_permissions(self):
        """Verify that adding a test run removes change permission.

        Adding a test run to an environment needs to remove the change/delete
        permission from that environment, but preserve view permission.
        """
        env = self.create_environment("test")
        tb = Tarball.objects.create(
            tarball_url='http://example.com/dpdk.tar.gz',
            branch=create_branch(),
            commit_id='0000000000000000000000000000000000000000')
        TestRun.objects.create(timestamp=now(),
                               log_output_file='http://example.com/log.tar.gz',
                               tarball=tb, environment=env)
        self.assertTrue(
            self.__class__.user.has_perm('results.view_environment', env))
        self.assertFalse(
            self.__class__.user.has_perm('results.change_environment', env))
        self.assertFalse(
            self.__class__.user.has_perm('results.delete_environment', env))
        self.assertTrue(
            self.__class__.user.has_perm('results.view_measurement',
                                         env.measurements.first()))
        self.assertFalse(
            self.__class__.user.has_perm('results.change_measurement',
                                         env.measurements.first()))
        self.assertFalse(
            self.__class__.user.has_perm('results.delete_measurement',
                                         env.measurements.first()))

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

        old_m = old_env.measurements.first()
        new_m = new_env.measurements.first()
        self.assertEqual(old_m.name, new_m.name)
        self.assertEqual(old_m.unit, new_m.unit)
        self.assertEqual(old_m.parameters.count(), new_m.parameters.count())

        sub = Subscription.objects.get(pk=self.sub.pk)
        self.assertEqual(sub.environment.pk, new_env.pk)

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


class TestResultTestCase(test.TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        TestCase.objects.create(
            name='nic_single_core_perf',
            description_url='http://git.dpdk.org/tools/dts/tree/test_plans/nic_single_core_perf_test_plan.rst?h=next')
        cls.test_tb = Tarball.objects.create(branch=create_branch(),
                commit_id="0000000000000000000000000000000000000000",
                tarball_url='http://host.invalid/dpdk.tar.gz')
        grp = Group.objects.create(name='group')
        cls.env1 = create_test_environment(owner=grp)
        ContactPolicy.objects.create(environment=cls.env1)
        cls.m1 = Measurement.objects.create(name="throughput",
                unit="Gbps", higher_is_better=True,
                environment=cls.env1, testcase=TestCase.objects.first())
        cls.env2 = create_test_environment(owner=grp)
        ContactPolicy.objects.create(environment=cls.env2)
        cls.m2 = Measurement.objects.create(name="throughput",
                unit="Gbps", higher_is_better=True,
                environment=cls.env2, testcase=TestCase.objects.first())

    def test_different_envs_fails(self):
        cls = self.__class__
        run = TestRun.objects.create(timestamp=now(),
            log_output_file='/foo/bar', tarball=cls.test_tb,
            environment=cls.env1)
        TestResult.objects.create(result="PASS", difference=-1.0,
                                  measurement=cls.m1, run=run)
        with self.assertRaises(ValidationError):
            res2 = TestResult.objects.create(result="PASS", difference=1.0,
                                             measurement=cls.m2, run=run)
            res2.full_clean()


class MeasurementTestCase(test.TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        TestCase.objects.create(
            name='nic_single_core_perf',
            description_url='http://git.dpdk.org/tools/dts/tree/test_plans/nic_single_core_perf_test_plan.rst?h=next')
        grp = Group.objects.create(name='group')
        cls.env = create_test_environment(owner=grp)
        ContactPolicy.objects.create(environment=cls.env)

    def test_create_measurement_anon(self):
        """Verify that anon user can view measurement if env is anon."""
        self.__class__.env.set_public()
        m = Measurement.objects.create(name="throughput",
                                       unit="Gbps", higher_is_better=True,
                                       environment=self.__class__.env, testcase=TestCase.objects.first())
        anon = get_anonymous_user()
        self.assertTrue(anon.has_perm('view_measurement', m))

        # Sanity check by setting env back to private
        self.__class__.env.set_private()
        m = Measurement.objects.create(name="throughput",
                                       unit="Gbps", higher_is_better=True,
                                       environment=self.__class__.env, testcase=TestCase.objects.first())
        anon = get_anonymous_user()
        self.assertFalse(anon.has_perm('view_measurement', m))


class SubscriptionTestCase(test.TestCase):
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


class EnvironmentViewSetTestCase(APITestCase):
    """Test the environment view set."""

    def test_public_permissions(self):
        """Test view permissions on public environment."""
        user = User.objects.create_user('joevendor2', 'joe2@example.com',
                                        'AbCdEfGh')
        grp = Group.objects.create(name='Group2')
        user.groups.add(grp)

        env = create_test_environment()

        response = self.client.get(reverse('environment-list')).json()
        self.assertEqual(0, response['count'])

        env.set_public()

        # check anonymous
        response = self.client.get(reverse('environment-list')).json()
        self.assertEqual(1, response['count'])

        # check other logged in user of different group
        self.client.login(username=user.username, password='AbCdEfGh')
        response = self.client.get(reverse('environment-list')).json()
        self.assertEqual(1, response['count'])

    def test_private_permissions(self):
        """Test view permissions on private environment AFTER set public."""
        user = User.objects.create_user('joevendor2', 'joe2@example.com',
                                        'AbCdEfGh')
        grp = Group.objects.create(name='Group2')
        user.groups.add(grp)

        env = create_test_environment()

        response = self.client.get(reverse('environment-list')).json()
        self.assertEqual(0, response['count'])

        env.set_public()
        env.set_private()

        # check anonymous
        response = self.client.get(reverse('environment-list')).json()
        self.assertEqual(0, response['count'])

        # check other logged in user of different group
        self.client.login(username=user.username, password='AbCdEfGh')
        response = self.client.get(reverse('environment-list')).json()
        self.assertEqual(0, response['count'])


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


class TestDownloadURL(test.TestCase):
    """Test the download/upload urls/locations."""

    def setUp(self):
        """Set up dummy test data."""
        super().setUp()
        self.env = create_test_environment()
        self.run = create_test_run(self.env)

    def test_verify_sameness_environment(self):
        """Verify that the methods in models and urls match."""
        path = upload_model_path_url(Environment, 'hardware_description')
        self.assertEqual(path, settings.PRIVATE_STORAGE_URL[1:] +
                         'environments/<uuidhex>/hardware_description/<filename>')
        path = upload_model_path('hardware_description', self.env, 'test.pdf')
        self.assertEqual(path, f'environments/{self.env.uuid.hex}/'
                               'hardware_description/test.pdf')
        # now the actual sameness verification
        url = reverse('hardware_description', args=(self.env.uuid.hex, 'test.pdf'))
        self.assertEqual(settings.PRIVATE_STORAGE_URL + path, url)

    def test_verify_sameness_test_run(self):
        """Verify that the methods in models and urls match."""
        path = upload_model_path_test_run_url(TestRun, 'log_upload_file')
        self.assertEqual(
            path, settings.PRIVATE_STORAGE_URL[1:] +
            'test_runs/<uuidhex>/log_upload_file/<year>/<month>/<filename>')
        path = upload_model_path_test_run(
            'log_upload_file', self.run, 'test.pdf')
        year = self.run.timestamp.year
        month = self.run.timestamp.month
        friendly_datetime = self.run.timestamp.strftime('%Y-%m-%d_%H-%M-%S')
        filename = f'dpdk_000000000000_1_{friendly_datetime}_fortville.pdf'
        self.assertEqual(path, f'test_runs/{self.run.uuid.hex}/log_upload_file/'
                               f'{year}/{month}/{filename}')
        # now the actual sameness verification
        url = reverse('log_upload_file', args=(self.run.uuid.hex, year, month,
                                               filename))
        self.assertEqual(settings.PRIVATE_STORAGE_URL + path, url)

    def test_upload_model_path_test_run_no_ps(self):
        """Verify no patchset on tarball is valid."""
        tb = Tarball.objects.create(
            branch=create_branch(),
            tarball_url='http://host.invalid/dpdk.tar.gz',
            commit_id="0" * 40)
        tr_kwargs = {
            'timestamp': now(),
            'log_output_file': 'http://foo.invalid/bar',
            'tarball': tb
        }
        tr = TestRun.objects.create(environment=self.env, **tr_kwargs)
        path = upload_model_path_test_run('log_upload_file', tr, 'test.pdf')
        year = tr.timestamp.year
        month = tr.timestamp.month
        friendly_datetime = tr.timestamp.strftime('%Y-%m-%d_%H-%M-%S')
        filename = f'dpdk_000000000000_{friendly_datetime}_fortville.pdf'
        self.assertEqual(path, f'test_runs/{tr.uuid.hex}/log_upload_file/'
                               f'{year}/{month}/{filename}')


class TestDownloadViewPermission(test.TestCase):
    """Test the download view permissions."""

    def setUp(self):
        """Set up dummy test data."""
        super().setUp()
        self.user = User.objects.create_user(
            'joevendor', 'joe@example.com', 'AbCdEfGh')
        self.group = Group.objects.create(name='TestGroup')
        self.user.groups.add(self.group)
        self.tmp_file = NamedTemporaryFile()
        self.django_file = File(self.tmp_file, name='test')
        self.env = create_test_environment(
            owner=self.group, hardware_description=self.django_file)
        self.run = create_test_run(
            self.env, log_upload_file=self.django_file)

    def test_hardware_description_download_view(self):
        """Make sure a 404 does not get raised."""
        view = HardwareDescriptionDownloadView()
        view.get_object(self.env.uuid.hex)

    def test_test_run_download_view(self):
        """Make sure a 404 does not get raised."""
        view = TestRunLogDownloadView()
        view.get_object(self.run.uuid.hex)

    def test_hardware_description_download_view_get_anonymous(self):
        """Check anonymous access."""
        resp = self.client.get(self.env.hardware_description.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_hardware_description_download_view_get_user(self):
        """Check user access."""
        self.client.login(username=self.user.username, password='AbCdEfGh')
        resp = self.client.get(self.env.hardware_description.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_hardware_description_download_view_get_public(self):
        """Check user access if download is supposed to be public."""
        user = User.objects.create_user(
            'joevendor2', 'joe2@example.com', 'AbCdEfGh')
        group = Group.objects.create(name='TestGroup2')
        user.groups.add(group)
        # make environment with self group
        env = create_test_environment(
            owner=self.group, hardware_description=self.django_file)
        env.set_public()

        # check anonymous is ok
        resp = self.client.get(env.hardware_description.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # check that a different group logged in user is ok
        self.client.login(username=user.username, password='AbCdEfGh')
        resp = self.client.get(env.hardware_description.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_hardware_description_download_view_get_private(self):
        """Check user access if download is private AFTER set public."""
        user = User.objects.create_user(
            'joevendor2', 'joe2@example.com', 'AbCdEfGh')
        group = Group.objects.create(name='TestGroup2')
        user.groups.add(group)
        # make environment with self group
        env = create_test_environment(
            owner=self.group, hardware_description=self.django_file)

        env.set_public()
        env.set_private()

        # check anonymous
        resp = self.client.get(env.hardware_description.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # check other logged in user of different group
        self.client.login(username=user.username, password='AbCdEfGh')
        resp = self.client.get(env.hardware_description.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_log_upload_file_download_view_get_public(self):
        """Check user access if download is supposed to be public.

        Test runs are to remain private even if the environment is public to
        avoid download of absolute values.
        """
        user = User.objects.create_user(
            'joevendor2', 'joe2@example.com', 'AbCdEfGh')
        group = Group.objects.create(name='TestGroup2')
        user.groups.add(group)
        # make environment with self group
        env = create_test_environment(
            owner=self.group, hardware_description=self.django_file)
        run = create_test_run(
            env, log_upload_file=self.django_file)

        env.set_public()

        # check anonymous cant access
        resp = self.client.get(run.log_upload_file.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # check that a different group logged in user can't access
        self.client.login(username=user.username, password='AbCdEfGh')
        resp = self.client.get(run.log_upload_file.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_test_run_download_view_get_anonymous(self):
        """Check anonymous access."""
        resp = self.client.get(self.run.log_upload_file.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_test_run_download_view_get_user(self):
        """Check user access."""
        self.client.login(username=self.user.username, password='AbCdEfGh')
        resp = self.client.get(self.run.log_upload_file.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_for_404(self):
        """Test that a 404 gets raised instead of 500."""
        dpv = HardwareDescriptionDownloadView()
        with self.assertRaises(Http404):
            dpv.get_object('abcdefg')


@requests_mock.Mocker(real_http=True)
class TestRerun(test.TestCase):
    """Test the rerun permissions."""

    def setUp(self):
        """Set up dummy test data."""
        super().setUp()
        self.user = User.objects.create_user(
            'joevendor', 'joe@example.com', 'AbCdEfGh')
        self.group = Group.objects.create(name='TestGroup')
        self.user.groups.add(self.group)
        env = create_test_environment(
            owner=self.group, pipeline='pipeline-env')
        tc = TestCase.objects.create(
            name='nic_single_core_perf',
            description_url='http://git.dpdk.org/tools/dts/tree/test_plans/nic_single_core_perf_test_plan.rst?h=next',
            pipeline='pipeline-tc')
        Measurement.objects.create(name='throughput', unit='Mpps',
                                   higher_is_better=True,
                                   environment=env,
                                   testcase=tc)
        self.tr = create_test_run(env)
        TestResult.objects.create(result='PASS', difference=-0.002,
                                  measurement=env.measurements.first(),
                                  run=self.tr)
        tr_url = 'http://testserver' + self.tr.tarball.get_absolute_url()
        pipeline = f'{env.pipeline}-{tc.pipeline}'
        self.pipeline_url = f'{settings.JENKINS_URL}job/{pipeline}/' \
                            'buildWithParameters/?' \
                            f'TARBALL_META_URL={tr_url}'

    def test_valid_user(self, m):
        m.register_uri('POST', self.pipeline_url)

        self.client.login(username=self.user.username, password='AbCdEfGh')
        resp = self.client.post(reverse('testrun-rerun', args=(self.tr.id,)))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_other_user(self, m):
        """Make sure a user of a different group can't rerun the test."""
        user = User.objects.create_user(
            'joevendor2', 'joe@example.com', 'AbCdEfGh')
        group = Group.objects.create(name='TestGroup2')
        user.groups.add(group)

        self.client.login(username=user.username, password='AbCdEfGh')
        resp = self.client.post(reverse('testrun-rerun', args=(self.tr.id,)))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous(self, m):
        """Make sure a user of a different group can't rerun the test."""
        resp = self.client.post(reverse('testrun-rerun', args=(self.tr.id,)))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


@requests_mock.Mocker(real_http=True)
class TestRebuild(test.TestCase):
    """Test the rebuild permissions."""

    def setUp(self):
        """Set up dummy test data."""
        super().setUp()
        self.user = User.objects.create_user(
            'joevendor', 'joe@example.com', 'AbCdEfGh')
        self.group = Group.objects.create(name='TestGroup')
        self.user.groups.add(self.group)
        self.ps = PatchSet.objects.create()
        self.branch = create_branch()
        ps_url = 'http://testserver' + self.ps.get_absolute_url()
        branch_url = 'http://testserver' + self.branch.get_absolute_url()
        self.pipeline_url = f'{settings.JENKINS_URL}job/'\
            'Apply-Custom-Patch-Set/buildWithParameters/?' \
            f'PATCHSET_META_URL={ps_url}&' \
            f'BRANCH={branch_url}'

    def test_valid_user(self, m):
        """Make sure authenticated users can rebuild the patchset."""
        m.register_uri('POST', self.pipeline_url)

        self.client.login(username=self.user.username, password='AbCdEfGh')
        resp = self.client.post(reverse('patchset-rebuild',
                                        args=(self.ps.id, self.branch.name)))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_anonymous(self, m):
        """Make sure anonymous users can't rebuild the patchset."""
        resp = self.client.post(reverse('patchset-rebuild',
                                        args=(self.ps.id, self.branch.name)))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_branch_exists(self, m):
        """Make sure a 404 gets returned for a branch that does not exist."""
        m.register_uri('POST', self.pipeline_url)

        self.client.login(username=self.user.username, password='AbCdEfGh')
        resp = self.client.post(reverse('patchset-rebuild',
                                        args=(self.ps.id, 'does-not-exist')))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_no_ps_exists(self, m):
        """Make sure a 404 gets returned for a patchset that does not exist."""
        m.register_uri('POST', self.pipeline_url)

        self.client.login(username=self.user.username, password='AbCdEfGh')
        resp = self.client.post(reverse('patchset-rebuild',
                                        args=(999999, self.branch.name)))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class TestUser(test.TestCase):
    """Test the user model permissions."""

    def setUp(self):
        """Set up dummy test data."""
        super().setUp()
        # Primary contact
        self.pc = User.objects.create_user(
            'contact', 'admin@example.com', 'AbCdEfGh')
        self.group = Group.objects.create(name='TestGroup')
        self.group2 = Group.objects.create(name='TestGroup2')
        self.pc.groups.add(self.group)
        self.pc.groups.add(self.group2)
        self.pc.results_profile.save()
        assign_perm('manage_group', self.pc, self.group.results_vendor)

        # Employee
        self.user_of_group = User.objects.create_user(
            'joevendor', 'joe@example.com', 'AbCdEfGh')
        self.user_of_group.groups.add(self.group)

        # Some other vendor
        self.user_other = User.objects.create_user(
            'othervendor', 'ov@example.com', 'AbCdEfGh')
        self.user_other.groups.add(self.group2)

        # Some random person
        self.user_rand = User.objects.create_user(
            'novendor', 'no@example.com', 'AbCdEfGh')

    def test_no_login(self):
        """Sanity check that anonymous users can't list users."""
        resp = self.client.get(reverse('user-list'))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        resp = self.client.get(reverse('user-list'), {'managed': True})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        resp = self.client.get(reverse('user-list'), {'managed': False})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_anon_managed_filter(self):
        """Test anonymous user does not show up to pc.

        Test that they do not show up in both managed and unmanaged filter.
        """
        self.client.login(username=self.pc.username, password='AbCdEfGh')

        resp = self.client.get(reverse('user-list'), {'managed': True}).json()
        # Since pc is part of group1 and manages group1
        self.assertEqual(resp['count'], 1)
        for result in resp['results']:
            self.assertTrue(result['username'] != 'AnonymousUser')

        resp = self.client.get(reverse('user-list'), {'managed': False}).json()
        # Since pc is part of group2 (but cant manage group2)
        self.assertEqual(resp['count'], 1)
        for result in resp['results']:
            self.assertTrue(result['username'] != 'AnonymousUser')

    def test_pc_proper_users(self):
        """Test primary contact group.

        Test that they can only see the literal group they are supposed to
        manage when primary contact is part of many groups.
        """
        # Sanity check
        self.assertTrue(len(self.pc.groups.all()) >= 2)
        self.client.login(username=self.pc.username, password='AbCdEfGh')

        resp = self.client.get(reverse('user-list'), {'managed': True}).json()
        self.assertEqual(resp['count'], 1)
        contains = False
        for result in resp['results']:
            self.assertTrue(result['username'] != self.user_other.username)
            if result['username'] == self.user_of_group.username:
                contains = True
        self.assertTrue(contains)

    def test_non_pc_ok(self):
        """Test that a regular user can see user list properly."""
        self.client.login(username=self.user_of_group.username, password='AbCdEfGh')

        resp = self.client.get(reverse('user-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['count'], 2)
        resp = self.client.get(reverse('user-list'), {'managed': True})
        self.assertEqual(resp.json()['count'], 0)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        resp = self.client.get(reverse('user-list'), {'managed': False})
        self.assertEqual(resp.json()['count'], 2)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_pc_directly(self):
        """Test pc can manage users part of their group."""
        self.client.login(username=self.pc.username, password='AbCdEfGh')

        # remove user in group
        resp = self.client.delete(
            reverse('user-manage-group', args=(self.user_of_group.username, self.group.name)))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        resp = self.client.get(reverse('user-list'))
        for result in resp.json()['results']:
            self.assertTrue(result['username'] != self.user_of_group.username)

        # add user to group
        resp = self.client.post(
            reverse('user-manage-group', args=(self.user_rand.username, self.group.name)))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        resp = self.client.get(reverse('user-list'))
        in_group = False
        for result in resp.json()['results']:
            if result['username'] == self.user_rand.username:
                in_group = True
                break
        self.assertTrue(in_group)

    def test_non_pc_no_perm(self):
        """Test regular user can't manage users. (non 500)"""
        self.client.login(username=self.user_of_group.username, password='AbCdEfGh')

        # user in different group
        # remove
        resp = self.client.delete(
            reverse('user-manage-group', args=(self.user_other.username, self.group2.name)))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        # add
        resp = self.client.post(
            reverse('user-manage-group', args=(self.user_other.username, self.group2.name)))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # non existent group
        # remove
        resp = self.client.delete(
            reverse('user-manage-group', args=(self.user_other.username, 'no-exist')))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        # add
        resp = self.client.post(
            reverse('user-manage-group', args=(self.user_other.username, 'no-exist')))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # non existent user
        # remove
        resp = self.client.delete(
            reverse('user-manage-group', args=('no-exist', self.group2.name)))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        # add
        resp = self.client.post(
            reverse('user-manage-group', args=('no-exist', self.group2.name)))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_pc_diff_group(self):
        """Test pc can't manage user not part of their group. (non 500)"""
        self.client.login(username=self.pc.username, password='AbCdEfGh')

        # user in different group
        # remove user from non pc group, in same group as pc
        resp = self.client.delete(
            reverse('user-manage-group', args=(self.user_other.username, self.group2.name)))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        # add user to non pc group
        resp = self.client.post(
            reverse('user-manage-group', args=(self.user_rand.username, self.group2.name)))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        # non existent group
        # remove
        resp = self.client.delete(
            reverse('user-manage-group', args=(self.user_other.username, 'no-exist')))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        # add
        resp = self.client.post(
            reverse('user-manage-group', args=(self.user_other.username, 'no-exist')))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        # non existent user
        # remove
        resp = self.client.delete(
            reverse('user-manage-group', args=('no-exist', self.group2.name)))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        # add
        resp = self.client.post(
            reverse('user-manage-group', args=('no-exist', self.group2.name)))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
