from django.urls import path

from campaigns.views import CreateCampaignView


urlpatterns = [
	path('', CreateCampaignView.as_view(), name='campaign-create'),
]
