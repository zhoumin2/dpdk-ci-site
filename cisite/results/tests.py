"""Define test cases for results app."""

from datetime import datetime
import pytz
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory
from .models import Patch, PatchSet, ContactPolicy, Environment, \
    Measurement, TestRun, TestResult, Tarball, Parameter
from .serializers import PatchSerializer, EnvironmentSerializer, \
    TarballSerializer, TestRunSerializer


class PatchSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        cls.test_ps = PatchSet.objects.create(patch_count=3,
            message_uid='20171023231534.90996')

    def test_create_patchset_does_not_exist(self):
        serializer = PatchSerializer(data=dict(patchworks_id=30744,
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


class EnvironmentSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        factory = APIRequestFactory()
        request = factory.get('/')
        group = Group.objects.create(name="TestGroup")
        cls.group_url = reverse(
            "group-detail", args=[group.id], request=request)

    def test_create_environment_measurement_parameters(self):
        serializer = EnvironmentSerializer(data=dict(
            owner=self.__class__.group_url,
            inventory_id="inventory_id",
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
            nic_device_id="07:00.0",
            nic_device_bustype="PCI",
            nic_pmd="models",
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
            contact_policy=dict()))
        serializer.is_valid(raise_exception=True)
        env = serializer.save()
        self.assertEqual(env.measurements.count(), 1)
        self.assertEqual(env.measurements.all()[0].name,
                         "throughput_large_queue")
        self.assertEqual(env.measurements.all()[0].parameters.count(), 2)
        self.assertEqual(env.measurements.all()[0].parameters.all()[0].name,
                         "Frame size")
        self.assertEqual(env.measurements.all()[0].parameters.all()[1].name,
                         "txd/rxd")


class TestRunSerializerTestCase(TestCase):
    """Test customized behavior of TestRunSerializer."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        factory = APIRequestFactory()
        request = factory.get('/')
        group = Group.objects.create(name="TestGroup")
        tarball = Tarball.objects.create(
            branch="master",
            commit_id="0000000000000000000000000000000000000000",
            tarball_url='http://host.invalid/dpdk.tar.gz')
        cls.tarball_url = reverse(
            'tarball-detail', args=[tarball.id], request=request)
        env = Environment.objects.create(
            owner=group,
            inventory_id='IOL-IOL-1', motherboard_make="Intel",
            motherboard_model="ABCDEF", motherboard_serial="12345",
            cpu_socket_count=1, cpu_cores_per_socket=1, cpu_threads_per_core=1,
            ram_type="DDR4", ram_size=65536, ram_channel_count=2,
            ram_frequency=2400, nic_make="Intel", nic_model="XL710",
            nic_device_id="01:00.0", nic_device_bustype="PCI", nic_pmd="i40e",
            nic_firmware_version="5.05", kernel_version="4.14",
            os_distro="Fedora26",
            compiler_name="gcc", compiler_version="7.1", bios_version="5.05")
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
            'measurement-detail', args=[m.id], request=request)
        cls.env_url = reverse(
            'environment-detail', args=[env.id], request=request)

    def test_create_test_run(self):
        """Verify that deserializing a test run creates its results."""
        serializer = TestRunSerializer(
            data=dict(tarball=self.__class__.tarball_url,
                      log_output_file='http://host.invalid/log_file.txt',
                      timestamp=datetime.now(tz=pytz.utc),
                      environment=self.__class__.env_url,
                      results=[dict(result='PASS',
                                    difference=-0.85,
                                    measurement=self.__class__.m_url)]))
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        self.assertEqual(run.results.count(), 1)
        self.assertEqual(run.results.all()[0].result, 'PASS')


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
        cls.env1 = Environment.objects.create(inventory_id='IOL-IOL-1',
                motherboard_make="Intel", motherboard_model="ABCDEF",
                motherboard_serial="12345", cpu_socket_count=1,
                cpu_cores_per_socket=1, cpu_threads_per_core=1,
                ram_type="DDR4", ram_size=65536, ram_channel_count=2,
                ram_frequency=2400, nic_make="Intel",
                nic_model="XL710", nic_device_id="01:00.0",
                nic_device_bustype="PCI", nic_pmd="i40e",
                nic_firmware_version="5.05", kernel_version="4.14",
                compiler_name="gcc", compiler_version="7.1",
                os_distro="Fedora26", bios_version="5.05", owner=cls.g1)
        ContactPolicy.objects.create(environment=cls.env1)
        cls.envn = Environment.objects.create(inventory_id='IOL-IOL-1',
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
        ContactPolicy.objects.create(environment=cls.envn)

    @classmethod
    def create_measurement(self, environment):
        return Measurement.objects.create(name="throughput",
                unit="Gbps", higher_is_better=True,
                environment=environment)

    @classmethod
    def create_test_run(cls, environment):
        tb = Tarball.objects.create(branch="master",
                commit_id="0000000000000000000000000000000000000000",
                tarball_url='http://host.invalid/dpdk.tar.gz')
        return TestRun.objects.create(timestamp=datetime.now(tz=pytz.utc),
            log_output_file='/foo/bar', tarball=tb, environment=environment)

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
        run = self.__class__.create_test_run(environment=env)
        for i in [-1.0, 1.0]:
            m = self.__class__.create_measurement(environment=env)
            res = TestResult.objects.create(result="PASS",
                difference=i, measurement=m, run=run)
        self.assertEqual(run.owner, env.owner)

    def test_test_run_owner_null(self):
        """Test NULL owner of TestRun model."""
        env = self.__class__.envn
        run = self.__class__.create_test_run(environment=env)
        m = self.__class__.create_measurement(environment=env)
        res = TestResult.objects.create(result="PASS",
            difference=-1.0, measurement=m, run=run)
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
        env = Environment.objects.create(
            inventory_id=name, owner=self.__class__.grp,
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
        self.assertIs(old_env.successor, new_env)
        self.assertIs(new_env.predecessor, old_env)
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
        cls.g1 = Group.objects.create(name='group1')
        cls.g2 = Group.objects.create(name='group2')
        cls.env1 = Environment.objects.create(inventory_id='IOL-IOL-1',
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
        ContactPolicy.objects.create(environment=cls.env1)
        cls.m1 = Measurement.objects.create(name="throughput",
                unit="Gbps", higher_is_better=True,
                environment=cls.env1)
        cls.env2 = Environment.objects.create(inventory_id='IOL-IOL-2',
                motherboard_make="Intel", motherboard_model="ABCDEF",
                motherboard_serial="12346", cpu_socket_count=1,
                cpu_cores_per_socket=1, cpu_threads_per_core=1,
                ram_type="DDR4", ram_size=65536, ram_channel_count=2,
                ram_frequency=2400, nic_make="Intel",
                nic_model="XL710", nic_device_id="01:00.0",
                nic_device_bustype="PCI", nic_pmd="i40e",
                nic_firmware_version="5.05", kernel_version="4.14",
                compiler_name="gcc", compiler_version="7.1",
                os_distro="Fedora26", bios_version="5.05")
        ContactPolicy.objects.create(environment=cls.env2)
        cls.m2 = Measurement.objects.create(name="throughput",
                unit="Gbps", higher_is_better=True,
                environment=cls.env2)

    def test_different_envs_fails(self):
        cls = self.__class__
        run = TestRun.objects.create(timestamp=datetime.now(tz=pytz.utc),
            log_output_file='/foo/bar', tarball=cls.test_tb,
            environment=cls.env1)
        res1 = TestResult.objects.create(result="PASS",
                    difference=-1.0, measurement=cls.m1, run=run)
        with self.assertRaises(ValidationError):
            res2 = TestResult.objects.create(result="PASS",
                    difference=1.0, measurement=cls.m2, run=run)
            res2.full_clean()
