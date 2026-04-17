from django.urls import path

from .views import (
    ChatMessagesView,
    ChatSessionsView,
    DeleteSessionView,
    SendMessageView,
    StartSessionView,
)

urlpatterns = [
    path("start-session", StartSessionView.as_view(), name="chat-start-session"),
    path("sessions", ChatSessionsView.as_view(), name="chat-sessions"),
    path("messages/<int:session_id>", ChatMessagesView.as_view(), name="chat-messages"),
    path("send-message", SendMessageView.as_view(), name="chat-send-message"),
    path("session/<int:session_id>", DeleteSessionView.as_view(), name="chat-delete-session"),
]
