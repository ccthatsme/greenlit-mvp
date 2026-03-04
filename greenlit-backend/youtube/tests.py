from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from youtube.models import CreatorChannel
from youtube.services import YouTubeAPIError, connect_creator_channel
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
