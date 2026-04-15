from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import GenerationError
from core.exceptions import SessionNotFoundError
from core.permissions import IsAuthenticatedUser
from .serializers import (
    ChatSessionSerializer,
    MessageSerializer,
    SendMessageSerializer,
    StartSessionSerializer,
)
from .services.chat_service import ChatService


class StartSessionView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request):
        serializer = StartSessionSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        try:
            session = ChatService().start_session(request.user)
            return Response(ChatSessionSerializer(session).data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatSessionsView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def get(self, request):
        try:
            sessions = ChatService().list_sessions(request.user)
            return Response(ChatSessionSerializer(sessions, many=True).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatMessagesView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def get(self, request, session_id: int):
        try:
            messages = ChatService().get_messages(request.user, session_id)
            return Response(MessageSerializer(messages, many=True).data, status=status.HTTP_200_OK)
        except SessionNotFoundError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendMessageView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def post(self, request):
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            return ChatService().handle_user_message(
                user=request.user,
                session_id=serializer.validated_data["session_id"],
                message_text=serializer.validated_data["message"],
            )
        except SessionNotFoundError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except (GenerationError, ValueError) as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeleteSessionView(APIView):
    permission_classes = [IsAuthenticatedUser]

    def delete(self, request, session_id: int):
        try:
            ChatService().delete_session(request.user, session_id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except SessionNotFoundError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
