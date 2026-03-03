from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from youtube.serializers import (
	ChannelProbeQuerySerializer,
	ChannelProbeResponseSerializer,
)
from youtube.services import YouTubeAPIError, fetch_public_channel_probe


class PublicChannelProbeView(APIView):
	permission_classes = [AllowAny]

	def get(self, request):
		query_serializer = ChannelProbeQuerySerializer(data=request.query_params)
		query_serializer.is_valid(raise_exception=True)

		channel_id = query_serializer.validated_data['channel_id']

		try:
			probe_data = fetch_public_channel_probe(channel_id=channel_id)
		except YouTubeAPIError as exc:
			return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

		response_serializer = ChannelProbeResponseSerializer(data=probe_data)
		response_serializer.is_valid(raise_exception=True)
		return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
