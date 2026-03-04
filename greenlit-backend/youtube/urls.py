from django.urls import path

from youtube.views import ConnectCreatorChannelView, PublicChannelProbeView

urlpatterns = [
    path('channel/', PublicChannelProbeView.as_view(), name='youtube-public-channel-probe'),
    path('channel/connect/', ConnectCreatorChannelView.as_view(), name='youtube-connect-channel'),
]
