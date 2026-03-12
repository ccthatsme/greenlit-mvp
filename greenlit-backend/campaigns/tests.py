from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from campaigns.models import Campaign
from campaigns.serializers import CampaignSummarySerializer, CreateCampaignSerializer
from campaigns.services import (
	CampaignConflictError,
	CampaignOnboardingError,
	CampaignPermissionError,
	CampaignValidationError,
	assert_creator_can_create_campaign,
	create_campaign,
)
from users.models import Role
from users.services import assign_role_to_user
from youtube.models import CreatorChannel


class CampaignModelTests(TestCase):
	def setUp(self):
		self.User = get_user_model()
		self.creator = self.User.objects.create_user(
			email='campaign-creator@example.com',
			password='StrongPass123!',
		)

	def test_create_campaign_sets_mvp_defaults(self):
		deadline = timezone.now() + timezone.timedelta(days=30)

		campaign = Campaign.objects.create(
			creator=self.creator,
			title='Fund My Next Video',
			summary='Help fund production for my next YouTube video.',
			funding_goal_cents=500000,
			deadline_at=deadline,
		)

		self.assertEqual(campaign.status, Campaign.Status.DRAFT)
		self.assertEqual(campaign.currency, 'USD')
		self.assertEqual(campaign.amount_pledged_cents, 0)
		self.assertIsNone(campaign.funded_at)
		self.assertIsNotNone(campaign.created_at)
		self.assertIsNotNone(campaign.updated_at)

	def test_campaign_can_record_funded_timestamp(self):
		deadline = timezone.now() + timezone.timedelta(days=14)
		funded_time = timezone.now()

		campaign = Campaign.objects.create(
			creator=self.creator,
			title='Documentary Episode 1',
			summary='Funding post-production and sound mix.',
			funding_goal_cents=250000,
			deadline_at=deadline,
			status=Campaign.Status.FUNDED,
			funded_at=funded_time,
		)

		self.assertEqual(campaign.status, Campaign.Status.FUNDED)
		self.assertEqual(campaign.funded_at, funded_time)

	def test_campaign_str_includes_title_and_status(self):
		deadline = timezone.now() + timezone.timedelta(days=7)
		campaign = Campaign.objects.create(
			creator=self.creator,
			title='Mini-Series Pilot',
			summary='Covering set design and filming costs.',
			funding_goal_cents=100000,
			deadline_at=deadline,
		)

		self.assertEqual(str(campaign), 'Mini-Series Pilot (draft)')


class CampaignServiceTests(TestCase):
	def setUp(self):
		self.User = get_user_model()
		self.creator_user = self.User.objects.create_user(
			email='svc-campaign-creator@example.com',
			password='StrongPass123!',
		)
		self.backer_user = self.User.objects.create_user(
			email='svc-campaign-backer@example.com',
			password='StrongPass123!',
		)
		assign_role_to_user(self.creator_user, Role.RoleName.CREATOR)
		assign_role_to_user(self.backer_user, Role.RoleName.BACKER)

	def test_assert_creator_can_create_campaign_rejects_non_creator(self):
		with self.assertRaisesMessage(CampaignPermissionError, 'Only creator users can create campaigns.'):
			assert_creator_can_create_campaign(self.backer_user)

	def test_assert_creator_can_create_campaign_requires_connected_channel(self):
		with self.assertRaisesMessage(
			CampaignOnboardingError,
			'You must connect your YouTube channel before creating a campaign.',
		):
			assert_creator_can_create_campaign(self.creator_user)

	def test_assert_creator_can_create_campaign_rejects_started_onboarding(self):
		CreatorChannel.objects.create(
			user=self.creator_user,
			onboarding_status=CreatorChannel.OnboardingStatus.STARTED,
		)

		with self.assertRaisesMessage(
			CampaignOnboardingError,
			'You must complete channel connection before creating a campaign.',
		):
			assert_creator_can_create_campaign(self.creator_user)

	def test_create_campaign_success_for_connected_creator(self):
		CreatorChannel.objects.create(
			user=self.creator_user,
			onboarding_status=CreatorChannel.OnboardingStatus.CHANNEL_CONNECTED,
		)
		deadline = timezone.now() + timezone.timedelta(days=21)

		campaign = create_campaign(
			self.creator_user,
			title='  New Video Drop  ',
			summary='  Help fund this production.  ',
			funding_goal_cents=750000,
			deadline_at=deadline,
		)

		self.assertEqual(campaign.title, 'New Video Drop')
		self.assertEqual(campaign.summary, 'Help fund this production.')
		self.assertEqual(campaign.status, Campaign.Status.DRAFT)
		self.assertEqual(campaign.currency, 'USD')

	def test_create_campaign_rejects_invalid_goal(self):
		CreatorChannel.objects.create(
			user=self.creator_user,
			onboarding_status=CreatorChannel.OnboardingStatus.CHANNEL_CONNECTED,
		)
		deadline = timezone.now() + timezone.timedelta(days=10)

		with self.assertRaisesMessage(
			CampaignValidationError,
			'Funding goal must be a positive integer amount in cents.',
		):
			create_campaign(
				self.creator_user,
				title='Bad Goal',
				summary='Invalid goal test',
				funding_goal_cents=0,
				deadline_at=deadline,
			)

	def test_create_campaign_rejects_past_deadline(self):
		CreatorChannel.objects.create(
			user=self.creator_user,
			onboarding_status=CreatorChannel.OnboardingStatus.COMPLETE,
		)
		past_deadline = timezone.now() - timezone.timedelta(days=1)

		with self.assertRaisesMessage(
			CampaignValidationError,
			'Campaign deadline must be in the future.',
		):
			create_campaign(
				self.creator_user,
				title='Past Deadline',
				summary='Deadline validation',
				funding_goal_cents=120000,
				deadline_at=past_deadline,
			)

	def test_create_campaign_rejects_when_active_campaign_exists(self):
		CreatorChannel.objects.create(
			user=self.creator_user,
			onboarding_status=CreatorChannel.OnboardingStatus.COMPLETE,
		)
		Campaign.objects.create(
			creator=self.creator_user,
			title='Existing Active Campaign',
			summary='Already active campaign',
			funding_goal_cents=300000,
			deadline_at=timezone.now() + timezone.timedelta(days=40),
			status=Campaign.Status.ACTIVE,
		)

		with self.assertRaisesMessage(CampaignConflictError, 'You already have an active campaign.'):
			create_campaign(
				self.creator_user,
				title='Second Campaign',
				summary='This should be blocked',
				funding_goal_cents=200000,
				deadline_at=timezone.now() + timezone.timedelta(days=30),
			)


class CampaignSerializerTests(TestCase):
	def test_create_campaign_serializer_valid_payload(self):
		payload = {
			'title': 'Launch My Next Episode',
			'summary': 'Funding editing, sound design, and graphics.',
			'funding_goal_cents': 450000,
			'deadline_at': (timezone.now() + timezone.timedelta(days=20)).isoformat(),
		}

		serializer = CreateCampaignSerializer(data=payload)

		self.assertTrue(serializer.is_valid(), serializer.errors)

	def test_create_campaign_serializer_rejects_invalid_goal(self):
		payload = {
			'title': 'Invalid Goal Campaign',
			'summary': 'Invalid campaign payload test.',
			'funding_goal_cents': 0,
			'deadline_at': (timezone.now() + timezone.timedelta(days=10)).isoformat(),
		}

		serializer = CreateCampaignSerializer(data=payload)

		self.assertFalse(serializer.is_valid())
		self.assertIn('funding_goal_cents', serializer.errors)

	def test_campaign_summary_serializer_returns_model_fields(self):
		user = get_user_model().objects.create_user(
			email='serializer-creator@example.com',
			password='StrongPass123!',
		)
		campaign = Campaign.objects.create(
			creator=user,
			title='Serializer Campaign',
			summary='Serializer output verification.',
			funding_goal_cents=250000,
			deadline_at=timezone.now() + timezone.timedelta(days=15),
		)

		serializer = CampaignSummarySerializer(campaign)

		self.assertEqual(serializer.data['title'], 'Serializer Campaign')
		self.assertEqual(serializer.data['currency'], 'USD')
		self.assertEqual(serializer.data['status'], Campaign.Status.DRAFT)


class CreateCampaignApiTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.User = get_user_model()
		self.url = reverse('campaign-create')
		self.creator_user = self.User.objects.create_user(
			email='api-campaign-creator@example.com',
			password='StrongPass123!',
		)
		self.backer_user = self.User.objects.create_user(
			email='api-campaign-backer@example.com',
			password='StrongPass123!',
		)
		assign_role_to_user(self.creator_user, Role.RoleName.CREATOR)
		assign_role_to_user(self.backer_user, Role.RoleName.BACKER)

	def test_creator_with_connected_channel_can_create_campaign(self):
		CreatorChannel.objects.create(
			user=self.creator_user,
			onboarding_status=CreatorChannel.OnboardingStatus.CHANNEL_CONNECTED,
		)
		payload = {
			'title': 'Fund Episode Two',
			'summary': 'Help cover production and editing costs.',
			'funding_goal_cents': 600000,
			'deadline_at': (timezone.now() + timezone.timedelta(days=25)).isoformat(),
		}

		self.client.force_authenticate(user=self.creator_user)
		response = self.client.post(self.url, payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['title'], 'Fund Episode Two')
		self.assertEqual(response.data['status'], Campaign.Status.DRAFT)

	def test_creator_without_connected_channel_gets_400(self):
		payload = {
			'title': 'Fund Episode Three',
			'summary': 'Need support for production.',
			'funding_goal_cents': 300000,
			'deadline_at': (timezone.now() + timezone.timedelta(days=20)).isoformat(),
		}

		self.client.force_authenticate(user=self.creator_user)
		response = self.client.post(self.url, payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data['detail'], 'You must connect your YouTube channel before creating a campaign.')

	def test_creator_with_started_onboarding_gets_400_with_exact_message(self):
		CreatorChannel.objects.create(
			user=self.creator_user,
			onboarding_status=CreatorChannel.OnboardingStatus.STARTED,
		)
		payload = {
			'title': 'Started Onboarding Campaign',
			'summary': 'This should be blocked until channel connection is completed.',
			'funding_goal_cents': 350000,
			'deadline_at': (timezone.now() + timezone.timedelta(days=20)).isoformat(),
		}

		self.client.force_authenticate(user=self.creator_user)
		response = self.client.post(self.url, payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data['detail'], 'You must complete channel connection before creating a campaign.')

	def test_non_creator_cannot_create_campaign(self):
		payload = {
			'title': 'Backer Trying Campaign',
			'summary': 'Should not pass creator permissions.',
			'funding_goal_cents': 300000,
			'deadline_at': (timezone.now() + timezone.timedelta(days=20)).isoformat(),
		}

		self.client.force_authenticate(user=self.backer_user)
		response = self.client.post(self.url, payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_unauthenticated_cannot_create_campaign(self):
		payload = {
			'title': 'Anonymous Campaign',
			'summary': 'Should require authentication.',
			'funding_goal_cents': 300000,
			'deadline_at': (timezone.now() + timezone.timedelta(days=20)).isoformat(),
		}

		response = self.client.post(self.url, payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

