from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from core.exceptions import AuthenticationError
from core.utils.jwt import create_access_token

User = get_user_model()


def register_user(*, username: str, email: str, password: str):
    if User.objects.filter(username=username).exists():
        raise AuthenticationError("Username is already taken.")
    if User.objects.filter(email=email).exists():
        raise AuthenticationError("Email is already in use.")

    try:
        validate_password(password)
    except DjangoValidationError as exc:
        raise AuthenticationError(" ".join(exc.messages)) from exc

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
    )
    return user


def login_user(*, identifier: str, password: str) -> tuple:
    user = None
    if "@" in identifier:
        try:
            matched_user = User.objects.get(email=identifier)
            user = authenticate(username=matched_user.username, password=password)
        except User.DoesNotExist:
            user = None
    else:
        user = authenticate(username=identifier, password=password)

    if user is None:
        raise AuthenticationError("Invalid credentials.")

    token = create_access_token(user)
    return user, token


def build_auth_response(user, token: str) -> dict:
    return {
        "access_token": token,
        "token_type": "Bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at,
        },
    }

