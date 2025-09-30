from rest_framework.permissions import BasePermission
from api.models import User

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        # Check if user is authenticated and has admin role or is staff
        return request.user and request.user.is_authenticated and (
            request.user.role == 'admin' or request.user.is_staff
        )