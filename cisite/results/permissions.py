"""Define custom permissions for results app."""

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


class OwnerReadCreateOnly(DjangoObjectPermissions):
    """Allow owner read and create access to objects.

    Allow access only to the owner of the object, or staff.
    """

    perms_map = {
        'GET': ['%(app_label)s.view_%(model_name)s'],
        'OPTIONS': ['%(app_label)s.view_%(model_name)s'],
        'HEAD': ['%(app_label)s.view_%(model_name)s'],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }

    def has_permission(self, request, view):
        """Permission to view list in api view.

        Also only checks has_object_permission if this returns true.
        """
        return request.user.is_staff or super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        """Return true if permission should be granted."""
        user = request.user

        if user.is_staff or obj.owner is None:
            return True

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
