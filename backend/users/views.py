from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import AuthenticationError
from .serializers import LoginSerializer, RegisterSerializer
from .services.auth_service import build_auth_response, login_user, register_user


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = register_user(**serializer.validated_data)
            token_user, token = login_user(
                identifier=user.username,
                password=serializer.validated_data["password"],
            )
            return Response(
                build_auth_response(token_user, token),
                status=status.HTTP_201_CREATED,
            )
        except AuthenticationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user, token = login_user(**serializer.validated_data)
            return Response(build_auth_response(user, token), status=status.HTTP_200_OK)
        except AuthenticationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

