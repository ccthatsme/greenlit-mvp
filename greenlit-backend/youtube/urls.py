from django.urls import path

from youtube.views import (
    CompleteCreatorOnboardingView,
    ConnectCreatorChannelView,
    CreatorOnboardingMeView,
    PublicChannelProbeView,
)

urlpatterns = [
    path('channel/', PublicChannelProbeView.as_view(), name='youtube-public-channel-probe'),
    path('channel/connect/', ConnectCreatorChannelView.as_view(), name='youtube-connect-channel'),
    path('onboarding/me/', CreatorOnboardingMeView.as_view(), name='youtube-onboarding-me'),
    path('onboarding/complete/', CompleteCreatorOnboardingView.as_view(), name='youtube-complete-onboarding'),
]
