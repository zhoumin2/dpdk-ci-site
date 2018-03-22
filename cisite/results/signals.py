"""Define signals for results models."""

from .models import ContactPolicy, Environment, Measurement, TestResult, \
    TestRun
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_save
from django.dispatch import receiver
from guardian.shortcuts import assign_perm, remove_perm


def clear_environment_perms(environment):
    """Remove change permissions on a now-immutable environment."""
    # FIXME: Remove any change permissions for other groups
    remove_perm('change_environment', environment.owner, environment)
    remove_perm('delete_environment', environment.owner, environment)
    for m in environment.measurements.all().iterator():
        remove_perm('change_measurement', environment.owner, m)
        remove_perm('delete_measurement', environment.owner, m)


@receiver(post_save, sender=Group)
def save_group(sender, instance, created, **kwargs):
    """Assign group permissions on save"""
    if (created):
        permissions = ['_'.join([x, y])
                       for x in ['add', 'view', 'change', 'delete']
                       for y in ['environment', 'measurement', 'testresult',
                                 'testrun']]
        instance.permissions.set(
            [Permission.objects.get(codename=x) for x in permissions])


@receiver(post_save, sender=ContactPolicy)
def save_contactpolicy(sender, instance, **kwargs):
    """Assign contact policy permissions on save."""
    group = instance.environment.owner
    if group is None:
        return
    assign_perm('view_contactpolicy', group, instance)
    assign_perm('change_contactpolicy', group, instance)


@receiver(post_save, sender=Environment)
def save_environment(sender, instance, **kwargs):
    """Assign environment permissions on save."""
    group = instance.owner
    if group is None:
        return
    assign_perm('view_environment', group, instance)
    assign_perm('change_environment', group, instance)
    assign_perm('delete_environment', group, instance)
    if instance.predecessor is not None:
        clear_environment_perms(instance.predecessor)


@receiver(post_save, sender=Measurement)
def save_measurement(sender, instance, **kwargs):
    """Assign measurement permissions on save"""
    group = instance.owner
    if group is None:
        return
    assign_perm('view_measurement', group, instance)
    assign_perm('change_measurement', group, instance)
    assign_perm('delete_measurement', group, instance)


@receiver(post_save, sender=TestResult)
def save_test_result(sender, instance, **kwargs):
    """Assign test result permissions on save"""
    group = instance.owner
    if group is None:
        return
    assign_perm('view_testresult', group, instance)
    assign_perm('change_testresult', group, instance)
    assign_perm('delete_testresult', group, instance)


@receiver(post_save, sender=TestRun)
def save_test_run(sender, instance, **kwargs):
    """Assign test run permissions on save"""
    group = instance.owner
    if group is None:
        return
    assign_perm('view_testrun', group, instance)
    assign_perm('change_testrun', group, instance)
    assign_perm('delete_testrun', group, instance)
    clear_environment_perms(instance.environment)
