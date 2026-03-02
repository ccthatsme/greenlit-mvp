from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib import admin
from django.db import IntegrityError
from django.urls import reverse
from uuid import UUID
from rest_framework import status
from rest_framework.test import APIClient

from users.admin import RoleAdmin, UserAdmin, UserRoleAdmin
from users.models import Role, UserRole
from users.services import assign_role_to_user, remove_role_from_user


class UserModelTests(TestCase):
	def setUp(self):
		self.User = get_user_model()

	def test_create_user_with_email_success(self):
		user = self.User.objects.create_user(
			email='TestUser@Example.COM',
			password='StrongPass123!'
		)

		self.assertEqual(user.email, 'TestUser@example.com')
		self.assertTrue(user.check_password('StrongPass123!'))
		self.assertTrue(user.is_active)
		self.assertFalse(user.is_staff)
		self.assertIsInstance(user.id, UUID)

	def test_create_user_without_email_raises_error(self):
		with self.assertRaises(ValueError):
			self.User.objects.create_user(email='', password='StrongPass123!')

	def test_create_superuser_has_required_flags(self):
		admin_user = self.User.objects.create_superuser(
			email='admin@example.com',
			password='AdminPass123!'
		)

		self.assertTrue(admin_user.is_staff)
		self.assertTrue(admin_user.is_superuser)
		self.assertTrue(admin_user.is_active)

	def test_create_superuser_with_invalid_staff_flag_raises_error(self):
		with self.assertRaises(ValueError):
			self.User.objects.create_superuser(
				email='badadmin@example.com',
				password='AdminPass123!',
				is_staff=False,
			)

	def test_string_representation_returns_email(self):
		user = self.User.objects.create_user(
			email='person@example.com',
			password='StrongPass123!'
		)

		self.assertEqual(str(user), 'person@example.com')


class UserAdminTests(TestCase):
	def setUp(self):
		self.User = get_user_model()

	def test_user_model_is_registered_in_admin_site(self):
		self.assertIn(self.User, admin.site._registry)

	def test_user_model_uses_custom_user_admin_class(self):
		registered_admin = admin.site._registry[self.User]

		self.assertIsInstance(registered_admin, UserAdmin)
		self.assertIn('email', registered_admin.list_display)
		self.assertEqual(registered_admin.ordering, ('email',))


class RoleModelTests(TestCase):
	def setUp(self):
		self.User = get_user_model()
		self.backer_role, _ = Role.objects.get_or_create(name=Role.RoleName.BACKER)
		self.creator_role, _ = Role.objects.get_or_create(name=Role.RoleName.CREATOR)

	def test_role_string_representation(self):
		self.assertEqual(str(self.backer_role), 'BACKER')

	def test_user_can_have_multiple_roles(self):
		user = self.User.objects.create_user(email='multi@example.com', password='StrongPass123!')
		UserRole.objects.create(user=user, role=self.backer_role)
		UserRole.objects.create(user=user, role=self.creator_role)

		role_names = set(user.role_assignments.values_list('role__name', flat=True))
		self.assertEqual(role_names, {'BACKER', 'CREATOR'})

	def test_duplicate_user_role_assignment_is_blocked(self):
		user = self.User.objects.create_user(email='dup@example.com', password='StrongPass123!')
		UserRole.objects.create(user=user, role=self.backer_role)

		with self.assertRaises(IntegrityError):
			UserRole.objects.create(user=user, role=self.backer_role)

	def test_user_has_role_helper(self):
		user = self.User.objects.create_user(email='roles@example.com', password='StrongPass123!')
		UserRole.objects.create(user=user, role=self.creator_role)

		self.assertTrue(user.has_role('CREATOR'))
		self.assertFalse(user.has_role('ADMIN'))


class RoleAdminTests(TestCase):
	def test_role_model_is_registered_in_admin_site(self):
		self.assertIn(Role, admin.site._registry)

	def test_user_role_model_is_registered_in_admin_site(self):
		self.assertIn(UserRole, admin.site._registry)

	def test_role_admin_classes_are_used(self):
		self.assertIsInstance(admin.site._registry[Role], RoleAdmin)
		self.assertIsInstance(admin.site._registry[UserRole], UserRoleAdmin)


class RoleServiceTests(TestCase):
	def setUp(self):
		self.User = get_user_model()
		self.user = self.User.objects.create_user(email='service@example.com', password='StrongPass123!')
		self.admin_user = self.User.objects.create_superuser(email='platform-admin@example.com', password='AdminPass123!')
		self.backer_role, _ = Role.objects.get_or_create(name=Role.RoleName.BACKER)

	def test_assign_role_to_user_creates_assignment(self):
		assignment = assign_role_to_user(self.user, Role.RoleName.BACKER, assigned_by=self.admin_user)

		self.assertEqual(assignment.user, self.user)
		self.assertEqual(assignment.role.name, Role.RoleName.BACKER)
		self.assertEqual(assignment.assigned_by, self.admin_user)
		self.assertTrue(self.user.has_role(Role.RoleName.BACKER))

	def test_assign_role_to_user_is_idempotent(self):
		first = assign_role_to_user(self.user, Role.RoleName.BACKER)
		second = assign_role_to_user(self.user, Role.RoleName.BACKER)

		self.assertEqual(first.id, second.id)
		self.assertEqual(UserRole.objects.filter(user=self.user, role=self.backer_role).count(), 1)

	def test_remove_role_from_user_returns_true_when_deleted(self):
		assign_role_to_user(self.user, Role.RoleName.BACKER)

		removed = remove_role_from_user(self.user, Role.RoleName.BACKER)

		self.assertTrue(removed)
		self.assertFalse(self.user.has_role(Role.RoleName.BACKER))

	def test_remove_role_from_user_returns_false_when_missing(self):
		removed = remove_role_from_user(self.user, Role.RoleName.BACKER)

		self.assertFalse(removed)


class SignupApiTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.signup_url = reverse('user-signup')

	def test_signup_creates_user_with_selected_backer_role(self):
		payload = {
			'email': 'newbacker@example.com',
			'password': 'StrongPass123!',
			'password_confirm': 'StrongPass123!',
			'first_name': 'Ari',
			'last_name': 'Lane',
			'selected_role': Role.RoleName.BACKER,
		}

		response = self.client.post(self.signup_url, payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		user = get_user_model().objects.get(email='newbacker@example.com')
		self.assertTrue(user.has_role(Role.RoleName.BACKER))
		self.assertEqual(response.data['email'], 'newbacker@example.com')
		self.assertEqual(set(response.data['roles']), {Role.RoleName.BACKER})

	def test_signup_creates_user_with_selected_creator_role(self):
		payload = {
			'email': 'creator@example.com',
			'password': 'StrongPass123!',
			'password_confirm': 'StrongPass123!',
			'selected_role': Role.RoleName.CREATOR,
		}

		response = self.client.post(self.signup_url, payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		user = get_user_model().objects.get(email='creator@example.com')
		self.assertTrue(user.has_role(Role.RoleName.CREATOR))

	def test_signup_rejects_admin_role_for_public_registration(self):
		payload = {
			'email': 'admin-try@example.com',
			'password': 'StrongPass123!',
			'password_confirm': 'StrongPass123!',
			'selected_role': Role.RoleName.ADMIN,
		}

		response = self.client.post(self.signup_url, payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('selected_role', response.data)

	def test_signup_rejects_password_mismatch(self):
		payload = {
			'email': 'mismatch@example.com',
			'password': 'StrongPass123!',
			'password_confirm': 'WrongPass123!',
			'selected_role': Role.RoleName.BACKER,
		}

		response = self.client.post(self.signup_url, payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('password_confirm', response.data)


class DeleteUserApiTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.User = get_user_model()
		self.target_user = self.User.objects.create_user(email='target@example.com', password='StrongPass123!')
		self.other_user = self.User.objects.create_user(email='other@example.com', password='StrongPass123!')
		self.admin_role_user = self.User.objects.create_user(email='appadmin@example.com', password='StrongPass123!')
		assign_role_to_user(self.admin_role_user, Role.RoleName.ADMIN)

	def _delete_url(self, user):
		return reverse('user-delete', kwargs={'user_id': user.id})

	def test_self_delete_succeeds(self):
		self.client.force_authenticate(user=self.target_user)

		response = self.client.delete(self._delete_url(self.target_user))

		self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
		self.assertFalse(self.User.objects.filter(id=self.target_user.id).exists())

	def test_admin_role_user_can_delete_another_user(self):
		self.client.force_authenticate(user=self.admin_role_user)

		response = self.client.delete(self._delete_url(self.target_user))

		self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
		self.assertFalse(self.User.objects.filter(id=self.target_user.id).exists())

	def test_non_admin_cannot_delete_another_user(self):
		self.client.force_authenticate(user=self.other_user)

		response = self.client.delete(self._delete_url(self.target_user))

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertTrue(self.User.objects.filter(id=self.target_user.id).exists())

	def test_unauthenticated_delete_is_denied(self):
		response = self.client.delete(self._delete_url(self.target_user))

		self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
