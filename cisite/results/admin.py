"""Register admin interface for DPDK CI site results models."""
from django.contrib import admin
from .models import ContactPolicy, Environment, Measurement, Parameter, \
    Patch, PatchSet, Tarball, TestResult, TestRun
from guardian.admin import GuardedModelAdmin


class ContactPolicyInline(admin.StackedInline):
    """Inline admin form for environment contact policy."""

    can_delete = False
    model = ContactPolicy
    verbose_name = 'contact policy'
    verbose_name_plural = verbose_name


class ParameterInline(admin.TabularInline):
    """Inline admin form for measurement parameters."""

    extra = 0
    show_change_link = True
    model = Parameter


class MeasurementInline(admin.TabularInline):
    """Inline admin form for measurements."""

    extra = 0
    show_change_link = True
    model = Measurement


class PatchInline(admin.StackedInline):
    """Inline admin form for patches."""

    extra = 0
    show_change_link = True
    model = Patch


class TestResultInline(admin.TabularInline):
    """Inline admin form for test results."""

    extra = 0
    show_change_link = True
    model = TestResult


admin.site.register(Environment, GuardedModelAdmin,
                    inlines=[ContactPolicyInline, MeasurementInline])
admin.site.register(Measurement, GuardedModelAdmin, inlines=[ParameterInline])
admin.site.register(PatchSet, inlines=[PatchInline])
admin.site.register(Tarball)
admin.site.register(TestRun, GuardedModelAdmin, inlines=[TestResultInline])
