from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(required=True, allow_blank=False, max_length=150)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, allow_blank=False, write_only=True, min_length=8)


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True, allow_blank=False)
    password = serializers.CharField(required=True, allow_blank=False, write_only=True)

