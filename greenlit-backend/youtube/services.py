import json
from django.utils import timezone
from django.db import IntegrityError
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings

from youtube.models import CreatorChannel
from users.models import Role


class YouTubeAPIError(Exception):
    pass


class YouTubeConnectError(Exception):
    pass


def start_creator_onboarding(user):
    if not user.has_role(Role.RoleName.CREATOR):
        raise YouTubeConnectError('Only creator users can start creator onboarding.')

    creator_channel, created = CreatorChannel.objects.get_or_create(
        user=user,
        defaults={
            'onboarding_status': CreatorChannel.OnboardingStatus.STARTED,
            'onboarding_started_at': timezone.now(),
            'sync_status': CreatorChannel.SyncStatus.PENDING,
            'sync_error': '',
        },
    )

    if created:
        return creator_channel

    if creator_channel.onboarding_status == CreatorChannel.OnboardingStatus.COMPLETE:
        return creator_channel

    fields_to_update = []
    if creator_channel.onboarding_status != CreatorChannel.OnboardingStatus.STARTED:
        creator_channel.onboarding_status = CreatorChannel.OnboardingStatus.STARTED
        fields_to_update.append('onboarding_status')

    if creator_channel.onboarding_started_at is None:
        creator_channel.onboarding_started_at = timezone.now()
        fields_to_update.append('onboarding_started_at')

    if fields_to_update:
        creator_channel.save(update_fields=fields_to_update)

    return creator_channel


def complete_creator_onboarding(user):
    if not user.has_role(Role.RoleName.CREATOR):
        raise YouTubeConnectError('Only creator users can complete creator onboarding.')

    try:
        creator_channel = CreatorChannel.objects.get(user=user)
    except CreatorChannel.DoesNotExist as exc:
        raise YouTubeConnectError('Creator channel does not exist. Start onboarding first.') from exc

    if not creator_channel.youtube_channel_id:
        raise YouTubeConnectError('Creator channel must be connected before onboarding can be completed.')

    if creator_channel.onboarding_status == CreatorChannel.OnboardingStatus.COMPLETE:
        return creator_channel

    creator_channel.onboarding_status = CreatorChannel.OnboardingStatus.COMPLETE
    creator_channel.onboarding_completed_at = timezone.now()
    creator_channel.save(update_fields=['onboarding_status', 'onboarding_completed_at'])

    return creator_channel


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _youtube_get(path, params):
    if not settings.YOUTUBE_API_KEY:
        raise YouTubeAPIError('YOUTUBE_API_KEY is not configured.')

    query = urlencode({**params, 'key': settings.YOUTUBE_API_KEY})
    url = f'https://www.googleapis.com/youtube/v3/{path}?{query}'

    try:
        with urlopen(url, timeout=10) as response:
            payload = response.read().decode('utf-8')
            return json.loads(payload)
    except HTTPError as exc:
        raise YouTubeAPIError(f'YouTube API HTTP error: {exc.code}') from exc
    except URLError as exc:
        raise YouTubeAPIError('YouTube API is unavailable right now.') from exc
    except json.JSONDecodeError as exc:
        raise YouTubeAPIError('Invalid response from YouTube API.') from exc


def fetch_public_channel_probe(channel_id, max_videos=5):
    channel_response = _youtube_get(
        'channels',
        {
            'part': 'snippet,statistics,contentDetails',
            'id': channel_id,
        },
    )

    items = channel_response.get('items', [])
    if not items:
        raise YouTubeAPIError('Channel not found for the provided channel_id.')

    channel = items[0]
    snippet = channel.get('snippet', {})
    statistics = channel.get('statistics', {})
    content_details = channel.get('contentDetails', {})

    uploads_playlist_id = (
        content_details.get('relatedPlaylists', {}).get('uploads')
    )

    recent_videos = []
    if uploads_playlist_id:
        playlist_response = _youtube_get(
            'playlistItems',
            {
                'part': 'snippet,contentDetails',
                'playlistId': uploads_playlist_id,
                'maxResults': max_videos,
            },
        )

        for video_item in playlist_response.get('items', []):
            video_snippet = video_item.get('snippet', {})
            video_content = video_item.get('contentDetails', {})
            thumbnails = video_snippet.get('thumbnails', {})

            recent_videos.append(
                {
                    'video_id': video_content.get('videoId'),
                    'title': video_snippet.get('title'),
                    'published_at': video_snippet.get('publishedAt'),
                    'thumbnail_url': (
                        thumbnails.get('medium', {}).get('url')
                        or thumbnails.get('default', {}).get('url')
                    ),
                }
            )

    thumbnails = snippet.get('thumbnails', {})

    return {
        'channel_id': channel.get('id'),
        'title': snippet.get('title'),
        'description': snippet.get('description'),
        'custom_url': snippet.get('customUrl'),
        'published_at': snippet.get('publishedAt'),
        'thumbnail_url': (
            thumbnails.get('high', {}).get('url')
            or thumbnails.get('medium', {}).get('url')
            or thumbnails.get('default', {}).get('url')
        ),
        'subscriber_count': _safe_int(statistics.get('subscriberCount')),
        'view_count': _safe_int(statistics.get('viewCount')),
        'video_count': _safe_int(statistics.get('videoCount')),
        'recent_videos': recent_videos,
    }


def connect_creator_channel(user, channel_id):
    start_creator_onboarding(user)

    probe_data = fetch_public_channel_probe(channel_id=channel_id)
    resolved_channel_id = probe_data.get('channel_id')

    if not resolved_channel_id:
        raise YouTubeConnectError('Unable to resolve channel ID from YouTube response.')

    try:
        creator_channel, _ = CreatorChannel.objects.update_or_create(
            user=user,
            defaults={
                'youtube_channel_id': resolved_channel_id,
                'channel_title': probe_data.get('title') or '',
                'channel_handle': probe_data.get('custom_url') or '',
                'last_synced_at': timezone.now(),
                'sync_status': CreatorChannel.SyncStatus.SUCCESS,
                'sync_error': '',
                'onboarding_status': CreatorChannel.OnboardingStatus.CHANNEL_CONNECTED,
                'channel_connected_at': timezone.now(),
            },
        )
    except IntegrityError as exc:
        raise YouTubeConnectError('This YouTube channel is already connected to another creator.') from exc

    return creator_channel


def get_creator_onboarding_summary(user):
    if not user.has_role(Role.RoleName.CREATOR):
        raise YouTubeConnectError('Only creator users can access creator onboarding summary.')

    try:
        creator_channel = CreatorChannel.objects.get(user=user)
    except CreatorChannel.DoesNotExist:
        return {
            'youtube_channel_id': '',
            'channel_title': '',
            'channel_handle': '',
            'sync_status': CreatorChannel.SyncStatus.PENDING,
            'last_synced_at': None,
            'onboarding_status': CreatorChannel.OnboardingStatus.STARTED,
            'onboarding_started_at': None,
            'channel_connected_at': None,
            'onboarding_completed_at': None,
        }

    return {
        'youtube_channel_id': creator_channel.youtube_channel_id or '',
        'channel_title': creator_channel.channel_title or '',
        'channel_handle': creator_channel.channel_handle or '',
        'sync_status': creator_channel.sync_status,
        'last_synced_at': creator_channel.last_synced_at,
        'onboarding_status': creator_channel.onboarding_status,
        'onboarding_started_at': creator_channel.onboarding_started_at,
        'channel_connected_at': creator_channel.channel_connected_at,
        'onboarding_completed_at': creator_channel.onboarding_completed_at,
    }
