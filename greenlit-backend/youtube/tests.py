from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from youtube.services import YouTubeAPIError


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
