"""Define test cases for results app."""

from datetime import datetime
import pytz
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from results.models import Patch, PatchSet, Environment, Measurement, \
    TestRun, TestResult


class PatchSetModelTestCase(TestCase):
    """Test the PatchSet and Patch models."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        cls.test_ps = PatchSet(patchworks_id=30741, patch_count=3)
        cls.test_ps.save()
        Patch(patchworks_id=30741,
              submitter='Ferruh Yigit <ferruh.yigit@intel.com>',
              subject='ethdev: extract xstat basic stat count calculation',
              patchset=cls.test_ps,
              version='v2',
              patch_number=1,
              date=datetime(2017, 10, 23, 23, 15, 32,
                                     tzinfo=pytz.utc)).save()
        Patch(patchworks_id=30742,
              submitter='Ferruh Yigit <ferruh.yigit@intel.com>',
              subject='ethdev: fix xstats get by id APIS',
              patchset=cls.test_ps,
              version='v2',
              patch_number=2,
              date=datetime(2017, 10, 23, 23, 15, 33,
                                     tzinfo=pytz.utc)).save()

    def test_incomplete_patch_set(self):
        """Test string representation of incomplete patch set."""
        self.assertEqual(str(self.__class__.test_ps), '30741 2/3')

    def test_complete_patch_set(self):
        """Test string representation of complete patch set."""
        Patch(patchworks_id=30743,
              submitter='Ferruh Yigit <ferruh.yigit@intel.com>',
              subject='ethdev: fix xstats get by id APIS',
              patchset=self.__class__.test_ps,
              version='v2',
              patch_number=2,
              date=datetime(2017, 10, 23, 23, 15, 34,
                                     tzinfo=pytz.utc)).save()
        self.assertEqual(str(self.__class__.test_ps), '30741 3/3')


class OwnerTestCase(TestCase):
    """Test the owner property of test result models."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        cls.g1 = Group(name='group1')
        cls.g1.save()
        cls.g2 = Group(name='group2')
        cls.g2.save()

    def test_measurement_owner(self):
        """Test owner property of Measurement model."""
        env = Environment(inventory_id='IOL-IOL-1', owner=self.__class__.g1)
        m = Measurement(environment=env)
        self.assertEqual(m.owner, env.owner)

    def test_measurement_owner_null(self):
        """Test NULL owner of Measurement model."""
        env = Environment(inventory_id='IOL-IOL-1')
        m = Measurement(environment=env)
        self.assertIsNone(m.owner)

    def test_test_result_owner(self):
        """Test owner property of TestResult model."""
        env = Environment(inventory_id='IOL-IOL-1', owner=self.__class__.g1)
        m = Measurement(environment=env)
        res = TestResult(measurement=m)
        self.assertEqual(res.owner, m.owner)

    def test_test_result_owner_null(self):
        """Test NULL owner of TestResult model."""
        env = Environment(inventory_id='IOL-IOL-1')
        m = Measurement(environment=env)
        res = TestResult(measurement=m)
        self.assertIsNone(res.owner)

    def test_measurement_owner(self):
        """Test owner property of TestRun model."""
        env = Environment(inventory_id='IOL-IOL-1', owner=self.__class__.g1)
        run = TestRun()
        for i in range(2):
            m = Measurement(environment=env)
            res = TestResult(measurement=m)
            run.results.add(res)
        self.assertEqual(run.owner, env.owner)

    def test_measurement_owner_null(self):
        """Test NULL owner of TestRun model."""
        env = Environment(inventory_id='IOL-IOL-1')
        run = TestRun()
        m = Measurement(environment=env)
        res = TestResult(measurement=m)
        run.results.add(res)
        self.assertIsNone(run.owner)


class TestResultTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        cls.test_ps = PatchSet(patchworks_id=30741, patch_count=3)
        cls.test_ps.save()
        cls.g1 = Group(name='group1')
        cls.g1.save()
        cls.g2 = Group(name='group2')
        cls.g2.save()
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
                bios_version="5.05")
        cls.env1.save()
        cls.m1 = Measurement.objects.create(name="throughput",
                unit="Gbps", higher_is_better=True,
                expected_value=39.0, delta_limit=1.0, environment=cls.env1)
        cls.m1.save()
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
                bios_version="5.05")
        cls.env2.save()
        cls.m2 = Measurement.objects.create(name="throughput",
                unit="Gbps", higher_is_better=True,
                expected_value=39.0, delta_limit=1.0, environment=cls.env2)
        cls.m2.save()

    def test_different_envs_fails(self):
        cls = self.__class__
        run = TestRun.objects.create(timestamp=datetime.now(tz=pytz.utc),
            log_output_file='/foo/bar', patchset=cls.test_ps)
        res1 = TestResult.objects.create(result="PASS",
                    actual_value=38.5, measurement=cls.m1, run=run)
        with self.assertRaises(ValidationError):
            res2 = TestResult.objects.create(result="PASS",
                    actual_value=39.5, measurement=cls.m2, run=run)
            res2.full_clean()
