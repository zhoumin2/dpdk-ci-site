"""Model data for patchsets, environments, and test results."""

import json

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth.models import Group, User
from django.db import models
from django.db.models import Q, F, Count
from django.utils.functional import cached_property
from django.utils.timezone import now
from functools import partial
from private_storage.fields import PrivateFileField


def get_admin_group():
    """Return a group of admin users."""
    return Group.objects.get_or_create(name='admins')[0]


def upload_model_path(field, instance, filename):
    """Upload files based on their model name, primary key, and field.

    NOTE: the `partial` method needs to be used to pass in the field.

    This is utilized for private storage. urls.upload_model_path will also
    have to be updated if this gets changed.
    """
    return f'{instance.__class__._meta.verbose_name_plural.replace(" ", "_")}/{instance.pk}/{field}/{filename}'


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

    statuses = {
        'Pass': {
            'class': 'success',
            'tooltip': 'All test results were within the tolerance threshold '
                       'from the expected result',
        },
        'Possible Regression': {
            'class': 'danger',
            'tooltip': 'At least one test result was below the tolerance '
                       'threshold from the expected result',
        },
        'Apply Error': {
            'class': 'warning',
            'tooltip': 'The patch series could not be applied or built',
        },
        'Incomplete': {
            'class': 'warning',
            'tooltip': 'Not all test cases have been completed for this '
                       'patch series',
        },
        'Waiting': {
            'class': 'primary',
            'tooltip': 'A tarball has been generated but no test results '
                       'are available yet',
        },
        'Pending': {
            'class': 'secondary',
            'tooltip': 'A tarball has not yet been generated for this '
                       'patch series',
        },
    }

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

    @property
    def time_to_last_test(self):
        """Return the time from submission to last test run."""
        tarball = self.tarballs.last()
        return tarball.runs.last().timestamp - self.patches.first().date

    def patchwork_range_str(self):
        """Return the range of patchwork IDs as an HTML string."""
        res = str(self.patches.first().patchworks_id)
        if self.patches.count() > 1:
            res += '&ndash;' + str(self.patches.last().patchworks_id)
        return res

    @cached_property
    def status(self):
        """Return the status string to be displayed on the dashboard."""
        if self.apply_error:
            return "Apply Error"
        elif not self.tarballs.exists():
            return "Pending"
        else:
            return self.tarballs.last().status

    def status_class(self):
        """Return the background context class to be used on the dashboard."""
        return self.statuses.get(self.status, dict()).get('class', 'warning')

    def status_tooltip(self):
        """Return the status tooltip to be used on the dashboard."""
        return self.statuses.get(self.status, dict()).get('tooltip',
                                                          self.status)


class Branch(models.Model):
    """Model a DPDK repository branch."""

    name = models.CharField(
        max_length=64, blank=False, unique=True,
        help_text='Name of the branch')
    repository_url = models.URLField(
        max_length=1024, help_text='Upstream URL of the repository')
    regexp = models.CharField(
        max_length=256, blank=True,
        help_text='Regular expression of subject lines that should be applied'
                  ' to this branch')
    last_commit_id = models.CharField(
        max_length=40, blank=False,
        help_text='Commit ID of last tested commit on this branch')

    class Meta:
        """Define metadata for branch model."""

        verbose_name_plural = "branches"

    def __str__(self):
        """Return string representation of branch record."""
        return self.name


class Tarball(models.Model):
    """Model a tarball constructed by a patchset."""

    branch = models.CharField(max_length=64, blank=False,
        help_text='DPDK branch that the patch set was applied to')
    commit_id = models.CharField('git commit hash', max_length=40, blank=False,
        help_text='git commit id that the patch set was applied to')
    job_name = models.CharField('Jenkins job name', max_length=128, blank=True,
        help_text='Name of Jenkins job that generated this tarball. '
        'This can be NULL if the tarball was manually created.')
    build_id = models.PositiveIntegerField('Jenkins build id',
        null=True, blank=True,
        help_text='Jenkins build id that generated this tarball. '
        'This can be NULL if the tarball was manually created.')
    tarball_url = models.URLField(max_length=1024,
        help_text='URL from which Jenkins can download this tarball')
    patchset = models.ForeignKey(PatchSet, on_delete=models.CASCADE,
        related_name='tarballs', null=True, blank=True,
        help_text='Patchset this tarball was constructed from')
    date = models.DateTimeField(
        null=True, default=now,
        help_text='When this tarball was generated')

    def __str__(self):
        """Return string representation of tarball record."""
        return self.tarball_url

    @property
    def commit_url(self):
        return f'https://git.dpdk.org/dpdk/commit/?id={self.commit_id}'

    @cached_property
    def status(self):
        """Return a status string to be displayed on the dashboard."""
        if not self.runs.exists():
            return "Waiting"

        date = self.patchset.patches.first().date
        Environment = apps.get_model('results', 'Environment')
        active_envs = Environment.objects.filter(
            Q(live_since__isnull=True) | Q(live_since__lte=date),
            successor__isnull=True)
        my_trs = {env.id: env.all_runs.filter(tarball__id=self.id).last()
                  for env in active_envs.iterator()}
        for x in my_trs.values():
            if x is None:
                return "Incomplete"
        if True in [tr.results.filter(result="FAIL").exists()
                    for tr in my_trs.values()]:
            return "Possible Regression"
        else:
            return "Pass"


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
    nic_model = models.CharField(max_length=191,
        help_text='Official model name of NIC under test')
    nic_dtscodename = models.CharField(max_length=64, blank=True,
        help_text='Codename of NIC under test as defined by DTS')
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
    date = models.DateTimeField(
        default=now, null=True,
        help_text='Date that this version of the environment was added to '
                  'the test lab')
    live_since = models.DateTimeField(
        null=True, blank=True,
        help_text='Date since which results should be included in the '
                  'overall result on the dashboard')
    hardware_description = PrivateFileField(
        null=True, blank=True,
        upload_to=partial(upload_model_path, 'hardware_description'),
        help_text='External hardware description provided by the member. '
                  'This can include setup configuration, topology, and '
                  'general hardware environment information.')

    # These are ill-defined
    # bios_settings = models.CharField(max_length=4096)
    # dts_configuration = models.CharField(max_length=4096)

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
        for m in self.measurements.iterator():
            m.clone(new_obj)
        self.contacts.update(environment=new_obj)
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

    @property
    def all_ids(self):
        """Return a list containing id of this and all predecessors."""
        ids = []
        pred = getattr(self, 'predecessor', None)
        if pred:
            ids = pred.all_ids
        ids.append(self.id)
        return ids

    @property
    def all_runs(self):
        """Return queryset containing runs of this and all predecessors."""
        TestRun = apps.get_model('results', 'TestRun')
        qs = TestRun.objects.filter(environment__id__in=self.all_ids)
        return qs


class TestCase(models.Model):
    """Test case to be run by environment."""

    name = models.CharField(
        max_length=128, help_text='Name of test case as defined in DTS')
    description_url = models.URLField(
        help_text='External URL describing test case')

    def __str__(self):
        """Return the name of the test case."""
        return self.name


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
    testcase = models.ForeignKey(
        TestCase, on_delete=models.CASCADE,
        help_text='Test case that this measurement applies to')

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

    def clone(self, environment):
        """Return a clone of this measurement for a new environment."""
        new_obj = Measurement.objects.get(pk=self.pk)

        new_obj.pk = None
        new_obj.environment = environment
        new_obj.save()
        for p in self.parameters.iterator():
            new_p = Parameter.objects.get(pk=p.pk)
            new_p.pk = None
            new_p.measurement = new_obj
            new_p.save()
        return new_obj


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
    log_output_file = models.URLField(blank=True, null=True,
        help_text='External URL of log output file')
    log_upload_file = PrivateFileField(
        upload_to=partial(upload_model_path, 'log_upload_file'),
        blank=True, null=True, help_text='Log output file for this test run')
    tarball = models.ForeignKey(Tarball, on_delete=models.CASCADE,
        related_name='runs', help_text='Tarball used for test run')
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE,
        help_text='Environment that this test run was executed on',
        related_name='runs')
    report_timestamp = models.DateTimeField(
        null=True, blank=True,
        help_text='Date and time of last e-mail report of this test run')

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

    @property
    def failures(self):
        """Return a queryset containing only failing test results."""
        return self.results.filter(result="FAIL")


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

    @property
    def result_class(self):
        """Return the background context class to be used on the dashboard."""
        class_map = {
            self.__class__.PASS: 'success',
            self.__class__.FAIL: 'danger',
            self.__class__.WARNING: 'warning',
            self.__class__.NOT_TESTED: 'secondary',
        }
        return class_map.get(self.result, 'warning')


class Subscription(models.Model):
    """Represent an e-mail subscription of a user to an environment.

    This is an intermediate model for the user-environment association. If a
    subscription object exists for a user, they will be notified of all test
    failures for the given device. Users can also request to be e-mailed for
    passing results and can select whether they will appear in the To or Cc
    field of the notification e-mails.
    """

    EMAIL_TO = 'to'
    EMAIL_CC = 'cc'
    HOW_CHOICES = (
        (EMAIL_TO, 'To'),
        (EMAIL_CC, 'Cc'),
    )

    user_profile = models.ForeignKey(
        'UserProfile', on_delete=models.CASCADE,
        help_text='The user that is being subscribed.')
    environment = models.ForeignKey(
        Environment, on_delete=models.CASCADE, related_name='contacts',
        help_text='The environment that the user is subscribing to.')
    email_success = models.NullBooleanField(
        help_text='Send e-mails when test succeeds; if null/unknown, '
        'then inherit the global setting from the environment.')
    how = models.CharField(
        max_length=4, blank=False, choices=HOW_CHOICES, default=EMAIL_TO,
        help_text='Which e-mail header to include contact in')

    def __str__(self):
        """Return a string with the username and environment."""
        return str(self.user_profile) + ': ' + str(self.environment)

    def clean(self):
        """Check that the user has permission to subscribe to the environment.

        A user has permission if he or she has view_environment permission
        for the target environment.
        """
        user = self.user_profile.user
        if not user.has_perm('results.view_environment', self.environment):
            raise ValidationError({
                'environment': 'User {name:s} does not have permission to view this environment.'.format(
                    name=user.username)
            })


class UserProfile(models.Model):
    """Define a user profile model.

    This has a one-to-one relationship with a user and is used to store
    profile settings that are not required for authentication.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='results_profile',
        help_text='The user that this profile corresponds to.')
    subscriptions = models.ManyToManyField(
        Environment, through='Subscription',
        help_text='The set of environments for which this user receives e-mail notifications.')

    def __str__(self):
        """Return the name of the user that owns this profile."""
        return self.user.username

    @property
    def display_name(self):
        """Return the user's display name."""
        return ' '.join([self.user.first_name, self.user.last_name])
