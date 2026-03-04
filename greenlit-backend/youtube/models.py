import uuid

from django.conf import settings
from django.db import models


class CreatorChannel(models.Model):
	class SyncStatus(models.TextChoices):
		PENDING = 'pending', 'Pending'
		SUCCESS = 'success', 'Success'
		FAILED = 'failed', 'Failed'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='creator_channel',
	)
	youtube_channel_id = models.CharField(max_length=128, unique=True)
	channel_title = models.CharField(max_length=255, blank=True)
	channel_handle = models.CharField(max_length=255, blank=True)
	last_synced_at = models.DateTimeField(null=True, blank=True)
	sync_status = models.CharField(
		max_length=20,
		choices=SyncStatus.choices,
		default=SyncStatus.PENDING,
	)
	sync_error = models.TextField(blank=True)

	def __str__(self):
		return f'{self.user.email} -> {self.youtube_channel_id}'
