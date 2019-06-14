"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Filter querysets for results database objects.

This file contains custom filter sets for the results application.
"""

from django.db.models import Q
from django_filters.rest_framework import BooleanFilter, FilterSet
from guardian.shortcuts import get_objects_for_user
from guardian.utils import get_anonymous_user
from rest_framework.filters import DjangoObjectPermissionsFilter

from .models import Environment, PatchSet, Subscription, Tarball


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
