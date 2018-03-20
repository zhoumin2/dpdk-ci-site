"""Register admin interface for DPDK CI site results models."""
from django.contrib import admin
from django.forms.models import ModelForm
from .models import ContactPolicy, Environment, Measurement, Parameter, \
    Patch, PatchSet, Tarball, TestResult, TestRun
from guardian.admin import GuardedModelAdmin


class AlwaysChangedModelForm(ModelForm):
    """Display a form which always saves even if not changed.

    This is used for the contact policy inline form, since we always want to
    save one if we haven't created one yet.

    The code is taken from: https://stackoverflow.com/a/36755438
    """

    def has_changed(self, *args, **kwargs):
        """Return true if the form has changed.

        This override always returns true if an object hasn't been created yet,
        since we always want to create an object the first time.
        """
        if self.instance.pk is None:
            return True
        return super(AlwaysChangedModelForm, self).has_changed(*args, **kwargs)


class ContactPolicyInline(admin.StackedInline):
    """Inline admin form for environment contact policy."""

    can_delete = False
    model = ContactPolicy
    verbose_name = 'contact policy'
    verbose_name_plural = verbose_name
    form = AlwaysChangedModelForm


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
