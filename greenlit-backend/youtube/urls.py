from django.urls import path

from youtube.views import PublicChannelProbeView

urlpatterns = [
    path('channel/', PublicChannelProbeView.as_view(), name='youtube-public-channel-probe'),
]
