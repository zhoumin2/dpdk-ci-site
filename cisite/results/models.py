"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Model data for patchsets, environments, and test results.
"""

import json
import os
import uuid
from abc import abstractmethod

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth.models import Group, User
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from functools import partial
from guardian.shortcuts import assign_perm, remove_perm
from guardian.utils import get_anonymous_user
from private_storage.fields import PrivateFileField


def get_admin_group():
    """Return a group of admin users."""
    return Group.objects.get_or_create(name='admins')[0]


def upload_model_path(field, instance, filename):
    """Upload files based on their model name, uuid, and field.

    NOTE: the `partial` method needs to be used to pass in the field. It is
        also assumed that a "uuid" field exists in the table!

    This is utilized for private storage. urls.upload_model_path will also
    have to be updated if this gets changed.
    """
    return f'{instance.__class__._meta.verbose_name_plural.replace(" ", "_")}/' \
           f'{instance.uuid.hex}/{field}/{filename}'


def upload_model_path_test_run(field, instance, filename):
    """Upload files for a test run. Filename is only used for the extension.

    See `upload_model_path` for more information.
    """
    time = instance.timestamp
    # chop to 12 to keep aligned with linux kernel conventions
    commit_hash = instance.tarball.commit_id[:12]
    # in case a base test run is made (like from master) which does not
    # contain a patchset
    ps_id = ''
    if instance.tarball.patchset:
        ps_id = f'{instance.tarball.patchset.id}_'
    nic_name = instance.environment.nic_dtscodename
    # since nic_dtscodename is optional, base the name off the last word in the
    # nic_model (since the nic_model is a friendly name of the nic)
    if not nic_name:
        nic_name = instance.environment.nic_model.split(" ")[-1]
    friendly_datetime = time.strftime('%Y-%m-%d_%H-%M-%S')
    ext = os.path.splitext(filename)[1]
    return f'{instance.__class__._meta.verbose_name_plural.replace(" ", "_")}/' \
           f'{instance.uuid.hex}/{field}/{time.year}/{time.month}/' \
           f'dpdk_{commit_hash}_{ps_id}{friendly_datetime}_{nic_name}{ext}'


class CommitURLMixin:
    """Create a commit_url property for a model.

    The model requires a commit_id string and a branch foreign key.
    """

    @property
    def commit_url(self):
        if not self.commit_id or not self.branch:
            return ''
        # Formatted for cgit
        return f'{self.branch.web_url}/commit/?id={self.commit_id}'


class PatchSetQuerySet(models.QuerySet):
    """Provide queries specific for patchsets."""

    def without_tarball(self):
        return self.filter(tarballs=None)

    def with_tarball(self):
        return self.exclude(tarballs=None)


class TarballQuerySet(models.QuerySet):
    """Provide queries specific for tarballs."""

    def without_patchset(self):
        return self.filter(patchset=None)

    def with_patchset(self):
        return self.exclude(patchset=None)


class StatusMixin:
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
            'tooltip': 'The patch series could not be applied',
        },
        'Build Error': {
            'class': 'warning',
            'tooltip': 'The patch series could not be built',
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
        'Not Applicable': {
            'class': 'secondary',
            'tooltip': 'The patch series is not active in Patchwork or is '
                       'not required to be tested',
        },
        'Indeterminate': {
            'class': 'primary',
            'tooltip': 'A result could not be determined and could mean '
                       'that the test did not run to completion',
        },
    }

    @abstractmethod
    def status(self):
        """Return a string status"""
        pass

    def status_class(self):
        """Return the background context class to be used on the dashboard."""
        return self.statuses.get(self.status, dict()).get('class', 'warning')

    def status_tooltip(self):
        """Return the status tooltip to be used on the dashboard."""
        return self.statuses.get(self.status, dict()).get('tooltip',
                                                          self.status)


class PatchSet(models.Model, CommitURLMixin, StatusMixin):
    """Model a single patchset."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_public = models.BooleanField(default=True,
        help_text='Was the patch set posted to a public mailing list?')
    apply_error = models.BooleanField(default=False,
        help_text='Was an error encountered trying to apply the patch?')
    build_error = models.BooleanField(default=False,
        help_text='Was an error encountered trying to build the patch?')
    series_id = models.PositiveIntegerField(unique=True, null=True,
        blank=True, help_text='The patchworks series ID.')
    completed_timestamp = models.DateTimeField(
        null=True, blank=True,
        help_text='When this patchset was completed')
    # This can be removed once patchworks updates to 2.1 (DPDKLAB-393)
    pw_is_active = models.BooleanField('Is active?', default=True,
        help_text="True if still considered active in Patchwork")
    build_log = models.FileField(
        null=True, blank=True, max_length=255,
        upload_to=partial(upload_model_path, 'build_log'),
        help_text='Build log of applying and building the patch.')
    branch = models.ForeignKey(
        'Branch', on_delete=models.SET_NULL, related_name='patchsets',
        null=True, blank=True,
        help_text='The branch that the patch set was applied to. The branch '
                  'in the tarball should be used instead of this. This should '
                  'be used when no tarball exists.')
    commit_id = models.CharField(
        max_length=40, blank=True,
        help_text='The most recent git commit id that the patch set was '
                  'applied to. The commit id in the tarball should be used '
                  'instead of this. This should be used when no tarball '
                  'exists.')

    objects = models.Manager.from_queryset(PatchSetQuerySet)()

    def __str__(self):
        """Return string representation of patchset record."""
        return f'{super().__str__()} (Series: {self.series_id}) ' \
               f'(Completed: {self.completed_timestamp})'

    @property
    def time_to_last_test(self):
        """Return the time from submission to last test run."""
        return (self.last_tarball.runs.last().timestamp -
                self.completed_timestamp)

    @cached_property
    def status(self):
        """Return the status string to be displayed on the dashboard."""
        if self.apply_error:
            return "Apply Error"
        elif self.build_error:
            return "Build Error"
        elif not self.tarballs.exists() and not self.pw_is_active:
            return "Not Applicable"
        elif not self.tarballs.exists():
            return "Pending"
        else:
            return self.last_tarball.status

    @cached_property
    def has_error(self):
        """"Returns whether the patchset had an apply error or build error."""
        return self.apply_error or self.build_error

    @cached_property
    def last_tarball(self):
        return self.tarballs.last()

    @property
    def passed(self):
        """Return the number of passed environments."""
        if self.has_error or not self.tarballs.exists():
            return 0
        return self.last_tarball.passed

    @property
    def failed(self):
        """Return the number of failed environments."""
        if self.has_error or not self.tarballs.exists():
            return 0
        return self.last_tarball.failed

    @property
    def incomplete(self):
        """Return the number of incomplete environments."""
        if self.has_error or not self.tarballs.exists():
            return 0
        return self.last_tarball.incomplete

    def get_absolute_url(self):
        """Return url to REST API for use with admin interface and rebuilds."""
        return reverse('patchset-detail', args=(self.id,))


class Branch(models.Model):
    """Model a DPDK repository branch."""

    name = models.CharField(
        max_length=64, blank=False, unique=True,
        help_text='Name of the branch')
    repository_url = models.URLField(
        max_length=1024, help_text='Upstream URL of the repository')
    web_url = models.URLField(
        max_length=1024, blank=True,
        help_text='Upstream URL of the repository that can be browsed')
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

    def get_absolute_url(self):
        """Return url to REST API for use with admin interface and rebuilds."""
        return reverse('branch-detail', args=(self.id,))


class Tarball(models.Model, CommitURLMixin, StatusMixin):
    """Model a tarball constructed by a patchset."""

    branch = models.ForeignKey(
        'Branch', on_delete=models.SET_NULL, related_name='tarballs',
        null=True, blank=True,
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

    objects = models.Manager.from_queryset(TarballQuerySet)()

    def __str__(self):
        """Return string representation of tarball record."""
        return self.tarball_url

    @cached_property
    def status(self):
        """Return a status string to be displayed on the dashboard."""
        if not self.runs.exists():
            return "Waiting"

        if self.incomplete > 0:
            return "Incomplete"

        if self.failed > 0:
            return "Possible Regression"

        if self.indeterminate > 0:
            return "Indeterminate"

        return "Pass"

    def get_absolute_url(self):
        """Return url to REST API for use with admin interface and reruns."""
        return reverse('tarball-detail', args=(self.id,))

    @cached_property
    def get_pass_fail_incomplete(self):
        """Return a dict of passed, failed, and incomplete test runs.

        For the Incomplete status, we consider only environments created since
        the tarball was created (falling back to the patchset submission date
        for old tarballs which didn't have a date tied to them). Environments
        with a null creation date are considered to have always been active.

        For the Possible Regression status, we consider only active
        environments that were live at the time the test run was completed
        (note that the reference time is *not* the same as for Incomplete).
        If the live_since value is null, then we also ignore failures because
        we presume that the environment is not yet live. Test results with
        no test runs are also considered a failure, as something may have gone
        wrong.
        """
        count = {'passed': 0, 'failed': 0, 'incomplete': 0, 'indeterminate': 0}

        if not self.runs.exists():
            return count

        date = getattr(self, 'date', None)
        if not date and self.patchset:
            date = self.patchset.completed_timestamp

        query = Q(date__isnull=True)
        if date:
            query |= Q(date__lte=date)

        Environment = apps.get_model('results', 'Environment')
        active_envs = Environment.objects.filter(
            query, successor__isnull=True, live_since__isnull=False)

        for env in active_envs.iterator():
            tr_qs = env.all_runs.filter(tarball__id=self.id)
            if not tr_qs.exists():
                count['incomplete'] += 1
                continue
            tr = tr_qs.last()

            if env.live_since <= tr.timestamp:
                if tr.results.filter(result="FAIL").exists():
                    count['failed'] += 1
                elif tr.results.filter(result="PASS").exists():
                    count['passed'] += 1
                else:
                    count['indeterminate'] += 1
        return count

    @cached_property
    def passed(self):
        """Return the number of passed environments."""
        return self.get_pass_fail_incomplete['passed']

    @cached_property
    def failed(self):
        """Return the number of failed environments."""
        return self.get_pass_fail_incomplete['failed']

    @cached_property
    def incomplete(self):
        """Return the number of incomplete environments."""
        return self.get_pass_fail_incomplete['incomplete']

    @cached_property
    def indeterminate(self):
        """Return the number of indeterminate environments."""
        return self.get_pass_fail_incomplete['indeterminate']


def validate_contact_list(value):
    xs = json.loads(value)
    for x in xs:
        if 'email' not in x:
            raise ValidationError('Patch contact does not have e-mail address')
        elif 'how' not in x or x['how'].lower() not in ('to', 'cc', 'bcc'):
            raise ValidationError('Patch contact "how" not present or '
                                  'valid; must be "to", "cc", or "bcc"')
        validate_email(x['email'])


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

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
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
        null=True, blank=True, max_length=255,
        upload_to=partial(upload_model_path, 'hardware_description'),
        help_text='External hardware description provided by the member. '
                  'This can include setup configuration, topology, and '
                  'general hardware environment information.')
    pipeline = models.CharField(
        max_length=255, null=True, blank=True,
        help_text='The pipeline name used for running tests. This is combined'
                  'with the pipeline name of the test case.')

    # These are ill-defined
    # bios_settings = models.CharField(max_length=4096)
    # dts_configuration = models.CharField(max_length=4096)

    class Meta:
        """Specify how to set up environments."""

    def clone(self):
        """Create and return an inactive copy of this object.

        This copy will be linked to the original object by the predecessor
        and successor attributes.
        """
        new_obj = Environment.objects.get(pk=self.pk)

        new_obj.pk = None
        new_obj.uuid = uuid.uuid4()
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
        if get_anonymous_user().has_perm('view_environment', self):
            is_public = 'Public'
        else:
            is_public = 'Private'
        return f'{self._meta.object_name} {self.id}: {self.inventory_id} ' \
               f'(v{generation}) {is_public}'

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

    def get_absolute_url(self):
        """Return url to REST API for use with admin interface."""
        return reverse('environment-detail', args=(self.id,))

    def get_related(self):
        """Get all related objects and itself into a 2d list.

        This is used when previewing what will become public from the
        admin interface.
        """
        measurements = self.measurements.all()
        runs = self.runs.all()
        results = []
        for run in runs:
            results += run.results.all()

        ret = [[self]]
        if measurements:
            ret += [measurements]
        if runs:
            ret += [runs]
        if results:
            ret += [results]
        if self.predecessor:
            ret += self.predecessor.get_related()
        return ret

    def set_public(self):
        """Set AnonymousUser view permission to environment and related."""
        anon = get_anonymous_user()
        assign_perm('view_environment', anon, self)
        for measurement in self.measurements.all():
            assign_perm('view_measurement', anon, measurement)
        for run in self.runs.all():
            # Although TestResult is serialized in the API, this is required
            # for syncing the public database.
            for result in run.results.all():
                assign_perm('view_testresult', anon, result)
            assign_perm('view_testrun', anon, run)
        # Required when syncing the public database, or else it will throw an
        # error that it can't find the foreign keys.
        if self.predecessor:
            self.predecessor.set_public()

    def set_private(self):
        """Set AnonymousUser view permission to environment and related."""
        anon = get_anonymous_user()
        remove_perm('view_environment', anon, self)
        for measurement in self.measurements.all():
            remove_perm('view_measurement', anon, measurement)
        for run in self.runs.all():
            for result in run.results.all():
                remove_perm('view_testresult', anon, result)
            remove_perm('view_testrun', anon, run)
        if self.predecessor:
            self.predecessor.set_private()


class TestCase(models.Model):
    """Test case to be run by environment."""

    name = models.CharField(
        max_length=128, help_text='Name of test case as defined in DTS')
    description_url = models.URLField(
        help_text='External URL describing test case')
    pipeline = models.CharField(
        max_length=255, null=True, blank=True,
        help_text='The pipeline name used for running tests. This is combined'
                  'with the pipeline name of the environment.')

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

    def __str__(self):
        """Return a string describing the measurement."""
        if get_anonymous_user().has_perm('view_measurement', self):
            is_public = 'Public'
        else:
            is_public = 'Private'
        return f'{self._meta.object_name} {self.id}: {self.name} ' \
               f'({self.unit}) {is_public}'

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

    def get_absolute_url(self):
        """Return url to REST API for use with admin interface."""
        return reverse('measurement-detail', args=(self.id,))


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


class TestRun(models.Model, CommitURLMixin):
    """Model a test run of a patch set."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    timestamp = models.DateTimeField('time run',
        help_text='Date and time that test was run')
    log_output_file = models.URLField(blank=True, null=True,
        help_text='External URL of log output file')
    log_upload_file = PrivateFileField(
        upload_to=partial(upload_model_path_test_run, 'log_upload_file'),
        blank=True, null=True, max_length=255,
        help_text='Log output file for this test run')
    tarball = models.ForeignKey(Tarball, on_delete=models.CASCADE,
        related_name='runs', help_text='Tarball used for test run')
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE,
        help_text='Environment that this test run was executed on',
        related_name='runs')
    report_timestamp = models.DateTimeField(
        null=True, blank=True,
        help_text='Date and time of last e-mail report of this test run')
    branch = models.ForeignKey(
        'Branch', on_delete=models.SET_NULL, related_name='runs',
        null=True, blank=True,
        help_text='The branch of the baseline used')
    # this can be different from the tarball commit_id if rerunning old tests
    # where the baseline has changed
    commit_id = models.CharField('git commit hash', max_length=40, blank=True,
                                 help_text='The commit id of the baseline used')
    testcase = models.ForeignKey(
        TestCase, on_delete=models.CASCADE, null=True, blank=True,
        help_text='Test case that this test run applies to')

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

    def __str__(self):
        """Return the patchset and timestamp as a string."""
        if get_anonymous_user().has_perm('view_testrun', self):
            is_public = 'Public'
        else:
            is_public = 'Private'
        return f'{self._meta.object_name} {self.id}: ' \
               f'{self.tarball.tarball_url} {self.timestamp} {is_public}'

    @property
    def failures(self):
        """Return a queryset containing only failing test results."""
        return self.results.filter(result="FAIL")

    def get_absolute_url(self):
        """Return url to REST API for use with admin interface."""
        return reverse('testrun-detail', args=(self.id,))


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

    def __str__(self):
        """Return a string briefly describing the test result.

        Return a string like "throughput PASS -0.1 Gbps" for a
        test throughput measuring 4.9 Gbps against an expected
        result of 5.0 Gbps +/- 100 Mbps.
        """
        if get_anonymous_user().has_perm('view_testresult', self):
            is_public = 'Public'
        else:
            is_public = 'Private'
        return f'{self._meta.object_name} {self.id}: ' \
               f'{self.measurement.name} {self.result} {self.difference} ' \
               f'{self.measurement.unit} {is_public}'

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
