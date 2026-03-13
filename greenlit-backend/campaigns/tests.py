from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from campaigns.models import Campaign
from campaigns.serializers import CampaignSummarySerializer, CreateCampaignSerializer, UpdateCampaignSerializer
from campaigns.services import (
	CampaignConflictError,
	CampaignOnboardingError,
	CampaignPermissionError,
	CampaignValidationError,
	assert_creator_can_create_campaign,
	create_campaign,
	publish_campaign,
	update_campaign,
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

	def test_update_campaign_success_for_owner_draft(self):
		campaign = Campaign.objects.create(
			creator=self.creator_user,
			title='Original Title',
			summary='Original summary',
			funding_goal_cents=300000,
			deadline_at=timezone.now() + timezone.timedelta(days=30),
		)
		new_deadline = timezone.now() + timezone.timedelta(days=45)

		updated = update_campaign(
			self.creator_user,
			campaign_id=campaign.id,
			title='  Updated Title  ',
			summary='  Updated summary text.  ',
			funding_goal_cents=450000,
			deadline_at=new_deadline,
		)

		self.assertEqual(updated.title, 'Updated Title')
		self.assertEqual(updated.summary, 'Updated summary text.')
		self.assertEqual(updated.funding_goal_cents, 450000)
		self.assertEqual(updated.deadline_at, new_deadline)

	def test_update_campaign_rejects_non_creator(self):
		campaign = Campaign.objects.create(
			creator=self.creator_user,
			title='Creator Campaign',
			summary='Owned by creator',
			funding_goal_cents=250000,
			deadline_at=timezone.now() + timezone.timedelta(days=20),
		)

		with self.assertRaisesMessage(CampaignPermissionError, 'Only creator users can update campaigns.'):
			update_campaign(
				self.backer_user,
				campaign_id=campaign.id,
				title='Should Fail',
			)

	def test_update_campaign_rejects_non_owner(self):
		other_creator = self.User.objects.create_user(
			email='other-creator@example.com',
			password='StrongPass123!',
		)
		assign_role_to_user(other_creator, Role.RoleName.CREATOR)
		campaign = Campaign.objects.create(
			creator=self.creator_user,
			title='Creator Campaign',
			summary='Owner only update.',
			funding_goal_cents=250000,
			deadline_at=timezone.now() + timezone.timedelta(days=20),
		)

		with self.assertRaisesMessage(CampaignPermissionError, 'You do not have permission to update this campaign.'):
			update_campaign(
				other_creator,
				campaign_id=campaign.id,
				title='Should Fail',
			)

	def test_update_campaign_rejects_non_draft_campaign(self):
		campaign = Campaign.objects.create(
			creator=self.creator_user,
			title='Active Campaign',
			summary='No updates when active',
			funding_goal_cents=250000,
			deadline_at=timezone.now() + timezone.timedelta(days=20),
			status=Campaign.Status.ACTIVE,
		)

		with self.assertRaisesMessage(CampaignConflictError, 'Only draft campaigns can be updated.'):
			update_campaign(
				self.creator_user,
				campaign_id=campaign.id,
				title='Should Fail',
			)

	def test_update_campaign_requires_at_least_one_field(self):
		campaign = Campaign.objects.create(
			creator=self.creator_user,
			title='Draft Campaign',
			summary='No-op update test',
			funding_goal_cents=250000,
			deadline_at=timezone.now() + timezone.timedelta(days=20),
		)

		with self.assertRaisesMessage(
			CampaignValidationError,
			'At least one campaign field must be provided for update.',
		):
			update_campaign(
				self.creator_user,
				campaign_id=campaign.id,
			)

	def test_update_campaign_rejects_invalid_goal(self):
		campaign = Campaign.objects.create(
			creator=self.creator_user,
			title='Draft Campaign',
			summary='Invalid goal update test',
			funding_goal_cents=250000,
			deadline_at=timezone.now() + timezone.timedelta(days=20),
		)

		with self.assertRaisesMessage(
			CampaignValidationError,
			'Funding goal must be a positive integer amount in cents.',
		):
			update_campaign(
				self.creator_user,
				campaign_id=campaign.id,
				funding_goal_cents=0,
			)

	def test_update_campaign_rejects_past_deadline(self):
		campaign = Campaign.objects.create(
			creator=self.creator_user,
			title='Draft Campaign',
			summary='Past deadline update test',
			funding_goal_cents=250000,
			deadline_at=timezone.now() + timezone.timedelta(days=20),
		)

		with self.assertRaisesMessage(
			CampaignValidationError,
			'Campaign deadline must be in the future.',
		):
			update_campaign(
				self.creator_user,
				campaign_id=campaign.id,
				deadline_at=timezone.now() - timezone.timedelta(days=1),
			)


class PublishCampaignServiceTests(TestCase):
	def setUp(self):
		self.User = get_user_model()
		self.creator_user = self.User.objects.create_user(
			email='svc-publish-creator@example.com',
			password='StrongPass123!',
		)
		self.other_creator_user = self.User.objects.create_user(
			email='svc-publish-other@example.com',
			password='StrongPass123!',
		)
		self.backer_user = self.User.objects.create_user(
			email='svc-publish-backer@example.com',
			password='StrongPass123!',
		)
		assign_role_to_user(self.creator_user, Role.RoleName.CREATOR)
		assign_role_to_user(self.other_creator_user, Role.RoleName.CREATOR)
		assign_role_to_user(self.backer_user, Role.RoleName.BACKER)
		self.campaign = Campaign.objects.create(
			creator=self.creator_user,
			title='Draft Campaign',
			summary='Ready to publish.',
			funding_goal_cents=500000,
			deadline_at=timezone.now() + timezone.timedelta(days=30),
		)

	def test_publish_campaign_transitions_draft_to_active(self):
		campaign = publish_campaign(self.creator_user, campaign_id=self.campaign.id)

		self.assertEqual(campaign.status, Campaign.Status.ACTIVE)

	def test_publish_campaign_rejects_non_creator(self):
		with self.assertRaisesMessage(CampaignPermissionError, 'Only creator users can publish campaigns.'):
			publish_campaign(self.backer_user, campaign_id=self.campaign.id)

	def test_publish_campaign_rejects_non_owner(self):
		with self.assertRaisesMessage(CampaignPermissionError, 'You do not have permission to publish this campaign.'):
			publish_campaign(self.other_creator_user, campaign_id=self.campaign.id)

	def test_publish_campaign_rejects_already_active_campaign(self):
		self.campaign.status = Campaign.Status.ACTIVE
		self.campaign.save(update_fields=['status'])

		with self.assertRaisesMessage(CampaignConflictError, 'Only draft campaigns can be published.'):
			publish_campaign(self.creator_user, campaign_id=self.campaign.id)

	def test_publish_campaign_rejects_closed_campaign(self):
		self.campaign.status = Campaign.Status.CLOSED
		self.campaign.save(update_fields=['status'])

		with self.assertRaisesMessage(CampaignConflictError, 'Only draft campaigns can be published.'):
			publish_campaign(self.creator_user, campaign_id=self.campaign.id)

	def test_publish_campaign_rejects_past_deadline(self):
		self.campaign.deadline_at = timezone.now() - timezone.timedelta(days=1)
		self.campaign.save(update_fields=['deadline_at'])

		with self.assertRaisesMessage(CampaignValidationError, 'Cannot publish a campaign with a past deadline.'):
			publish_campaign(self.creator_user, campaign_id=self.campaign.id)

	def test_publish_campaign_rejects_nonexistent_campaign(self):
		import uuid
		with self.assertRaisesMessage(CampaignValidationError, 'Campaign does not exist.'):
			publish_campaign(self.creator_user, campaign_id=uuid.uuid4())


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

	def test_update_campaign_serializer_valid_partial_payload(self):
		payload = {
			'title': 'Updated Campaign Title',
			'funding_goal_cents': 550000,
		}

		serializer = UpdateCampaignSerializer(data=payload)

		self.assertTrue(serializer.is_valid(), serializer.errors)

	def test_update_campaign_serializer_rejects_invalid_goal(self):
		payload = {
			'funding_goal_cents': 0,
		}

		serializer = UpdateCampaignSerializer(data=payload)

		self.assertFalse(serializer.is_valid())
		self.assertIn('funding_goal_cents', serializer.errors)

	def test_update_campaign_serializer_allows_empty_object_for_service_layer_validation(self):
		serializer = UpdateCampaignSerializer(data={})

		self.assertTrue(serializer.is_valid(), serializer.errors)


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


class UpdateCampaignApiTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.User = get_user_model()
		self.creator_user = self.User.objects.create_user(
			email='api-update-creator@example.com',
			password='StrongPass123!',
		)
		self.other_creator_user = self.User.objects.create_user(
			email='api-update-other-creator@example.com',
			password='StrongPass123!',
		)
		self.backer_user = self.User.objects.create_user(
			email='api-update-backer@example.com',
			password='StrongPass123!',
		)
		assign_role_to_user(self.creator_user, Role.RoleName.CREATOR)
		assign_role_to_user(self.other_creator_user, Role.RoleName.CREATOR)
		assign_role_to_user(self.backer_user, Role.RoleName.BACKER)
		self.campaign = Campaign.objects.create(
			creator=self.creator_user,
			title='Original Campaign Title',
			summary='Original campaign summary.',
			funding_goal_cents=400000,
			deadline_at=timezone.now() + timezone.timedelta(days=30),
		)
		self.url = reverse('campaign-update', kwargs={'campaign_id': self.campaign.id})

	def test_owner_can_patch_draft_campaign(self):
		payload = {
			'title': 'Updated Campaign Title',
			'funding_goal_cents': 450000,
		}

		self.client.force_authenticate(user=self.creator_user)
		response = self.client.patch(self.url, payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['title'], 'Updated Campaign Title')
		self.assertEqual(response.data['funding_goal_cents'], 450000)

	def test_unauthenticated_cannot_patch_campaign(self):
		response = self.client.patch(self.url, {'title': 'No Auth'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_non_creator_cannot_patch_campaign(self):
		self.client.force_authenticate(user=self.backer_user)
		response = self.client.patch(self.url, {'title': 'Backer Update'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_non_owner_creator_cannot_patch_campaign(self):
		self.client.force_authenticate(user=self.other_creator_user)
		response = self.client.patch(self.url, {'title': 'Not Owner Update'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(response.data['detail'], 'You do not have permission to update this campaign.')

	def test_patch_rejects_non_draft_campaign(self):
		self.campaign.status = Campaign.Status.ACTIVE
		self.campaign.save(update_fields=['status'])

		self.client.force_authenticate(user=self.creator_user)
		response = self.client.patch(self.url, {'title': 'Should Fail'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data['detail'], 'Only draft campaigns can be updated.')

	def test_patch_rejects_empty_payload(self):
		self.client.force_authenticate(user=self.creator_user)
		response = self.client.patch(self.url, {}, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data['detail'], 'At least one campaign field must be provided for update.')


class PublishCampaignApiTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.User = get_user_model()
		self.creator_user = self.User.objects.create_user(
			email='api-publish-creator@example.com',
			password='StrongPass123!',
		)
		self.other_creator_user = self.User.objects.create_user(
			email='api-publish-other@example.com',
			password='StrongPass123!',
		)
		self.backer_user = self.User.objects.create_user(
			email='api-publish-backer@example.com',
			password='StrongPass123!',
		)
		assign_role_to_user(self.creator_user, Role.RoleName.CREATOR)
		assign_role_to_user(self.other_creator_user, Role.RoleName.CREATOR)
		assign_role_to_user(self.backer_user, Role.RoleName.BACKER)
		self.campaign = Campaign.objects.create(
			creator=self.creator_user,
			title='Draft Campaign To Publish',
			summary='Ready to go live.',
			funding_goal_cents=500000,
			deadline_at=timezone.now() + timezone.timedelta(days=30),
		)
		self.url = reverse('campaign-publish', kwargs={'campaign_id': self.campaign.id})

	def test_owner_can_publish_draft_campaign(self):
		self.client.force_authenticate(user=self.creator_user)
		response = self.client.post(self.url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['status'], Campaign.Status.ACTIVE)

	def test_unauthenticated_cannot_publish_campaign(self):
		response = self.client.post(self.url)

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_non_creator_cannot_publish_campaign(self):
		self.client.force_authenticate(user=self.backer_user)
		response = self.client.post(self.url)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_non_owner_creator_cannot_publish_campaign(self):
		self.client.force_authenticate(user=self.other_creator_user)
		response = self.client.post(self.url)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(response.data['detail'], 'You do not have permission to publish this campaign.')

	def test_cannot_publish_non_draft_campaign(self):
		self.campaign.status = Campaign.Status.ACTIVE
		self.campaign.save(update_fields=['status'])

		self.client.force_authenticate(user=self.creator_user)
		response = self.client.post(self.url)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data['detail'], 'Only draft campaigns can be published.')

	def test_cannot_publish_campaign_with_past_deadline(self):
		self.campaign.deadline_at = timezone.now() - timezone.timedelta(days=1)
		self.campaign.save(update_fields=['deadline_at'])

		self.client.force_authenticate(user=self.creator_user)
		response = self.client.post(self.url)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data['detail'], 'Cannot publish a campaign with a past deadline.')

