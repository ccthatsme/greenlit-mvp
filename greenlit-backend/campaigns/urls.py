from django.urls import path

from campaigns.views import CreateCampaignView, UpdateCampaignView


urlpatterns = [
	path('', CreateCampaignView.as_view(), name='campaign-create'),
	path('<uuid:campaign_id>/', UpdateCampaignView.as_view(), name='campaign-update'),
]
