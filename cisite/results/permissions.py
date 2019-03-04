"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Define custom permissions for results app.
"""

from guardian.utils import get_anonymous_user
from rest_framework.permissions import BasePermission, \
    DjangoObjectPermissions, SAFE_METHODS


class IsAdminUserOrReadOnly(BasePermission):
    """Allow only admins to edit objects.

    Allow read-only access to any anonymous user, but only allow write
    permission to admins.
    """

    def has_object_permission(self, request, view, obj):
        """Return true if permission should be granted."""
        if request.method in SAFE_METHODS:
            return True

        return request.user.is_staff


class DjangoObjectPermissionsOrAnonReadOnly(DjangoObjectPermissions):
    """Base access of object from the object permissions.

    Also allow anonymous users read only access to page listing.
    (AnonymousUser still needs a separate permissions added for
    viewing objects.)
    This is similar to `DjangoModelPermissionsOrAnonReadOnly`, but
    an equivalent did not exist.

    This also makes it so that if anonymous users can view the object,
    then any logged in user chan view the object.
    """

    authenticated_users_only = False

    def has_permission(self, request, view):
        """Return if permission is granted if AnonymousUser has access."""
        if super().has_permission(request, view):
            return True
        queryset = self._queryset(view)
        perms = self.get_required_permissions(request.method, queryset.model)
        return get_anonymous_user().has_perms(perms)

    def has_object_permission(self, request, view, obj):
        """Return if permission is granted if AnonymousUser has access."""
        if super().has_object_permission(request, view, obj):
            return True
        model_cls = self._queryset(view).model
        perms = self.get_required_object_permissions(request.method, model_cls)
        return get_anonymous_user().has_perms(perms, obj)


class TestRunPermission(DjangoObjectPermissionsOrAnonReadOnly):
    """Allows specific actions to be run outside of the object permissions."""

    def has_object_permission(self, request, view, obj):
        """Return true if permission should be granted."""
        if view.action == 'rerun':
            user = request.user
            env = obj.environment
            if user.groups.all().filter(name=env.owner).exists() or \
                    user.is_staff:
                return True

        return super().has_object_permission(request, view, obj)


class PatchSetPermission(IsAdminUserOrReadOnly):
    """Allows specific actions to be run outside of the object permissions."""

    def has_object_permission(self, request, view, obj):
        """Return true if permission should be granted."""
        if view.action == 'rebuild':
            return request.user.is_authenticated

        return super().has_object_permission(request, view, obj)


class UserProfileObjectPermission(DjangoObjectPermissions):
    """Allow user to access models attached to their user profile.

    Allow access only to the owner of the object, or staff.
    Note: This is only for an individual object, not a view set!
    """

    def has_object_permission(self, request, view, obj):
        """Return true if permission should be granted."""
        user = request.user
        return user.is_staff or obj.user_profile.user == user
