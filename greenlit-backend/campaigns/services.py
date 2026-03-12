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


def validate_campaign_update_payload(*, title=None, summary=None, funding_goal_cents=None, deadline_at=None):
	if title is None and summary is None and funding_goal_cents is None and deadline_at is None:
		raise CampaignValidationError('At least one campaign field must be provided for update.')

	validated_data = {}

	if title is not None:
		normalized_title = title.strip()
		if not normalized_title:
			raise CampaignValidationError('Campaign title is required.')
		validated_data['title'] = normalized_title

	if summary is not None:
		normalized_summary = summary.strip()
		if not normalized_summary:
			raise CampaignValidationError('Campaign summary is required.')
		validated_data['summary'] = normalized_summary

	if funding_goal_cents is not None:
		if not isinstance(funding_goal_cents, int) or funding_goal_cents <= 0:
			raise CampaignValidationError('Funding goal must be a positive integer amount in cents.')
		validated_data['funding_goal_cents'] = funding_goal_cents

	if deadline_at is not None:
		if deadline_at <= timezone.now():
			raise CampaignValidationError('Campaign deadline must be in the future.')
		validated_data['deadline_at'] = deadline_at

	return validated_data


def update_campaign(
	user,
	*,
	campaign_id,
	title=None,
	summary=None,
	funding_goal_cents=None,
	deadline_at=None,
):
	if not user.has_role(Role.RoleName.CREATOR):
		raise CampaignPermissionError('Only creator users can update campaigns.')

	try:
		campaign = Campaign.objects.get(id=campaign_id)
	except Campaign.DoesNotExist as exc:
		raise CampaignValidationError('Campaign does not exist.') from exc

	if campaign.creator_id != user.id:
		raise CampaignPermissionError('You do not have permission to update this campaign.')

	if campaign.status != Campaign.Status.DRAFT:
		raise CampaignConflictError('Only draft campaigns can be updated.')

	validated_data = validate_campaign_update_payload(
		title=title,
		summary=summary,
		funding_goal_cents=funding_goal_cents,
		deadline_at=deadline_at,
	)

	for field_name, field_value in validated_data.items():
		setattr(campaign, field_name, field_value)

	campaign.save(update_fields=[*validated_data.keys(), 'updated_at'])
	return campaign
