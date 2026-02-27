import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
	def create_user(self, email, password=None, **extra_fields):
		if not email:
			raise ValueError('Email is required')

		email = self.normalize_email(email)
		user = self.model(email=email, **extra_fields)
		user.set_password(password)
		user.save(using=self._db)
		return user

	def create_superuser(self, email, password=None, **extra_fields):
		extra_fields.setdefault('is_staff', True)
		extra_fields.setdefault('is_superuser', True)
		extra_fields.setdefault('is_active', True)

		if extra_fields.get('is_staff') is not True:
			raise ValueError('Superuser must have is_staff=True.')
		if extra_fields.get('is_superuser') is not True:
			raise ValueError('Superuser must have is_superuser=True.')

		return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	email = models.EmailField(unique=True)
	first_name = models.CharField(max_length=150, blank=True)
	last_name = models.CharField(max_length=150, blank=True)
	phone_number = models.CharField(max_length=20, blank=True)
	date_of_birth = models.DateField(null=True, blank=True)
	country = models.CharField(max_length=100, blank=True)
	is_active = models.BooleanField(default=True)
	is_staff = models.BooleanField(default=False)
	date_joined = models.DateTimeField(auto_now_add=True)

	objects = UserManager()

	USERNAME_FIELD = 'email'
	REQUIRED_FIELDS = []

	def has_role(self, role_name):
		return self.role_assignments.filter(role__name=role_name).exists()

	def __str__(self):
		return self.email


class Role(models.Model):
	class RoleName(models.TextChoices):
		BACKER = 'BACKER', 'Backer'
		CREATOR = 'CREATOR', 'Creator'
		ADMIN = 'ADMIN', 'Admin'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	name = models.CharField(max_length=20, choices=RoleName.choices, unique=True)
	description = models.CharField(max_length=255, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return self.name


class UserRole(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='role_assignments')
	role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_assignments')
	assigned_at = models.DateTimeField(auto_now_add=True)
	assigned_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='roles_assigned'
	)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['user', 'role'], name='unique_user_role_assignment'),
		]

	def __str__(self):
		return f'{self.user.email} -> {self.role.name}'
