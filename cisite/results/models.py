"""Model data for patchsets, environments, and test results."""

import json

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth.models import Group
from django.db import models
from django.db.models import Q, F, Count


def get_admin_group():
    """Return a group of admin users."""
    return Group.objects.get_or_create(name='admins')[0]


class PatchSetQuerySet(models.QuerySet):
    """Provide queries specific for patchsets."""

    def incomplete(self):
        return self.filter(patch_count__gt=F('cur_patch_count'))

    def complete(self):
        return self.filter(patch_count=F('cur_patch_count'))

    def without_tarball(self):
        return self.filter(tarballs=None)

    def with_tarball(self):
        return self.exclude(tarballs=None)


class PatchSetManager(models.Manager):
    """Provide custom annotation for patchset objects."""

    def get_queryset(self):
        return super().get_queryset().annotate(
            cur_patch_count=Count('patches',
                                  filter=Q(patches__pw_is_active=True)))


class PatchSet(models.Model):
    """Model a single patchset."""

    message_uid = models.CharField(max_length=255, unique=True,
        help_text="Subset of patch e-mail Message-Id to match on")
    patch_count = models.PositiveIntegerField(
        help_text='Number of patches in the patch set')
    is_public = models.BooleanField(default=True,
        help_text='Was the patch set posted to a public mailing list?')
    apply_error = models.BooleanField(default=False,
        help_text='Was an error encountered trying to apply the patch?')

    objects = PatchSetManager.from_queryset(PatchSetQuerySet)()

    @property
    def complete(self):
        return self.patches.count() == self.patch_count

    def __str__(self):
        """Return string representation of patchset record."""
        return '{uid:s} {actual:d}/{expected:d}'.format(
            uid=self.message_uid, actual=self.patches.count(),
            expected=self.patch_count)

    def patchwork_range_str(self):
        """Return the range of patchwork IDs as an HTML string."""
        res = str(self.patches.first().patchworks_id)
        if self.patches.count() > 1:
            res += '&ndash;' + str(self.patches.last().patchworks_id)
        return res

    def status(self):
        """Return the status string to be displayed on the dashboard."""
        if self.apply_error:
            return "Apply Error"
        elif (not self.tarballs.exists() or
              not self.tarballs.last().runs.exists()):
            return "Pending"
        else:
            trs = self.tarballs.last().runs
            if trs.filter(results__result="FAIL").exists():
                return "Possible Regression"
            else:
                return "Pass"

    def status_class(self):
        """Return the background context class to be used on the dashboard."""
        if self.apply_error:
            return "warning"
        elif not self.tarballs.exists():
            return "secondary"
        elif not self.tarballs.last().runs.exists():
            return "primary"
        else:
            trs = self.tarballs.last().runs
            if trs.filter(results__result="FAIL").exists():
                return "danger"
            else:
                return "success"


class Tarball(models.Model):
    """Model a tarball constructed by a patchset."""

    branch = models.CharField(max_length=64, blank=False,
        help_text='DPDK branch that the patch set was applied to')
    commit_id = models.CharField('git commit hash', max_length=40, blank=False,
        help_text='git commit id that the patch set was applied to')
    job_id = models.PositiveIntegerField('Jenkins job id',
        null=True, blank=True,
        help_text='''Jenkins job id that generated this tarball

        This can be NULL if the tarball was manually created.
        ''')
    tarball_url = models.URLField(max_length=1024,
        help_text='URL from which Jenkins can download this tarball')
    patchset = models.ForeignKey(PatchSet, on_delete=models.CASCADE,
        related_name='tarballs', null=True, blank=True,
        help_text='Patchset this tarball was constructed from')

    def __str__(self):
        """Return string representation of tarball record."""
        return self.tarball_url


def validate_contact_list(value):
    xs = json.loads(value)
    for x in xs:
        if 'email' not in x:
            raise ValidationError('Patch contact does not have e-mail address')
        elif 'how' not in x or x['how'].lower() not in ('to', 'cc', 'bcc'):
            raise ValidationError('Patch contact "how" not present or '
                                  'valid; must be "to", "cc", or "bcc"')
        validate_email(x['email'])


class Patch(models.Model):
    """Model a single patch in PatchWorks."""

    patchworks_id = models.PositiveIntegerField("Patchwork ID", unique=True,
        null=True, blank=True,
        help_text="ID of patch in DPDK Patchworks instance")
    pw_is_active = models.BooleanField('Is active?', default=True,
        help_text="True if still considered active in Patchwork")
    # Per RFC, maximum length of a Message-ID is 995 characters
    message_id = models.CharField("Message-ID", max_length=1024,
        help_text="Message-ID from patch submission e-mail")
    submitter = models.CharField(max_length=128,
        help_text="Patch submitter")
    subject = models.CharField(max_length=128,
        help_text="Subject line of commit message")
    patchset = models.ForeignKey(PatchSet, on_delete=models.CASCADE,
        related_name='patches', help_text="Patchset containing this patch")
    version = models.CharField(max_length=16, help_text="Version of patchset")
    is_rfc = models.BooleanField('RFC?', default=False,
        help_text="Indicates that this patch is not to be merged")
    patch_number = models.PositiveIntegerField(
        help_text="Number of this patch within its patchset")
    date = models.DateTimeField(help_text='Date this patch was submitted')
    contacts = models.TextField(blank=True, validators=[validate_contact_list],
        help_text='Recipients listed in To and Cc field, as JSON string '
        'containing list of dictionaries with fields: '
        'display_name (optional), email (required), '
        'how (required, "to" or "cc")')

    class Meta:
        """Define metadata for patch model."""

        verbose_name_plural = "patches"
        ordering = ['patchset', 'patch_number']

    def __str__(self):
        """Return string representation of patch record."""
        rfc = ''
        if self.is_rfc:
            rfc = ',RFC'
        ver = ',' + self.version
        if ver == 'v0':
            ver = ''
        nc = ''
        pc = self.patchset.patch_count
        if pc > 1:
            nc = ',{number:d}/{count:d}'.format(
                number=self.patch_number, count=pc)
        fs = '{pwid:d} [dpdk-dev{rfc:s}{version:s}{nc:s}] {subject:s}'
        return fs.format(pwid=self.patchworks_id, rfc=rfc, version=ver,
                         nc=nc, subject=self.subject)


class ContactPolicy(models.Model):
    """Define policy for e-mailing on test failure.

    This provides a number of knobs to determine exactly who gets an e-mail
    when a test fails.
    """

    email_submitter = models.BooleanField(default=False,
        help_text="Whether or not to e-mail the patch submitter")
    email_recipients = models.BooleanField(default=False,
        help_text="Whether to e-mail the recipients of the patch")
    email_owner = models.BooleanField(default=True,
        help_text="Whether to e-mail the owner group of the environment")
    email_success = models.BooleanField(default=True,
        help_text="Set to false to send only reports of failures")
    email_list = models.CharField(max_length=128, blank=True,
        default="dpdklab@iol.unh.edu",
        help_text="Mailing list to cc on all e-mails")
    environment = models.OneToOneField(
        'Environment', on_delete=models.CASCADE,
        related_name='contact_policy',
        help_text='Environment that this contact policy applies to')

    class Meta:
        """Define metadata for contact policy model."""

        permissions = (
            ('view_contactpolicy', 'View contact policy'),
        )
        verbose_name_plural = "contact policies"

    def clone(self, environment):
        """Make a copy of this object which is unrelated to any environment."""
        new_obj = ContactPolicy.objects.get(pk=self.pk)
        new_obj.pk = None
        new_obj.environment = environment
        new_obj.save()
        return new_obj

    def __str__(self):
        """Return string representation of contact policy."""
        result = []
        if self.email_submitter:
            result.append('submitter')
        if self.email_recipients:
            result.append('recipients')
        if self.email_owner:
            result.append('owner')
        result.append(self.email_list)
        return 'Send mail to ' + ', '.join(result)


class Environment(models.Model):
    """Model an environment in which a test is run.

    This model describes the motherboard, CPU(s), RAM, and NIC hardware
    as well as the kernel and compiler versions. Ideally this should
    fully describe everything about the test environment such that two
    runs on the same environment are comparable and reproducible.
    """

    inventory_id = models.CharField(max_length=64,
        help_text='Site equipment inventory label/identifier')
    owner = models.ForeignKey(Group, on_delete=models.SET_NULL,
                              null=True, blank=False)
    motherboard_make = models.CharField(max_length=64,
        help_text='Motherboard manufacturer of Device Under Test')
    motherboard_model = models.CharField(max_length=64,
        help_text='Motherboard model of Device Under Test')
    motherboard_serial = models.CharField(max_length=64,
        help_text='Motherboard/system serial number of Device Under Test')
    cpu_socket_count = models.PositiveIntegerField(
        help_text='Number of populated physical CPUs in Device Under Test')
    cpu_cores_per_socket = models.PositiveIntegerField(
        help_text='Number of cores per physical CPU in Device Under Test')
    cpu_threads_per_core = models.PositiveIntegerField(default=1,
        help_text='Number of threads per core in Device Under Test')
    ram_type = models.CharField(max_length=64)
    ram_size = models.PositiveIntegerField(
        help_text='Size of RAM in megabytes for Device Under Test')
    ram_channel_count = models.PositiveIntegerField(default=1,
        help_text='Number of memory channels for Device Under Test')
    ram_frequency = models.PositiveIntegerField(
        help_text='RAM frequency in megahertz for Device Under Test')
    nic_make = models.CharField(max_length=64,
        help_text='Manufaturer of NIC under test')
    nic_model = models.CharField(max_length=64,
        help_text='Model of NIC under test')
    nic_speed = models.PositiveIntegerField(default=10000,
        help_text='Speed of NIC link(s) used for testing')
    nic_device_id = models.CharField(max_length=64,
        help_text='Bus-specific address or identifier of NIC under test')
    nic_device_bustype = models.CharField(max_length=64, default='pci',
        help_text='Local bus type used by device under test')
    nic_pmd = models.CharField(max_length=64,
        help_text='DPDK Physical Media Dependent (PMD) driver for testing')
    nic_firmware_source_id = models.CharField(max_length=64, blank=True,
        help_text='Source control revision for NIC firmware')
    nic_firmware_version = models.CharField(max_length=64,
        help_text='Official firmware version')
    kernel_cmdline = models.CharField(max_length=4096, blank=True,
        help_text='Kernel command line for device under test')
    kernel_name = models.CharField(max_length=32, default='linux',
        help_text='Name of operating system kernel, lowercase (default linux)')
    kernel_version = models.CharField(max_length=64,
        help_text='Version of operating system kernel, i.e., uname -r')
    compiler_name = models.CharField(max_length=32, default='gcc',
        help_text='Name of C compiler, lowercase (default gcc)')
    compiler_version = models.CharField(max_length=64,
        help_text='Version of C compiler')
    bios_version = models.CharField(max_length=64,
        help_text='Version of BIOS for Device Under Test')
    os_distro = models.CharField('OS distribution', max_length=64,
        help_text='Operating system distribution name and version, e.g., Fedora26')
    predecessor = models.OneToOneField(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='successor',
        help_text='Environment that this was cloned from')

    # These are ill-defined
    # bios_settings = models.CharField(max_length=4096)
    # dts_configuration = models.CharField(max_length=4096)

    @property
    def contacts(self):
        """Return a list of contacts to be e-mailed about test results.

        Each contact is represented as a dictionary with a display name,
        e-mail address, and a "how" field specifying whether the contact
        should be put in the To, Cc, or Bcc field of the e-mail.

        At present this list is simply built from the list of users that
        are part of the owner group. This will become more sophisticated
        in the future.
        """
        ret = []
        if not self.contact_policy:
            return []

        if self.contact_policy.email_owner:
            users = self.owner.user_set
            ret.extend(
                [{'display_name': ' '.join([x['first_name'], x['last_name']]),
                  'email': x['email'], 'how': 'to'}
                 for x in users.values('first_name', 'last_name', 'email')])
        if self.contact_policy.email_list:
            ret.append({'email': self.contact_policy.email_list, 'how': 'cc'})
        return ret

    class Meta:
        """Specify how to set up environments."""

        permissions = (
            ('view_environment', 'View environment'),
        )

    def clone(self):
        """Create and return an inactive copy of this object.

        This copy will be linked to the original object by the predecessor
        and successor attributes.
        """
        new_obj = Environment.objects.get(pk=self.pk)

        new_obj.pk = None
        new_obj.predecessor = self
        new_obj.contact_policy = None
        new_obj.save()
        new_obj.contact_policy = self.contact_policy.clone(
            environment=new_obj)
        return new_obj

    def __str__(self):
        """Return inventory ID as a string."""
        generation = 0
        p = self.predecessor
        if p is not None:
            while p is not None:
                generation += 1
                p = p.predecessor
        return '{0:s} (v{1:d})'.format(self.inventory_id, generation)


class Measurement(models.Model):
    """Model a single measurement to be taken during a test run."""

    name = models.CharField(max_length=128,
        help_text='Name of measurement; unique within an environment')
    unit = models.CharField(max_length=128,
        help_text='Units for this measurement value, e.g., Gbps')
    higher_is_better = models.BooleanField(
        help_text='True if higher numbers are better, e.g., throughput; False otherwise, e.g., latency')
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE,
        help_text='Environment that measurement applies to',
        related_name='measurements')

    @property
    def owner(self):
        """Return the owner of the environment for this measurement."""
        return self.environment.owner

    class Meta:
        """Specify how to set up measurements."""

        permissions = (
            ('view_measurement', 'View measurement'),
        )

    def __str__(self):
        """Return a string describing the measurement."""
        return '{name:s} ({unit:s})'.format(name=self.name, unit=self.unit)


class Parameter(models.Model):
    """Model an instance of an input parameter of a measurement."""

    name = models.CharField(max_length=128,
        help_text="Name of input paramater, e.g., frame_size")
    unit = models.CharField(max_length=128,
        help_text="Unit of input parameter, e.g., bytes")
    value = models.IntegerField(help_text="Value of input parameter")
    measurement = models.ForeignKey(Measurement, on_delete=models.CASCADE,
                             related_name="parameters")

    @property
    def owner(self):
        """Return the owner of the environment for this measurement."""
        return self.environment.owner

    def __str__(self):
        """Return a string describing the measurement parameter.

        Returns a string indicating the name and value of the parameter.
        """
        return '{name:s}: {value:d} {unit:s}'.format(name=self.name,
            value=self.value, unit=self.unit)


class TestRun(models.Model):
    """Model a test run of a patch set."""

    timestamp = models.DateTimeField('time run',
        help_text='Date and time that test was run')
    log_output_file = models.URLField(
        help_text='External URL of log output file')
    tarball = models.ForeignKey(Tarball, on_delete=models.CASCADE,
        related_name='runs', help_text='Tarball used for test run')
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE,
        help_text='Environment that this test run was executed on',
        related_name='runs')

    def clean(self):
        """Check that all expected measurements' environment matches."""
        if self.results.count() == 0:
            return

        env = self.environment
        values = self.results.all()
        for result in values:
            if result.measurement.environment != env:
                raise ValidationError('All results for a test run must be on the same environment.')

    @property
    def owner(self):
        """Return the owner of the test results."""
        return self.environment.owner

    class Meta:
        """Specify how to set up test runs."""

        permissions = (
            ('view_testrun', 'View test run'),
        )

    def __str__(self):
        """Return the patchset and timestamp as a string."""
        return '{url:s} {timestamp:s}'.format(
            url=self.tarball.tarball_url,
            timestamp=self.timestamp.isoformat(sep=' '))


class TestResult(models.Model):
    """Model a single test result in a patch set."""

    PASS = 'PASS'
    FAIL = 'FAIL'
    WARNING = 'WARN'
    NOT_TESTED = 'N/T'
    RESULT_CHOICES = (
        (PASS, 'Pass'),
        (FAIL, 'Fail'),
        (WARNING, 'Warning'),
        (NOT_TESTED, 'Not Tested'),
    )

    result = models.CharField(max_length=4,
        help_text='Result for this test: ' +
            ', '.join([x[0] for x in RESULT_CHOICES]))
    difference = models.FloatField(
        help_text='Difference between actual and expected values')
    expected_value = models.FloatField(null=True, blank=True,
        help_text='Value of measurement expected by vendor')
    measurement = models.ForeignKey(Measurement, on_delete=models.CASCADE,
        help_text='Vendor expected measurement that this result corresponds to')
    run = models.ForeignKey(TestRun, on_delete=models.CASCADE,
        help_text='Test run that this result is part of',
        related_name='results')

    def clean(self):
        """Check for same environment for all results."""
        if self.run is not None:
            self.run.clean()

    @property
    def owner(self):
        """Return the owner of the measurement."""
        return self.measurement.owner

    class Meta:
        """Specify how to set up test results."""

        permissions = (
            ('view_testresult', 'View test result'),
        )

    def __str__(self):
        """Return a string briefly describing the test result.

        Return a string like "throughput PASS -0.1 Gbps" for a
        test throughput measuring 4.9 Gbps against an expected
        result of 5.0 Gbps +/- 100 Mbps.
        """
        return '{name:s} {result:s} {difference:f} {unit:s}'.format(
            name=self.measurement.name, result=self.result,
            difference=self.difference, unit=self.measurement.unit)
