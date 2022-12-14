"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Define signals for results models.
"""

from .models import ContactPolicy, Environment, Measurement, TestResult, \
    TestRun, Subscription, UserProfile, Vendor
from django.contrib.auth.models import Group, Permission, User
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from guardian.shortcuts import assign_perm, remove_perm
from guardian.utils import get_anonymous_user


def clear_environment_perms(environment):
    """Remove change permissions on a now-immutable environment."""
    # FIXME: Remove any change permissions for other groups
    remove_perm('change_environment', environment.owner, environment)
    remove_perm('delete_environment', environment.owner, environment)
    for m in environment.measurements.all().iterator():
        remove_perm('change_measurement', environment.owner, m)
        remove_perm('delete_measurement', environment.owner, m)


def set_anon_permissions(permission, environment, instance):
    """Set anonymous permissions if environment can be viewed anonymously."""
    anon = get_anonymous_user()
    if anon.has_perm('view_environment', environment):
        assign_perm(permission, anon, instance)
        return True
    return False


@receiver(post_save, sender=Group)
def save_group(sender, instance, created, **kwargs):
    """Assign group permissions on save"""
    if created and not kwargs.get('raw', False):
        permissions = ['_'.join([x, y])
                       for x in ['add', 'view', 'change', 'delete']
                       for y in ['environment', 'measurement', 'testresult',
                                 'testrun']]
        # some permissions don't have a 'view' permission
        permissions += ['_'.join([x, y])
                        for x in ['add', 'change', 'delete']
                        for y in ['subscription']]
        instance.permissions.set(
            [Permission.objects.get(codename=x) for x in permissions])
        Vendor.objects.create(group=instance)


def remove_subscriptions(user, group):
    """Remove subscription for all environments owned by the given group."""
    envs = group.environment_set.all()
    for sub in Subscription.objects.filter(environment__pk__in=envs):
        sub.delete()


@receiver(m2m_changed, sender=User.groups.through)
def group_membership_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    """Handle changes in user group membership."""
    if action in 'post_remove':
        if reverse:
            group = instance
            for user in User.objects.filter(pk__in=pk_set):
                remove_subscriptions(user, group)
        else:
            user = instance
            for group in Group.objects.filter(pk__in=pk_set):
                remove_subscriptions(user, group)
    elif action == 'pre_clear':
        if reverse:
            group = instance
            for user in group.user_set.all():
                remove_subscriptions(user, group)
        else:
            user = instance
            for group in user.groups.all():
                remove_subscriptions(user, group)


@receiver(post_save, sender=User)
def post_save_user(sender, instance, created, **kwargs):
    """Assign default profile on save new user."""
    if created and not kwargs.get('raw', False):
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=ContactPolicy)
def save_contactpolicy(sender, instance, **kwargs):
    """Assign contact policy permissions on save."""
    group = instance.environment.owner
    if group is None or kwargs.get('raw', False):
        return
    assign_perm('view_contactpolicy', group, instance)
    assign_perm('change_contactpolicy', group, instance)


@receiver(post_save, sender=Environment)
def save_environment(sender, instance, **kwargs):
    """Assign environment permissions on save."""
    group = instance.owner
    if group is None or kwargs.get('raw', False):
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
    if group is None or kwargs.get('raw', False):
        return
    assign_perm('view_measurement', group, instance)
    assign_perm('change_measurement', group, instance)
    assign_perm('delete_measurement', group, instance)

    set_anon_permissions('view_measurement', instance.environment, instance)


@receiver(post_save, sender=TestResult)
def save_test_result(sender, instance, **kwargs):
    """Assign test result permissions on save"""
    group = instance.owner
    if group is None or kwargs.get('raw', False):
        return
    assign_perm('view_testresult', group, instance)
    assign_perm('change_testresult', group, instance)
    assign_perm('delete_testresult', group, instance)

    set_anon_permissions('view_testresult', instance.run.environment, instance)


@receiver(post_save, sender=TestRun)
def save_test_run(sender, instance, **kwargs):
    """Assign test run permissions on save"""
    group = instance.owner
    if group is None or kwargs.get('raw', False):
        return
    assign_perm('view_testrun', group, instance)
    assign_perm('change_testrun', group, instance)
    assign_perm('delete_testrun', group, instance)

    was_set = set_anon_permissions('view_testrun', instance.environment, instance)

    # allow test run download to anon users
    if was_set and instance.testcase:
        anon = get_anonymous_user()
        if anon.has_perm('download_artifacts', instance.testcase):
            assign_perm('download_artifacts', anon, instance)

    clear_environment_perms(instance.environment)
