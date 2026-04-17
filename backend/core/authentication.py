from django.contrib.auth import get_user_model
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed

from .utils.jwt import decode_access_token


class JWTAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        authorization_header = authentication.get_authorization_header(request).decode("utf-8")
        if not authorization_header:
            return None

        parts = authorization_header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            raise AuthenticationFailed("Invalid authorization header.")

        token = parts[1]
        try:
            payload = decode_access_token(token)
        except ValueError as exc:
            raise AuthenticationFailed(str(exc)) from exc

        user_model = get_user_model()
        try:
            user = user_model.objects.get(pk=payload.get("sub"))
        except user_model.DoesNotExist as exc:
            raise AuthenticationFailed("User not found.") from exc

        if not user.is_active:
            raise AuthenticationFailed("User account is inactive.")

        return user, token
