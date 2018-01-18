"""Define custom permissions for results app."""

from rest_framework.permissions import BasePermission, IsAdminUser, \
    SAFE_METHODS


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


class OwnerReadOnly(BasePermission):
    """Allow owner read only access to objects.

    Allow access only to the owner of the object, or staff.
    """

    def has_object_permission(self, request, view, obj):
        """Return true if permission should be granted."""
        user = request.user
        return user.is_staff or (obj.owner is not None and obj.owner == user)
