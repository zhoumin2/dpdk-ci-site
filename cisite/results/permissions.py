"""Define custom permissions for results app."""

from rest_framework.permissions import BasePermission, \
    DjangoObjectPermissions, IsAdminUser, SAFE_METHODS


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


class OwnerReadCreateOnly(DjangoObjectPermissions):
    """Allow owner read and create access to objects.

    Allow access only to the owner of the object, or staff.
    """

    def has_permission(self, request, view):
        """Permission to view list in api view.

        Also only checks has_object_permission if this returns true.
        """
        return True

    def has_object_permission(self, request, view, obj):
        """Return true if permission should be granted."""
        user = request.user

        if user.is_staff or obj.owner is None:
            return True

        model_name = obj._meta.model_name

        if request.method in SAFE_METHODS:
            return user.has_perm('view_' + model_name, obj)
        elif request.method == "DELETE":
            return user.has_perm('delete_' + model_name, obj)
        else:
            return user.has_perm('change_' + model_name, obj)
