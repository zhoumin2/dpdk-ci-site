"""Filter querysets for results database objects.

This file contains custom filter sets for the results application.
"""

from django_filters.rest_framework import BooleanFilter, FilterSet
from .models import Environment, PatchSet, Subscription


class EnvironmentFilter(FilterSet):
    """Supply an "active" filter for environments."""

    active = BooleanFilter(
        name='successor', label='active', lookup_expr='isnull',
        help_text='If present, limits to active (if true) or inactive (if false) patchsets.')

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


class PatchSetFilter(FilterSet):
    """Supply a "complete" filter for patch sets.

    The complete property of the PatchSet module is not actually a
    field but just a property, so it cannot be automatically filtered by
    django-filter. This class provides a custom filter to do this
    filtering via our custom query.
    """

    has_tarball = BooleanFilter(
        name='has_tarball', label='has tarball', method='has_tarball_filter',
        help_text='If present, limits to patchsets with or without a corresponding tarball built.')

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
        fields = ('apply_error', 'pw_is_active')

    def has_tarball_filter(self, queryset, name, value):
        """Filter based on the value of the complete query field."""
        assert name == 'has_tarball', 'Unexpected query field name'
        if value:
            return queryset.with_tarball()
        else:
            return queryset.without_tarball()


class SubscriptionFilter(FilterSet):
    """Supply a "mine" filter for patch sets.

    This filter create a "mine" parameter that only shows subscriptions where
    the requesting user matches the subscriptions. This is only useful for
    admins since they can see all subscriptions.
    """

    mine = BooleanFilter(
        name='mine', label='mine', method='mine_filter',
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
