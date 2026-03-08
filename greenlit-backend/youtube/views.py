from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from youtube.permissions import IsCreatorUser
from youtube.serializers import (
	ChannelProbeQuerySerializer,
	ChannelProbeResponseSerializer,
	ConnectCreatorChannelSerializer,
	CreatorChannelSummarySerializer,
)
from youtube.services import (
	YouTubeAPIError,
	YouTubeConnectError,
	complete_creator_onboarding,
	connect_creator_channel,
	fetch_public_channel_probe,
	get_creator_onboarding_summary,
)


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


class ConnectCreatorChannelView(APIView):
	permission_classes = [IsCreatorUser]

	def post(self, request):
		request_serializer = ConnectCreatorChannelSerializer(data=request.data)
		request_serializer.is_valid(raise_exception=True)

		channel_id = request_serializer.validated_data['channel_id']

		try:
			creator_channel = connect_creator_channel(user=request.user, channel_id=channel_id)
		except (YouTubeAPIError, YouTubeConnectError) as exc:
			return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

		response_serializer = CreatorChannelSummarySerializer(creator_channel)
		return Response(response_serializer.data, status=status.HTTP_200_OK)


class CompleteCreatorOnboardingView(APIView):
	permission_classes = [IsCreatorUser]

	def post(self, request):
		try:
			creator_channel = complete_creator_onboarding(user=request.user)
		except YouTubeConnectError as exc:
			return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

		response_serializer = CreatorChannelSummarySerializer(creator_channel)
		return Response(response_serializer.data, status=status.HTTP_200_OK)


class CreatorOnboardingMeView(APIView):
	permission_classes = [IsCreatorUser]

	def get(self, request):
		summary_data = get_creator_onboarding_summary(user=request.user)
		response_serializer = CreatorChannelSummarySerializer(data=summary_data)
		response_serializer.is_valid(raise_exception=True)
		return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
