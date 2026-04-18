from django.db.models import QuerySet
from django.utils import timezone

from core.exceptions import SessionNotFoundError
from chat.models import ChatSession, Message


class ChatRepository:
    def create_session(self, user) -> ChatSession:
        return ChatSession.objects.create(user=user)

    def get_user_sessions(self, user) -> QuerySet[ChatSession]:
        return ChatSession.objects.filter(user=user).order_by("-updated_at", "-id")

    def get_session_for_user(self, session_id: int, user) -> ChatSession:
        try:
            return ChatSession.objects.get(id=session_id, user=user)
        except ChatSession.DoesNotExist as exc:
            raise SessionNotFoundError("Chat session not found.") from exc

    def delete_session(self, session: ChatSession) -> None:
        session.delete()

    def create_message(
        self,
        session: ChatSession,
        role: str,
        content: str,
        *,
        source_context: dict | None = None,
        sources: list[dict] | None = None,
    ) -> Message:
        return Message.objects.create(
            session=session,
            role=role,
            content=content,
            sources=sources or [],
            source_context=source_context or {},
        )

    def get_recent_messages(
        self,
        session: ChatSession,
        max_pairs: int = 3,
        exclude_message_id: int | None = None,
    ) -> list[Message]:
        queryset = Message.objects.filter(session=session)
        if exclude_message_id is not None:
            queryset = queryset.exclude(id=exclude_message_id)
        messages = list(queryset.order_by("-created_at", "-id")[: max_pairs * 2])
        messages.reverse()
        return messages

    def list_messages(self, session: ChatSession) -> QuerySet[Message]:
        return Message.objects.filter(session=session).order_by("created_at", "id")

    def update_session_title(self, session: ChatSession, title: str) -> ChatSession:
        session.title = title
        session.save(update_fields=["title", "updated_at"])
        return session

    def touch_session(self, session: ChatSession) -> ChatSession:
        session.updated_at = timezone.now()
        session.save(update_fields=["updated_at"])
        return session

    def get_first_user_message(self, session: ChatSession) -> Message | None:
        return (
            Message.objects.filter(session=session, role=Message.ROLE_USER)
            .order_by("created_at", "id")
            .first()
        )
