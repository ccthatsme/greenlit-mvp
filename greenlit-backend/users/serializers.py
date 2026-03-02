from django.contrib.auth import get_user_model
from rest_framework import serializers

from users.models import Role
from users.services import assign_role_to_user


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    selected_role = serializers.ChoiceField(
        choices=[Role.RoleName.BACKER, Role.RoleName.CREATOR],
        write_only=True,
    )
    roles = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = get_user_model()
        fields = [
            'id',
            'email',
            'password',
            'password_confirm',
            'first_name',
            'last_name',
            'phone_number',
            'date_of_birth',
            'country',
            'selected_role',
            'roles',
        ]
        read_only_fields = ['id', 'roles']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        selected_role = validated_data.pop('selected_role')
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')

        user = get_user_model().objects.create_user(password=password, **validated_data)
        assign_role_to_user(user=user, role_name=selected_role)
        return user

    def get_roles(self, obj):
        return list(obj.role_assignments.values_list('role__name', flat=True))
