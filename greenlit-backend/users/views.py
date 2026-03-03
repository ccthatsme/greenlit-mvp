from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model

from users.permissions import IsSelfOrAdmin
from users.serializers import LogoutSerializer, MeSerializer, SignupSerializer


class SignupView(generics.CreateAPIView):
	serializer_class = SignupSerializer
	permission_classes = [AllowAny]


class UserDeleteView(generics.DestroyAPIView):
	queryset = get_user_model().objects.all()
	permission_classes = [IsSelfOrAdmin]
	lookup_field = 'id'
	lookup_url_kwarg = 'user_id'


class MeView(generics.RetrieveAPIView):
	serializer_class = MeSerializer
	permission_classes = [IsAuthenticated]

	def get_object(self):
		return self.request.user


class LogoutView(APIView):
	permission_classes = [IsAuthenticated]

	def post(self, request):
		serializer = LogoutSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		serializer.save()
		return Response(status=status.HTTP_205_RESET_CONTENT)
