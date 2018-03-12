"""Define signals for results models."""

from .models import Environment, Measurement, TestResult, TestRun
from django.db.models.signals import post_save
from django.dispatch import receiver
from guardian.shortcuts import assign_perm


@receiver(post_save, sender=Environment)
def save_environment(sender, instance, **kwargs):
    """Assign environement permissions on save"""
    group = instance.owner
    if group is None:
        return
    assign_perm('view_environment', group, instance)


@receiver(post_save, sender=Measurement)
def save_measurement(sender, instance, **kwargs):
    """Assign measurement permissions on save"""
    group = instance.owner
    if group is None:
        return
    assign_perm('view_measurement', group, instance)


@receiver(post_save, sender=TestResult)
def save_test_result(sender, instance, **kwargs):
    """Assign test result permissions on save"""
    group = instance.owner
    if group is None:
        return
    assign_perm('view_testresult', group, instance)


@receiver(post_save, sender=TestRun)
def save_test_run(sender, instance, **kwargs):
    """Assign test run permissions on save"""
    group = instance.owner
    if group is None:
        return
    assign_perm('view_testrun', group, instance)
