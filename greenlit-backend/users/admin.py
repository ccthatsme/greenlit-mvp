from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Role, User, UserRole


@admin.register(User)
class UserAdmin(BaseUserAdmin):
	ordering = ('email',)
	list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active')
	search_fields = ('email', 'first_name', 'last_name')

	fieldsets = (
		(None, {'fields': ('email', 'password')}),
		('Personal info', {'fields': ('first_name', 'last_name', 'phone_number', 'date_of_birth', 'country')}),
		('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
		('Important dates', {'fields': ('last_login', 'date_joined')}),
	)

	add_fieldsets = (
		(
			None,
			{
				'classes': ('wide',),
				'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active'),
			},
		),
	)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
	list_display = ('name', 'description', 'created_at')
	search_fields = ('name',)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
	list_display = ('user', 'role', 'assigned_at', 'assigned_by')
	search_fields = ('user__email', 'role__name')
	list_filter = ('role__name',)
