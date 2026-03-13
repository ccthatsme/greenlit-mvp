from django.urls import path

from campaigns.views import CreateCampaignView, PublishCampaignView, UpdateCampaignView


urlpatterns = [
	path('', CreateCampaignView.as_view(), name='campaign-create'),
	path('<uuid:campaign_id>/', UpdateCampaignView.as_view(), name='campaign-update'),
	path('<uuid:campaign_id>/publish/', PublishCampaignView.as_view(), name='campaign-publish'),
]
