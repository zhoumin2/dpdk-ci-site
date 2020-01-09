"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Filter querysets for results database objects.

This file contains custom filter sets for the results application.
"""
from django.contrib.auth.models import User
from django.db.models import Q
from django_filters.rest_framework import BooleanFilter, FilterSet, CharFilter
from guardian.shortcuts import get_objects_for_user
from guardian.utils import get_anonymous_user
from rest_framework.filters import DjangoObjectPermissionsFilter

from .models import Environment, PatchSet, Subscription, Tarball, TestRun


class EnvironmentFilter(FilterSet):
    """Supply an "active" filter for environments."""

    active = BooleanFilter(
        field_name='successor', label='active', lookup_expr='isnull',
        help_text='If present, limits to active (if true) or inactive (if false) environments.')

    mine = BooleanFilter(
        field_name='mine', label='mine', method='mine_filter',
        help_text='If present, limits to only your environments.')

    class Meta:
        """Set up model association."""

        model = Environment
        fields = ()

    def active_filter(self, queryset, name, value):
        """Filter based on whether this environment is active."""
        assert name == 'active', 'Unexpected query field name'
        if value is None:
            return queryset
        else:
            return queryset.filter(successor__isnull=value)

    def mine_filter(self, queryset, name, value):
        """Filter based on the value of the mine query field."""
        assert name == 'mine', 'Unexpected query field name'
        mine = get_objects_for_user(self.request.user, 'view_environment',
                                    queryset, accept_global_perms=False)
        if value:
            return mine
        else:
            return queryset.exclude(id__in=mine)


class PatchSetFilter(FilterSet):
    """Supply a "complete" filter for patch sets.

    The complete property of the PatchSet module is not actually a
    field but just a property, so it cannot be automatically filtered by
    django-filter. This class provides a custom filter to do this
    filtering via our custom query.
    """

    has_tarball = BooleanFilter(
        field_name='has_tarball', label='has tarball', method='has_tarball_filter',
        help_text='If present, limits to patchsets with or without a corresponding tarball built.')

    has_error = BooleanFilter(
        field_name='has_error', label='has error', method='has_error_filter',
        help_text='If present, limits to patchsets with apply errors or build errors.')

    # Django-filters does not allow isnull checks on integer filters.
    # This is a double negative since Django does not a have a isnotnull, and
    # I'd rather not add extra code to remove the double negative.
    # This also exists since we did not use the patchworks series when the original
    # database was created (since their REST API did not exist at the time), thus
    # older patchset don't have a series_id.
    without_series = BooleanFilter(
        field_name='series_id', lookup_expr='isnull',
        help_text='Patchsets without series attached to them.')

    class Meta:
        """Set up class fields automatically."""

        model = PatchSet
        fields = ('apply_error', 'build_error', 'pw_is_active', 'series_id')

    def has_tarball_filter(self, queryset, name, value):
        """Filter based on the value of the complete query field."""
        assert name == 'has_tarball', 'Unexpected query field name'
        if value:
            return queryset.with_tarball()
        else:
            return queryset.without_tarball()

    def has_error_filter(self, queryset, name, value):
        """Filter based on the value of the complete query field."""
        assert name == 'has_error', 'Unexpected query field name'
        if value:
            return queryset.filter(Q(apply_error=True) | Q(build_error=True))
        else:
            return queryset.filter(apply_error=False, build_error=False)


class SubscriptionFilter(FilterSet):
    """Supply a "mine" filter for patch sets.

    This filter create a "mine" parameter that only shows subscriptions where
    the requesting user matches the subscriptions. This is only useful for
    admins since they can see all subscriptions.
    """

    mine = BooleanFilter(
        field_name='mine', label='mine', method='mine_filter',
        help_text='If present, limits to only your subscriptions.')

    class Meta:
        """Set up class fields automatically."""
        model = Subscription
        fields = ()

    def mine_filter(self, queryset, name, value):
        """Filter based on the value of the mine query field."""
        assert name == 'mine', 'Unexpected query field name'
        if value:
            return queryset.filter(
                user_profile__exact=self.request.user.results_profile)
        else:
            return queryset.exclude(
                user_profile__exact=self.request.user.results_profile)


class DjangoObjectPermissionsFilterWithAnonPerms(DjangoObjectPermissionsFilter):
    """Allow access to any logged in user if AnonymousUser has permission."""

    def filter_queryset(self, request, queryset, view):
        """Combine filter of super() and AnonymousUser."""
        model_cls = queryset.model
        kwargs = {
            'app_label': model_cls._meta.app_label,
            'model_name': model_cls._meta.model_name
        }
        permission = self.perm_format % kwargs
        extra = {'accept_global_perms': False}
        return super().filter_queryset(request, queryset, view) | \
            get_objects_for_user(get_anonymous_user(), permission, queryset,
                                 **extra)


class TarballFilter(FilterSet):
    has_patchset = BooleanFilter(
        field_name='has_patchset', label='has patchset', method='has_patchset_filter',
        help_text='If present, limits to tarballs with or without a corresponding patchset.')

    class Meta:
        """Set up class fields automatically."""

        model = Tarball
        fields = ('job_name', 'build_id', 'branch', 'commit_id', 'patchset')

    def has_patchset_filter(self, queryset, name, value):
        """Filter based on the value of the complete query field."""
        assert name == 'has_patchset', 'Unexpected query field name'
        if value:
            return queryset.with_patchset()
        else:
            return queryset.without_patchset()


class UserFilter(FilterSet):
    """Supply a "managed" filter for users.

    This filter create a "managed" parameter that only shows users
    that the primary contact can manage.
    """

    managed = BooleanFilter(
        field_name='managed', label='managed', method='managed_filter',
        help_text='If present, limits to users you can manage.')

    class Meta:
        """Set up class fields automatically."""
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')

    def managed_filter(self, queryset, name, value):
        """Filter based on the value of the managed query field."""
        assert name == 'managed', 'Unexpected query field name'
        user = self.request.user
        groups = []
        for group in user.groups.all():
            if user.has_perm('manage_group', group.results_vendor):
                groups.append(group)

        if value:
            # Exclude requesting user from the list. So there isn't a situation
            # where they can remove themselves from their own group while still
            # being a primary contact. That should be handled separately.
            return queryset.filter(groups__in=groups).exclude(username=user) \
                .distinct()
        else:
            return queryset.exclude(groups__in=groups)


class TestRunFilter(FilterSet):
    """
    This filter class is utilized in finding the baseline for a combined
    environment, test case, and branch.
    The baseline typically does not have a patch set associated with it.
    The baseline should never be the same commit as the currently testing
    commit.
    """

    has_patchset = BooleanFilter(
        field_name='has_patchset', label='has patchset',
        method='has_patchset_filter',
        help_text='If present, limits to test runs with or without a '
                  'corresponding patchset of the tarball used in the test '
                  'run.')
    does_not_have_commit = CharFilter(
        field_name='does_not_have_commit', label='does not have commit',
        method='does_not_have_commit_filter',
        help_text='If present, limits to test runs that DO NOT have the '
                  'specific commit of the tarball used in the test '
                  'run.')

    class Meta:
        """Set up class fields automatically."""

        model = TestRun
        fields = ('environment', 'tarball__branch', 'testcase')

    def has_patchset_filter(self, queryset, name, value):
        """Filter based on the value of the complete query field."""
        assert name == 'has_patchset', 'Unexpected query field name'
        if value:
            return queryset.exclude(tarball__patchset=None)
        else:
            return queryset.filter(tarball__patchset=None)

    def does_not_have_commit_filter(self, queryset, name, value):
        """Filter based on the value of the complete query field."""
        assert name == 'does_not_have_commit', 'Unexpected query field name'
        if value:
            return queryset.exclude(tarball__commit_id=value)
        else:
            return queryset
