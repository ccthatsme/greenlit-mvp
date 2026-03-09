import uuid

from django.conf import settings
from django.db import models


class Campaign(models.Model):
	class Status(models.TextChoices):
		DRAFT = 'draft', 'Draft'
		ACTIVE = 'active', 'Active'
		FUNDED = 'funded', 'Funded'
		CLOSED = 'closed', 'Closed'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	creator = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='campaigns',
	)
	title = models.CharField(max_length=120)
	summary = models.CharField(max_length=500)
	funding_goal_cents = models.PositiveIntegerField()
	currency = models.CharField(max_length=3, default='USD')
	deadline_at = models.DateTimeField()
	status = models.CharField(
		max_length=20,
		choices=Status.choices,
		default=Status.DRAFT,
	)
	amount_pledged_cents = models.PositiveIntegerField(default=0)
	funded_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f'{self.title} ({self.status})'

