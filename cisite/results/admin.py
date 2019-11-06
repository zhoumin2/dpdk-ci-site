"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Register admin interface for DPDK CI site results models.
"""

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.forms.models import ModelForm
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse, path
from django.utils.html import format_html
from .models import Branch, ContactPolicy, Environment, Measurement, \
    Parameter, PatchSet, Tarball, TestResult, TestRun, \
    Subscription, UserProfile, TestCase, Vendor
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import get_objects_for_user

from .forms import SetPublicForm, SetPrivateForm, SetPublicTestCaseForm, SetPrivateTestCaseForm


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


class TestResultInline(admin.TabularInline):
    """Inline admin form for test results."""

    extra = 0
    show_change_link = True
    model = TestResult


class SubscriptionInline(admin.TabularInline):
    """Present inline admin form for user environment-specific settings."""

    extra = 0
    show_change_link = True
    model = Subscription

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Restrict the environments that can be supplied for the user.

        Note that even if the user manages to get by this check and submit a
        request to the admin interface to add a user to an environment he
        doesn't have access to, the model's clean() function would reject
        adding it.
        """
        # Solution taken from https://stackoverflow.com/a/4236159
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'environment':
            print(dir(request))
            if request._obj_ is not None and \
                    isinstance(request._obj_, UserProfile):
                field.queryset = get_objects_for_user(
                    request._obj_.user, 'results.view_environment',
                    accept_global_perms=False)
            else:
                field.queryset = field.queryset.none()

        return field


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Present user profile on form."""

    inlines = [SubscriptionInline]

    def get_form(self, request, obj=None, **kwargs):
        """Save object being used before calling superclass function."""
        request._obj_ = obj
        return super().get_form(request, obj, **kwargs)


@admin.register(ContactPolicy)
class ContactPolicyAdmin(GuardedModelAdmin):
    """Add hidden contact policy screen to admin interface."""

    readonly_fields = ('environment',)

    def has_module_permission(self, request):
        """Do not show contact policy module on admin interface index."""
        return False


@admin.register(Environment)
class EnvironmentAdmin(GuardedModelAdmin):
    """Define environment module in admin interface."""

    inlines = [ContactPolicyInline, MeasurementInline]
    list_display = ('__str__', 'contact_policy_link', 'environment_actions')
    list_select_related = ('contact_policy',)
    readonly_fields = ('predecessor', 'environment_actions')

    def contact_policy_link(self, obj):
        """Return a link to edit the contact policy for this environment."""
        return format_html('<a href={0:s}>{1:s}</a>',
                           reverse('admin:results_contactpolicy_change',
                                   args=(obj.contact_policy.id,)),
                           obj.contact_policy)

    def get_urls(self):
        """Add custom urls to the admin page."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<environment_id>/set_public/',
                self.admin_site.admin_view(self.process_set_public),
                name='environment-public',
            ),
            path(
                '<environment_id>/set_private/',
                self.admin_site.admin_view(self.process_set_private),
                name='environment-private',
            ),
        ]
        return custom_urls + urls

    def environment_actions(self, obj):
        """Create custom environment actions."""
        return format_html(
            '<a class="button" href="{}">Set Public</a>&nbsp;'
            '<a class="button" href="{}">Set Private</a>',
            reverse('admin:environment-public', args=(obj.pk,)),
            reverse('admin:environment-private', args=(obj.pk,)),
        )

    def process_set_public(self, request, environment_id, *args, **kwargs):
        """Set environment public action call."""
        return self.process_action(request, environment_id, SetPublicForm,
                                   'Set Public')

    def process_set_private(self, request, environment_id, *args, **kwargs):
        """Set environment private action call."""
        return self.process_action(request, environment_id, SetPrivateForm,
                                   'Set Private')

    def process_action(self, request, environment_id, action_form, action_title):
        """Mostly generic method for custom actions."""
        environment = self.get_object(request, environment_id)

        if request.method != 'POST':
            form = action_form()
        else:
            form = action_form(request.POST)
            if form.is_valid():
                form.save(environment, request.user)
                self.message_user(request, 'Success')
                url = reverse(
                    'admin:results_environment_change',
                    args=(environment.pk,),
                )
                return HttpResponseRedirect(url)

        context = self.admin_site.each_context(request)
        context['opts'] = self.model._meta
        context['form'] = form
        context['title'] = action_title
        context['modified'] = environment.get_related()

        return TemplateResponse(
            request,
            'admin/environment/environment_action.html',
            context,
        )


@admin.register(TestCase)
class TestCaseAdmin(GuardedModelAdmin):
    """Define test case module in admin interface."""

    list_display = ('__str__', 'test_case_actions')
    readonly_fields = ('test_case_actions',)

    def get_urls(self):
        """Add custom urls to the admin page."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<test_case_id>/set_public/',
                self.admin_site.admin_view(self.process_set_public),
                name='testcase-public',
            ),
            path(
                '<test_case_id>/set_private/',
                self.admin_site.admin_view(self.process_set_private),
                name='testcase-private',
            ),
        ]
        return custom_urls + urls

    def test_case_actions(self, obj):
        """Create custom test case actions."""
        return format_html(
            '<a class="button" href="{}">Set Public</a>&nbsp;'
            '<a class="button" href="{}">Set Private</a>',
            reverse('admin:testcase-public', args=(obj.pk,)),
            reverse('admin:testcase-private', args=(obj.pk,)),
        )

    def process_set_public(self, request, test_case_id, *args, **kwargs):
        """Set test case public action call."""
        return self.process_action(
            request, test_case_id, SetPublicTestCaseForm, 'Set Public')

    def process_set_private(self, request, test_case_id, *args, **kwargs):
        """Set test case private action call."""
        return self.process_action(
            request, test_case_id, SetPrivateTestCaseForm, 'Set Private')

    def process_action(self, request, test_case_id, action_form, action_title):
        """Mostly generic method for custom actions."""
        test_case = self.get_object(request, test_case_id)

        if request.method != 'POST':
            form = action_form()
        else:
            form = action_form(request.POST)
            if form.is_valid():
                form.save(test_case, request.user)
                self.message_user(request, 'Success')
                url = reverse(
                    'admin:results_testcase_change',
                    args=(test_case.pk,),
                )
                return HttpResponseRedirect(url)

        context = self.admin_site.each_context(request)
        context['opts'] = self.model._meta
        context['form'] = form
        context['title'] = action_title

        return TemplateResponse(
            request,
            'admin/test_run/test_run_action.html',
            context,
        )


@admin.register(TestRun)
class TestRunAdmin(GuardedModelAdmin):
    """Define TestRun module in admin interface."""

    inlines = [TestResultInline]
    readonly_fields = ('tarball',)
    list_select_related = ('tarball',)


@admin.register(Tarball)
class TarballAdmin(GuardedModelAdmin):
    """Define Tarball module in admin interface."""

    readonly_fields = ('patchset',)


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    """Define a mostly read-only LogEntry module in admin interface."""
    readonly_fields = ('content_type', 'user', 'action_time', 'object_id',
                       'object_repr', 'action_flag', 'change_message')


admin.site.register(Branch)
admin.site.register(Measurement, GuardedModelAdmin, inlines=[ParameterInline])
admin.site.register(PatchSet)
admin.site.register(Vendor, GuardedModelAdmin)
admin.site.register(Subscription)
