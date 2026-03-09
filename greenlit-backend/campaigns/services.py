from django.utils import timezone

from campaigns.models import Campaign
from users.models import Role
from youtube.models import CreatorChannel


class CampaignPermissionError(Exception):
	pass


class CampaignValidationError(Exception):
	pass


class CampaignOnboardingError(Exception):
	pass


class CampaignConflictError(Exception):
	pass


def assert_creator_can_create_campaign(user):
	if not user.has_role(Role.RoleName.CREATOR):
		raise CampaignPermissionError('Only creator users can create campaigns.')

	try:
		creator_channel = CreatorChannel.objects.get(user=user)
	except CreatorChannel.DoesNotExist as exc:
		raise CampaignOnboardingError('You must connect your YouTube channel before creating a campaign.') from exc

	allowed_statuses = {
		CreatorChannel.OnboardingStatus.CHANNEL_CONNECTED,
		CreatorChannel.OnboardingStatus.COMPLETE,
	}
	if creator_channel.onboarding_status not in allowed_statuses:
		raise CampaignOnboardingError('You must complete channel connection before creating a campaign.')


def has_active_campaign(user):
	return Campaign.objects.filter(creator=user, status=Campaign.Status.ACTIVE).exists()


def validate_campaign_create_payload(*, title, summary, funding_goal_cents, deadline_at):
	normalized_title = (title or '').strip()
	if not normalized_title:
		raise CampaignValidationError('Campaign title is required.')

	normalized_summary = (summary or '').strip()
	if not normalized_summary:
		raise CampaignValidationError('Campaign summary is required.')

	if not isinstance(funding_goal_cents, int) or funding_goal_cents <= 0:
		raise CampaignValidationError('Funding goal must be a positive integer amount in cents.')

	if deadline_at is None or deadline_at <= timezone.now():
		raise CampaignValidationError('Campaign deadline must be in the future.')

	return {
		'title': normalized_title,
		'summary': normalized_summary,
		'funding_goal_cents': funding_goal_cents,
		'deadline_at': deadline_at,
	}


def create_campaign(user, *, title, summary, funding_goal_cents, deadline_at):
	assert_creator_can_create_campaign(user)

	validated_data = validate_campaign_create_payload(
		title=title,
		summary=summary,
		funding_goal_cents=funding_goal_cents,
		deadline_at=deadline_at,
	)

	if has_active_campaign(user):
		raise CampaignConflictError('You already have an active campaign.')

	return Campaign.objects.create(
		creator=user,
		title=validated_data['title'],
		summary=validated_data['summary'],
		funding_goal_cents=validated_data['funding_goal_cents'],
		deadline_at=validated_data['deadline_at'],
		currency='USD',
	)
