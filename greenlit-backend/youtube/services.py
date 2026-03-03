import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings


class YouTubeAPIError(Exception):
    pass


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
