from rest_framework.permissions import BasePermission

from users.models import Role


class IsSelfOrAdmin(BasePermission):
	def has_permission(self, request, view):
		return bool(request.user and request.user.is_authenticated)

	def has_object_permission(self, request, view, obj):
		if request.user.id == obj.id:
			return True

		if request.user.is_superuser or request.user.is_staff:
			return True

		return request.user.has_role(Role.RoleName.ADMIN)
