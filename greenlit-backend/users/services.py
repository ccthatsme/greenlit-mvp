from users.models import Role, UserRole


def assign_role_to_user(user, role_name, assigned_by=None):
	role = Role.objects.get(name=role_name)
	user_role, _ = UserRole.objects.get_or_create(
		user=user,
		role=role,
		defaults={'assigned_by': assigned_by},
	)

	return user_role


def remove_role_from_user(user, role_name):
	deleted_count, _ = UserRole.objects.filter(
		user=user,
		role__name=role_name,
	).delete()

	return deleted_count > 0
