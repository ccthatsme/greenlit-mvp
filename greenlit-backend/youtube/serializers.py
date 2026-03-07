from rest_framework import serializers


class ChannelProbeQuerySerializer(serializers.Serializer):
    channel_id = serializers.CharField(max_length=100)


class ChannelVideoSerializer(serializers.Serializer):
    video_id = serializers.CharField(allow_null=True)
    title = serializers.CharField(allow_blank=True, allow_null=True)
    published_at = serializers.CharField(allow_blank=True, allow_null=True)
    thumbnail_url = serializers.CharField(allow_blank=True, allow_null=True)


class ChannelProbeResponseSerializer(serializers.Serializer):
    channel_id = serializers.CharField()
    title = serializers.CharField(allow_blank=True, allow_null=True)
    description = serializers.CharField(allow_blank=True, allow_null=True)
    custom_url = serializers.CharField(allow_blank=True, allow_null=True)
    published_at = serializers.CharField(allow_blank=True, allow_null=True)
    thumbnail_url = serializers.CharField(allow_blank=True, allow_null=True)
    subscriber_count = serializers.IntegerField()
    view_count = serializers.IntegerField()
    video_count = serializers.IntegerField()
    recent_videos = ChannelVideoSerializer(many=True)


class ConnectCreatorChannelSerializer(serializers.Serializer):
    channel_id = serializers.CharField(max_length=100)


class CreatorChannelSummarySerializer(serializers.Serializer):
    youtube_channel_id = serializers.CharField()
    channel_title = serializers.CharField(allow_blank=True)
    channel_handle = serializers.CharField(allow_blank=True)
    sync_status = serializers.CharField()
    last_synced_at = serializers.DateTimeField(allow_null=True)
    onboarding_status = serializers.CharField()
    onboarding_started_at = serializers.DateTimeField(allow_null=True)
    channel_connected_at = serializers.DateTimeField(allow_null=True)
    onboarding_completed_at = serializers.DateTimeField(allow_null=True)
