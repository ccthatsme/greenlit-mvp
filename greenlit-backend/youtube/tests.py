from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from youtube.models import CreatorChannel
from youtube.services import (
	YouTubeAPIError,
	YouTubeConnectError,
	complete_creator_onboarding,
	connect_creator_channel,
	get_creator_onboarding_summary,
	start_creator_onboarding,
)
from users.models import Role
from users.services import assign_role_to_user


class PublicChannelProbeApiTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.url = reverse('youtube-public-channel-probe')

	@patch('youtube.views.fetch_public_channel_probe')
	def test_channel_probe_success(self, mock_probe):
		mock_probe.return_value = {
			'channel_id': 'UC12345',
			'title': 'Test Channel',
			'description': 'Demo channel',
			'custom_url': '@testchannel',
			'published_at': '2022-01-01T00:00:00Z',
			'thumbnail_url': 'https://img.youtube.com/example.jpg',
			'subscriber_count': 1200,
			'view_count': 87000,
			'video_count': 42,
			'recent_videos': [
				{
					'video_id': 'video-1',
					'title': 'First video',
					'published_at': '2025-01-01T00:00:00Z',
					'thumbnail_url': 'https://img.youtube.com/video-1.jpg',
				}
			],
		}

		response = self.client.get(self.url, {'channel_id': 'UC12345'})

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['channel_id'], 'UC12345')
		self.assertEqual(response.data['subscriber_count'], 1200)
		mock_probe.assert_called_once_with(channel_id='UC12345')

	def test_channel_probe_requires_channel_id(self):
		response = self.client.get(self.url)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('channel_id', response.data)

	@patch('youtube.views.fetch_public_channel_probe')
	def test_channel_probe_handles_service_error(self, mock_probe):
		mock_probe.side_effect = YouTubeAPIError('Channel not found for the provided channel_id.')

		response = self.client.get(self.url, {'channel_id': 'unknown'})

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data['detail'], 'Channel not found for the provided channel_id.')


class CreatorChannelModelTests(TestCase):
	def setUp(self):
		self.User = get_user_model()

	def test_create_creator_channel_links_user_and_channel(self):
		user = self.User.objects.create_user(email='creator@example.com', password='StrongPass123!')
		creator_channel = CreatorChannel.objects.create(
			user=user,
			youtube_channel_id='UC_CREATOR_1',
			channel_title='Creator Channel',
		)

		self.assertEqual(creator_channel.user, user)
		self.assertEqual(creator_channel.youtube_channel_id, 'UC_CREATOR_1')
		self.assertEqual(creator_channel.sync_status, CreatorChannel.SyncStatus.PENDING)
		self.assertEqual(creator_channel.onboarding_status, CreatorChannel.OnboardingStatus.STARTED)
		self.assertIsNotNone(creator_channel.onboarding_started_at)

	def test_user_cannot_have_more_than_one_creator_channel(self):
		user = self.User.objects.create_user(email='creator2@example.com', password='StrongPass123!')
		CreatorChannel.objects.create(user=user, youtube_channel_id='UC_CREATOR_2')

		with self.assertRaises(IntegrityError):
			CreatorChannel.objects.create(user=user, youtube_channel_id='UC_CREATOR_3')

	def test_youtube_channel_id_is_unique_across_users(self):
		user_one = self.User.objects.create_user(email='creator3@example.com', password='StrongPass123!')
		user_two = self.User.objects.create_user(email='creator4@example.com', password='StrongPass123!')

		CreatorChannel.objects.create(user=user_one, youtube_channel_id='UC_SHARED')

		with self.assertRaises(IntegrityError):
			CreatorChannel.objects.create(user=user_two, youtube_channel_id='UC_SHARED')


class CreatorChannelServiceTests(TestCase):
	def setUp(self):
		self.User = get_user_model()
		self.user = self.User.objects.create_user(email='svc-creator@example.com', password='StrongPass123!')
		self.backer_user = self.User.objects.create_user(email='svc-backer@example.com', password='StrongPass123!')
		assign_role_to_user(self.user, Role.RoleName.CREATOR)
		assign_role_to_user(self.backer_user, Role.RoleName.BACKER)

	def test_start_creator_onboarding_creates_channel_anchor_for_creator(self):
		creator_channel = start_creator_onboarding(self.user)

		self.assertEqual(creator_channel.user, self.user)
		self.assertIsNone(creator_channel.youtube_channel_id)
		self.assertEqual(creator_channel.onboarding_status, CreatorChannel.OnboardingStatus.STARTED)
		self.assertIsNotNone(creator_channel.onboarding_started_at)

	def test_start_creator_onboarding_rejects_non_creator(self):
		with self.assertRaisesMessage(YouTubeConnectError, 'Only creator users can start creator onboarding.'):
			start_creator_onboarding(self.backer_user)

	def test_start_creator_onboarding_is_idempotent(self):
		first = start_creator_onboarding(self.user)
		second = start_creator_onboarding(self.user)

		self.assertEqual(first.id, second.id)
		self.assertEqual(CreatorChannel.objects.filter(user=self.user).count(), 1)

	@patch('youtube.services.fetch_public_channel_probe')
	def test_connect_creator_channel_creates_channel(self, mock_probe):
		mock_probe.return_value = {
			'channel_id': 'UC_SERVICE_1',
			'title': 'Service Creator Channel',
			'custom_url': '@servicecreator',
		}

		creator_channel = connect_creator_channel(self.user, 'UC_SERVICE_1')

		self.assertEqual(creator_channel.youtube_channel_id, 'UC_SERVICE_1')
		self.assertEqual(creator_channel.channel_title, 'Service Creator Channel')
		self.assertEqual(creator_channel.channel_handle, '@servicecreator')
		self.assertEqual(creator_channel.sync_status, CreatorChannel.SyncStatus.SUCCESS)
		self.assertEqual(creator_channel.onboarding_status, CreatorChannel.OnboardingStatus.CHANNEL_CONNECTED)
		self.assertIsNotNone(creator_channel.channel_connected_at)

	def test_complete_creator_onboarding_marks_status_complete(self):
		creator_channel = CreatorChannel.objects.create(
			user=self.user,
			youtube_channel_id='UC_COMPLETE_1',
			onboarding_status=CreatorChannel.OnboardingStatus.CHANNEL_CONNECTED,
		)

		completed = complete_creator_onboarding(self.user)

		self.assertEqual(completed.id, creator_channel.id)
		self.assertEqual(completed.onboarding_status, CreatorChannel.OnboardingStatus.COMPLETE)
		self.assertIsNotNone(completed.onboarding_completed_at)

	def test_complete_creator_onboarding_is_idempotent(self):
		creator_channel = CreatorChannel.objects.create(
			user=self.user,
			youtube_channel_id='UC_COMPLETE_2',
			onboarding_status=CreatorChannel.OnboardingStatus.COMPLETE,
		)
		initial_timestamp = creator_channel.onboarding_completed_at

		first = complete_creator_onboarding(self.user)
		second = complete_creator_onboarding(self.user)

		self.assertEqual(first.id, second.id)
		self.assertEqual(second.onboarding_status, CreatorChannel.OnboardingStatus.COMPLETE)
		self.assertEqual(second.onboarding_completed_at, initial_timestamp)

	def test_complete_creator_onboarding_rejects_non_creator(self):
		with self.assertRaisesMessage(YouTubeConnectError, 'Only creator users can complete creator onboarding.'):
			complete_creator_onboarding(self.backer_user)

	def test_complete_creator_onboarding_requires_creator_channel(self):
		with self.assertRaisesMessage(YouTubeConnectError, 'Creator channel does not exist. Start onboarding first.'):
			complete_creator_onboarding(self.user)

	def test_complete_creator_onboarding_requires_connected_channel_id(self):
		CreatorChannel.objects.create(
			user=self.user,
			youtube_channel_id=None,
			onboarding_status=CreatorChannel.OnboardingStatus.STARTED,
		)

		with self.assertRaisesMessage(
			YouTubeConnectError,
			'Creator channel must be connected before onboarding can be completed.',
		):
			complete_creator_onboarding(self.user)

	def test_get_creator_onboarding_summary_rejects_non_creator(self):
		with self.assertRaisesMessage(YouTubeConnectError, 'Only creator users can access creator onboarding summary.'):
			get_creator_onboarding_summary(self.backer_user)

	def test_get_creator_onboarding_summary_returns_defaults_when_channel_missing(self):
		summary = get_creator_onboarding_summary(self.user)

		self.assertEqual(summary['youtube_channel_id'], '')
		self.assertEqual(summary['channel_title'], '')
		self.assertEqual(summary['channel_handle'], '')
		self.assertEqual(summary['sync_status'], CreatorChannel.SyncStatus.PENDING)
		self.assertEqual(summary['onboarding_status'], CreatorChannel.OnboardingStatus.STARTED)
		self.assertIsNone(summary['last_synced_at'])
		self.assertIsNone(summary['onboarding_started_at'])
		self.assertIsNone(summary['channel_connected_at'])
		self.assertIsNone(summary['onboarding_completed_at'])

	def test_get_creator_onboarding_summary_returns_existing_channel_values(self):
		creator_channel = CreatorChannel.objects.create(
			user=self.user,
			youtube_channel_id='UC_SUMMARY_1',
			channel_title='Summary Channel',
			channel_handle='@summary',
			sync_status=CreatorChannel.SyncStatus.SUCCESS,
			onboarding_status=CreatorChannel.OnboardingStatus.CHANNEL_CONNECTED,
		)

		summary = get_creator_onboarding_summary(self.user)

		self.assertEqual(summary['youtube_channel_id'], 'UC_SUMMARY_1')
		self.assertEqual(summary['channel_title'], 'Summary Channel')
		self.assertEqual(summary['channel_handle'], '@summary')
		self.assertEqual(summary['sync_status'], CreatorChannel.SyncStatus.SUCCESS)
		self.assertEqual(summary['onboarding_status'], CreatorChannel.OnboardingStatus.CHANNEL_CONNECTED)
		self.assertEqual(summary['onboarding_started_at'], creator_channel.onboarding_started_at)

	def test_get_creator_onboarding_summary_normalizes_null_channel_id_to_empty_string(self):
		CreatorChannel.objects.create(
			user=self.user,
			youtube_channel_id=None,
			onboarding_status=CreatorChannel.OnboardingStatus.STARTED,
		)

		summary = get_creator_onboarding_summary(self.user)

		self.assertEqual(summary['youtube_channel_id'], '')


class ConnectCreatorChannelApiTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.User = get_user_model()
		self.connect_url = reverse('youtube-connect-channel')
		self.creator_user = self.User.objects.create_user(email='creator-api@example.com', password='StrongPass123!')
		self.backer_user = self.User.objects.create_user(email='backer-api@example.com', password='StrongPass123!')
		assign_role_to_user(self.creator_user, Role.RoleName.CREATOR)
		assign_role_to_user(self.backer_user, Role.RoleName.BACKER)

	@patch('youtube.views.connect_creator_channel')
	def test_creator_can_connect_channel(self, mock_connect):
		mock_connect.return_value = CreatorChannel(
			user=self.creator_user,
			youtube_channel_id='UC_API_1',
			channel_title='API Creator Channel',
			channel_handle='@apicreator',
			sync_status=CreatorChannel.SyncStatus.SUCCESS,
		)

		self.client.force_authenticate(user=self.creator_user)
		response = self.client.post(self.connect_url, {'channel_id': 'UC_API_1'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['youtube_channel_id'], 'UC_API_1')
		mock_connect.assert_called_once_with(user=self.creator_user, channel_id='UC_API_1')

	def test_backer_cannot_connect_channel(self):
		self.client.force_authenticate(user=self.backer_user)
		response = self.client.post(self.connect_url, {'channel_id': 'UC_API_2'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_unauthenticated_user_cannot_connect_channel(self):
		response = self.client.post(self.connect_url, {'channel_id': 'UC_API_3'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	@patch('youtube.views.connect_creator_channel')
	def test_connect_returns_400_on_service_error(self, mock_connect):
		mock_connect.side_effect = YouTubeAPIError('Channel not found for the provided channel_id.')

		self.client.force_authenticate(user=self.creator_user)
		response = self.client.post(self.connect_url, {'channel_id': 'UNKNOWN'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data['detail'], 'Channel not found for the provided channel_id.')


class CompleteCreatorOnboardingApiTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.User = get_user_model()
		self.complete_url = reverse('youtube-complete-onboarding')
		self.creator_user = self.User.objects.create_user(email='complete-creator@example.com', password='StrongPass123!')
		self.backer_user = self.User.objects.create_user(email='complete-backer@example.com', password='StrongPass123!')
		assign_role_to_user(self.creator_user, Role.RoleName.CREATOR)
		assign_role_to_user(self.backer_user, Role.RoleName.BACKER)

	def test_creator_can_complete_onboarding_after_channel_connected(self):
		CreatorChannel.objects.create(
			user=self.creator_user,
			youtube_channel_id='UC_ONBOARD_1',
			onboarding_status=CreatorChannel.OnboardingStatus.CHANNEL_CONNECTED,
		)

		self.client.force_authenticate(user=self.creator_user)
		response = self.client.post(self.complete_url, {}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['onboarding_status'], CreatorChannel.OnboardingStatus.COMPLETE)
		self.assertIsNotNone(response.data['onboarding_completed_at'])

	def test_non_creator_cannot_complete_onboarding(self):
		self.client.force_authenticate(user=self.backer_user)
		response = self.client.post(self.complete_url, {}, format='json')

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_completion_returns_400_when_channel_not_connected(self):
		CreatorChannel.objects.create(
			user=self.creator_user,
			youtube_channel_id=None,
			onboarding_status=CreatorChannel.OnboardingStatus.STARTED,
		)

		self.client.force_authenticate(user=self.creator_user)
		response = self.client.post(self.complete_url, {}, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(
			response.data['detail'],
			'Creator channel must be connected before onboarding can be completed.',
		)


class CreatorOnboardingMeApiTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.User = get_user_model()
		self.me_url = reverse('youtube-onboarding-me')
		self.creator_user = self.User.objects.create_user(email='me-creator@example.com', password='StrongPass123!')
		self.backer_user = self.User.objects.create_user(email='me-backer@example.com', password='StrongPass123!')
		assign_role_to_user(self.creator_user, Role.RoleName.CREATOR)
		assign_role_to_user(self.backer_user, Role.RoleName.BACKER)

	def test_creator_with_connected_channel_gets_summary(self):
		CreatorChannel.objects.create(
			user=self.creator_user,
			youtube_channel_id='UC_ME_1',
			channel_title='Me Channel',
			channel_handle='@mechannel',
			sync_status=CreatorChannel.SyncStatus.SUCCESS,
			onboarding_status=CreatorChannel.OnboardingStatus.CHANNEL_CONNECTED,
		)

		self.client.force_authenticate(user=self.creator_user)
		response = self.client.get(self.me_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['youtube_channel_id'], 'UC_ME_1')
		self.assertEqual(response.data['channel_title'], 'Me Channel')
		self.assertEqual(response.data['onboarding_status'], CreatorChannel.OnboardingStatus.CHANNEL_CONNECTED)

	def test_creator_without_channel_gets_default_summary(self):
		self.client.force_authenticate(user=self.creator_user)
		response = self.client.get(self.me_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['youtube_channel_id'], '')
		self.assertEqual(response.data['sync_status'], CreatorChannel.SyncStatus.PENDING)
		self.assertEqual(response.data['onboarding_status'], CreatorChannel.OnboardingStatus.STARTED)
		self.assertIsNone(response.data['onboarding_started_at'])

	def test_non_creator_cannot_access_onboarding_me(self):
		self.client.force_authenticate(user=self.backer_user)
		response = self.client.get(self.me_url)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_unauthenticated_user_cannot_access_onboarding_me(self):
		response = self.client.get(self.me_url)

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
