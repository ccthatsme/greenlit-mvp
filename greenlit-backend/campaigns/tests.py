from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from campaigns.models import Campaign
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

