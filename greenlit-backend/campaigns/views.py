from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from campaigns.permissions import IsCreatorUser
from campaigns.serializers import CampaignSummarySerializer, CreateCampaignSerializer, UpdateCampaignSerializer
from campaigns.services import (
	CampaignConflictError,
	CampaignOnboardingError,
	CampaignPermissionError,
	CampaignValidationError,
	create_campaign,
	publish_campaign,
	update_campaign,
)


class CreateCampaignView(APIView):
	permission_classes = [IsCreatorUser]

	def post(self, request):
		request_serializer = CreateCampaignSerializer(data=request.data)
		request_serializer.is_valid(raise_exception=True)

		try:
			campaign = create_campaign(
				request.user,
				title=request_serializer.validated_data['title'],
				summary=request_serializer.validated_data['summary'],
				funding_goal_cents=request_serializer.validated_data['funding_goal_cents'],
				deadline_at=request_serializer.validated_data['deadline_at'],
			)
		except CampaignPermissionError as exc:
			return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
		except (CampaignValidationError, CampaignOnboardingError, CampaignConflictError) as exc:
			return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

		response_serializer = CampaignSummarySerializer(campaign)
		return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class UpdateCampaignView(APIView):
	permission_classes = [IsCreatorUser]

	def patch(self, request, campaign_id):
		request_serializer = UpdateCampaignSerializer(data=request.data)
		request_serializer.is_valid(raise_exception=True)

		try:
			campaign = update_campaign(
				request.user,
				campaign_id=campaign_id,
				title=request_serializer.validated_data.get('title'),
				summary=request_serializer.validated_data.get('summary'),
				funding_goal_cents=request_serializer.validated_data.get('funding_goal_cents'),
				deadline_at=request_serializer.validated_data.get('deadline_at'),
			)
		except CampaignPermissionError as exc:
			return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
		except (CampaignValidationError, CampaignConflictError) as exc:
			return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

		response_serializer = CampaignSummarySerializer(campaign)
		return Response(response_serializer.data, status=status.HTTP_200_OK)


class PublishCampaignView(APIView):
	permission_classes = [IsCreatorUser]

	def post(self, request, campaign_id):
		try:
			campaign = publish_campaign(request.user, campaign_id=campaign_id)
		except CampaignPermissionError as exc:
			return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
		except (CampaignValidationError, CampaignConflictError) as exc:
			return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

		response_serializer = CampaignSummarySerializer(campaign)
		return Response(response_serializer.data, status=status.HTTP_200_OK)

