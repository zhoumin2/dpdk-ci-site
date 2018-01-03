"""Model data for patchsets, environments, and test results."""

from django.contrib.auth.models import Group
from django.db import models


def get_admin_group():
    """Return a group of admin users."""
    return Group.objects.get_or_create(name='admins')[0]


class PatchSet(models.Model):
    """Model a single patchset."""

    patchworks_id = models.IntegerField(unique=True)
    branch = models.CharField(max_length=64)
    commit_id = models.CharField('git commit hash', max_length=40)
    tarball = models.CharField(max_length=256)
    patch_count = models.IntegerField()

    def __str__(self):
        """Return string representation of patchset record."""
        return '{pid:d} {actual:d}/{expected:d}'.format(
            pid=self.patchworks_id, actual=self.patches.count(),
            expected=self.patch_count)


class Patch(models.Model):
    """Model a single patch in PatchWorks."""

    patchworks_id = models.IntegerField(unique=True)
    submitter = models.CharField(max_length=128)
    subject = models.CharField(max_length=128)
    patchset = models.ForeignKey(PatchSet, on_delete=models.CASCADE,
                                 related_name='patches')
    version = models.CharField(max_length=16)
    patch_number = models.IntegerField()
    date = models.DateTimeField('date submitted')

    def __str__(self):
        """Return string representation of patch record."""
        return '[PATCH,{version:s},{number:d},{count:d}] {subject:s}'.format(
            version=self.version, subject=self.subject,
            number=self.patch_number, count=self.patchset.patch_count)


class Environment(models.Model):
    """Model an environment in which a test is run.

    This model describes the motherboard, CPU(s), RAM, and NIC hardware
    as well as the kernel and compiler versions. Ideally this should
    fully describe everything about the test environment such that two
    runs on the same environment are comparable and reproducible.
    """

    inventory_id = models.CharField(max_length=64)
    owner = models.ForeignKey(Group, on_delete=models.SET_DEFAULT,
                              default=get_admin_group)
    motherboard_make = models.CharField(max_length=64)
    motherboard_model = models.CharField(max_length=64)
    motherboard_serial = models.CharField(max_length=64)
    cpu_socket_count = models.IntegerField()
    cpu_cores_per_socket = models.IntegerField()
    cpu_threads_per_core = models.IntegerField()
    ram_type = models.CharField(max_length=64)
    ram_size = models.IntegerField('RAM size in megabytes')
    ram_channel_count = models.IntegerField()
    ram_frequency = models.IntegerField('RAM frequency in megahertz')
    nic_make = models.CharField(max_length=64)
    nic_model = models.CharField(max_length=64)
    nic_device_id = models.CharField(max_length=64)
    nic_device_bustype = models.CharField(max_length=64)
    nic_pmd = models.CharField(max_length=64)
    nic_firmware_source_id = models.CharField(max_length=64)
    nic_firmware_version = models.CharField(max_length=64)
    kernel_cmdline = models.CharField(max_length=4096)
    kernel_name = models.CharField(max_length=32)
    kernel_version = models.CharField(max_length=64)
    compiler_name = models.CharField(max_length=32)
    compiler_version = models.CharField(max_length=64)
    bios_version = models.CharField(max_length=64)

    # These are ill-defined
    # bios_settings = models.CharField(max_length=4096)
    # dts_configuration = models.CharField(max_length=4096)

    def __str__(self):
        """Return inventory ID as a string."""
        return self.inventory_id


class Measurement(models.Model):
    """Model a single measurement to be taken during a test run."""

    name = models.CharField(max_length=128)
    unit = models.CharField(max_length=128)
    higher_is_better = models.BooleanField()
    expected_value = models.FloatField()
    delta_limit = models.FloatField()
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE,
                                    related_name='measurements')

    def __str__(self):
        """Return a string describing the measurement.

        Return a string like "throughput ^ 5.0 0.1" for a throughput
        measurement expected to be 5.0 Gbps with an allowed variation
        of 100 Mbps.
        """
        hl = 'v'
        if self.higher_is_better:
            hl = '^'
        return '{name:s} {expected:f} {hl:s} {delta:f}'.format(
            name=self.name, expected=self.expected_value,
            delta=self.delta_limit, hl=hl)


class TestResult(models.Model):
    """Model a single test result in a patch set."""

    result = models.CharField(max_length=64)
    actual_value = models.FloatField()
    measurement = models.ForeignKey(Measurement, on_delete=models.CASCADE)

    def __str__(self):
        """Return a string briefly describing the test result.

        Return a string like "throughput PASS 4.9/5.0+-0.1" for a
        test throughput measuring 4.9 Gbps against an expected
        result of 5.0 Gbps +/- 100 Mbps.
        """
        return '{name:s} {result:s} {actual:f}/{expected:f}+-{delta:f}'.format(
            name=self.measurement.name, result=self.result,
            actual=self.actual_value,
            expected=self.measurement.expected_value,
            delta=self.measurement.delta_limit)


class TestRun(models.Model):
    """Model a test run of a patch set."""

    timestamp = models.DateTimeField('time run')
    log_output_file = models.CharField(max_length=4096)
    is_official = models.BooleanField()
    patchset = models.ForeignKey(PatchSet, on_delete=models.CASCADE,
                                 related_name='test_runs')
    result = models.ForeignKey(TestResult, on_delete=models.CASCADE,
                               related_name='results')

    def __str__(self):
        """Return the patchset and timestamp as a string."""
        return '{psid:d} {timestamp:s}'.format(
            psid=self.patchset.patchworks_id,
            timestamp=self.timestamp.isoformat(sep=' '))
