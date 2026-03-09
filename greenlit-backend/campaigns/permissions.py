from rest_framework.permissions import BasePermission

from users.models import Role


class IsCreatorUser(BasePermission):
	def has_permission(self, request, view):
		return bool(
			request.user
			and request.user.is_authenticated
			and request.user.has_role(Role.RoleName.CREATOR)
		)

