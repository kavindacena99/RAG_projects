from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from chat.models import ChatSession, Message
from core.utils.jwt import create_access_token


class ChatApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="chatuser",
            email="chat@example.com",
            password="SecurePass123!",
        )
        token = create_access_token(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_start_session_creates_empty_chat_session(self):
        response = self.client.post("/chat/start-session", {}, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertTrue(ChatSession.objects.filter(user=self.user).exists())

    @patch("chat.services.stream_service.generate_answer_stream")
    @patch("chat.services.chat_service.build_response_schema")
    @patch("chat.services.chat_service.build_synthesis_instructions")
    @patch("chat.services.chat_service.build_answer_plan")
    @patch("chat.services.chat_service.build_structured_context")
    @patch("chat.services.chat_service.retrieve_context")
    @patch("chat.services.chat_service.reformulate_question")
    def test_send_message_streams_and_persists_assistant_reply(
        self,
        mock_reformulate_question,
        mock_retrieve_context,
        mock_build_structured_context,
        mock_build_answer_plan,
        mock_build_synthesis_instructions,
        mock_build_response_schema,
        mock_generate_answer_stream,
    ):
        session = ChatSession.objects.create(user=self.user)
        mock_reformulate_question.return_value = "What is CI/CD?"
        mock_retrieve_context.return_value = {
            "comparison_question_detected": False,
            "unique_topics_final": ["devops"],
            "retrieved_chunks_final": [
                {
                    "id": "chunk-1",
                    "text": "CI/CD automates integration and delivery.",
                    "metadata": {"topic": "devops", "source": "knowledge/devops/devops.txt"},
                }
            ],
        }
        mock_build_structured_context.return_value = {
            "mode": "standard",
            "primary_topic": "devops",
            "structured_topics": ["devops"],
            "deduped_chunk_count": 1,
            "chunks": [
                {
                    "source": "knowledge/devops/devops.txt",
                    "text": "CI/CD automates integration and delivery.",
                }
            ],
        }
        mock_build_answer_plan.return_value = {
            "mode": "definition",
            "topics": ["devops"],
            "sections": [{"name": "Explanation"}, {"name": "Key Points"}],
        }
        mock_build_synthesis_instructions.return_value = (
            "SYNTHESIS INSTRUCTIONS:\n- Answer directly first."
        )
        mock_build_response_schema.return_value = {
            "format_name": "definition_response",
            "sections": ["Explanation", "Key Points"],
        }
        mock_generate_answer_stream.return_value = iter(["CI/CD ", "automates delivery."])

        response = self.client.post(
            "/chat/send-message",
            {
                "session_id": session.id,
                "message": "What is CI/CD?",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        streamed_payload = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn('"type": "token"', streamed_payload)
        self.assertIn('"type": "done"', streamed_payload)

        stored_messages = list(Message.objects.filter(session=session).order_by("created_at", "id"))
        self.assertEqual(len(stored_messages), 2)
        self.assertEqual(stored_messages[0].role, Message.ROLE_USER)
        self.assertEqual(stored_messages[1].role, Message.ROLE_ASSISTANT)
        self.assertEqual(stored_messages[1].content, "CI/CD automates delivery.")
        session.refresh_from_db()
        self.assertEqual(session.title, "What is CI/CD")
        mock_build_structured_context.assert_called_once()
        mock_build_answer_plan.assert_called_once()
        mock_build_synthesis_instructions.assert_called_once()
        mock_build_response_schema.assert_called_once()

    def test_messages_endpoint_blocks_other_users_session(self):
        other_user = get_user_model().objects.create_user(
            username="other",
            email="other@example.com",
            password="SecurePass123!",
        )
        session = ChatSession.objects.create(user=other_user)

        response = self.client.get(f"/chat/messages/{session.id}")

        self.assertEqual(response.status_code, 404)
