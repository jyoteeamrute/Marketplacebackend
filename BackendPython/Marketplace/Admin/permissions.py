from rest_framework.permissions import BasePermission

class IsAdminAccount(BasePermission):
    """
    Custom permission to allow only AdminUser accounts.
    """

    def has_permission(self, request, view):
        return hasattr(request.user, 'role') and request.user.role.name == 'administrator' or request.user.role.name == 'Administrator'
