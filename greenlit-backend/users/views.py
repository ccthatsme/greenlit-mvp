from rest_framework import generics
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model

from users.permissions import IsSelfOrAdmin
from users.serializers import SignupSerializer


class SignupView(generics.CreateAPIView):
	serializer_class = SignupSerializer
	permission_classes = [AllowAny]


class UserDeleteView(generics.DestroyAPIView):
	queryset = get_user_model().objects.all()
	permission_classes = [IsSelfOrAdmin]
	lookup_field = 'id'
	lookup_url_kwarg = 'user_id'
