from rest_framework import serializers

from campaigns.models import Campaign


class CreateCampaignSerializer(serializers.Serializer):
	title = serializers.CharField(max_length=120)
	summary = serializers.CharField(max_length=500)
	funding_goal_cents = serializers.IntegerField(min_value=1)
	deadline_at = serializers.DateTimeField()


class CampaignSummarySerializer(serializers.ModelSerializer):
	class Meta:
		model = Campaign
		fields = [
			'id',
			'creator',
			'title',
			'summary',
			'funding_goal_cents',
			'currency',
			'deadline_at',
			'status',
			'amount_pledged_cents',
			'funded_at',
			'created_at',
			'updated_at',
		]
		read_only_fields = fields

