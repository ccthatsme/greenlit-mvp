import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class CreatorChannel(models.Model):
	class SyncStatus(models.TextChoices):
		PENDING = 'pending', 'Pending'
		SUCCESS = 'success', 'Success'
		FAILED = 'failed', 'Failed'

	class OnboardingStatus(models.TextChoices):
		STARTED = 'started', 'Started'
		CHANNEL_CONNECTED = 'channel_connected', 'Channel Connected'
		COMPLETE = 'complete', 'Complete'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='creator_channel',
	)
	youtube_channel_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
	channel_title = models.CharField(max_length=255, blank=True)
	channel_handle = models.CharField(max_length=255, blank=True)
	last_synced_at = models.DateTimeField(null=True, blank=True)
	sync_status = models.CharField(
		max_length=20,
		choices=SyncStatus.choices,
		default=SyncStatus.PENDING,
	)
	sync_error = models.TextField(blank=True)
	onboarding_status = models.CharField(
		max_length=24,
		choices=OnboardingStatus.choices,
		default=OnboardingStatus.STARTED,
	)
	onboarding_started_at = models.DateTimeField(default=timezone.now)
	channel_connected_at = models.DateTimeField(null=True, blank=True)
	onboarding_completed_at = models.DateTimeField(null=True, blank=True)

	def __str__(self):
		channel_id = self.youtube_channel_id or 'unlinked'
		return f'{self.user.email} -> {channel_id}'
