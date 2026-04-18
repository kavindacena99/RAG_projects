from django.conf import settings

from chat.models import Message
from chat.repositories.chat_repository import ChatRepository
from chat.services.stream_service import build_streaming_response
from chat.services.title_service import generate_chat_title
from rag.services.answer_synthesis_service import (
    build_answer_plan,
    build_response_schema,
    build_synthesis_instructions,
)
from rag.services.context_structuring_service import build_structured_context
from rag.services.generation_service import build_generation_metadata
from rag.services.prompt_builder import build_answer_prompt
from rag.services.query_analysis_service import is_comparison_question
from rag.services.reformulation_service import reformulate_question
from rag.services.retrieval_service import retrieve_context


def _normalize_sources(chunks: list[dict]) -> list[dict]:
    normalized_sources = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.get("metadata") or {}
        text = str(chunk.get("text") or "").strip()
        if not text:
            continue

        normalized_sources.append(
            {
                "chunk_index": metadata.get("chunk_index", index),
                "id": str(chunk.get("id") or f"source-{index}"),
                "source": metadata.get("source"),
                "text": text,
                "topic": metadata.get("topic"),
            }
        )

    return normalized_sources


def _build_source_context(
    *,
    retrieved_chunk_count: int,
    standalone_question: str,
    structured_context: dict | None = None,
    retrieval_result: dict,
) -> dict:
    topics = [
        *((structured_context or {}).get("structured_topics", []) or []),
        *(retrieval_result.get("unique_topics_final") or []),
    ]

    return {
        "retrieved_chunk_count": retrieved_chunk_count,
        "standalone_question": standalone_question,
        "topics": list(dict.fromkeys(topic for topic in topics if topic)),
    }


class ChatService:
    def __init__(self, repository: ChatRepository | None = None):
        self.repository = repository or ChatRepository()

    def start_session(self, user):
        return self.repository.create_session(user)

    def list_sessions(self, user):
        return self.repository.get_user_sessions(user)

    def get_messages(self, user, session_id: int):
        session = self.repository.get_session_for_user(session_id, user)
        return self.repository.list_messages(session)

    def delete_session(self, user, session_id: int):
        session = self.repository.get_session_for_user(session_id, user)
        self.repository.delete_session(session)

    def handle_user_message(self, *, user, session_id: int | None, message_text: str):
        created_session = False
        session = None

        if session_id is None:
            session = self.repository.create_session(user)
            created_session = True
        else:
            session = self.repository.get_session_for_user(session_id, user)

        try:
            user_message = self.repository.create_message(
                session,
                Message.ROLE_USER,
                message_text,
            )

            history_messages = self.repository.get_recent_messages(
                session,
                max_pairs=settings.CHAT_MAX_HISTORY_PAIRS,
                exclude_message_id=user_message.id,
            )
            history = [
                {"role": message.role, "content": message.content}
                for message in history_messages
            ]

            standalone_question = reformulate_question(history, message_text)
            retrieval_result = retrieve_context(
                standalone_question,
                top_k=settings.RAG_CHAT_MAX_RETRIEVED_CHUNKS,
            )
            final_chunks = retrieval_result.get("retrieved_chunks_final") or []
            normalized_sources = _normalize_sources(final_chunks)
            comparison_detected = is_comparison_question(standalone_question)
            structured_context = build_structured_context(
                final_chunks,
                standalone_question,
                is_comparison=comparison_detected,
            )
            answer_plan = build_answer_plan(
                standalone_question,
                structured_context,
                is_comparison=comparison_detected,
            )
            synthesis_instructions = build_synthesis_instructions(answer_plan)
            response_schema = build_response_schema(answer_plan)
            answer_prompt = build_answer_prompt(
                history=history,
                standalone_question=standalone_question,
                structured_context=structured_context,
                answer_plan=answer_plan,
                synthesis_instructions=synthesis_instructions,
                response_schema=response_schema,
                is_comparison=comparison_detected,
            )
            source_context = _build_source_context(
                retrieved_chunk_count=len(normalized_sources),
                standalone_question=standalone_question,
                structured_context=structured_context,
                retrieval_result=retrieval_result,
            )

            def complete_stream(answer_text: str):
                assistant_message = self.repository.create_message(
                    session,
                    Message.ROLE_ASSISTANT,
                    answer_text,
                    sources=normalized_sources,
                    source_context=source_context,
                )
                self.repository.touch_session(session)
                if not session.title.strip():
                    self.repository.update_session_title(
                        session,
                        generate_chat_title(message_text),
                    )

                return {
                    "assistant_message_id": assistant_message.id,
                    "session_id": session.id,
                    "source_context": source_context,
                    "sources": normalized_sources,
                    "title": session.title,
                }

            def handle_stream_error(_exc):
                if created_session:
                    self.repository.delete_session(session)

            metadata = build_generation_metadata(
                session_id=session.id,
                standalone_question=standalone_question,
                history=history,
                chunks=final_chunks,
                structured_context=structured_context,
                answer_plan=answer_plan,
                retrieval_result=retrieval_result,
                source_context=source_context,
                sources=normalized_sources,
            )
            return build_streaming_response(
                prompt=answer_prompt,
                response_schema=response_schema,
                output_mode=answer_plan.get("mode", "standard"),
                metadata=metadata,
                on_complete=complete_stream,
                on_error=handle_stream_error,
            )
        except Exception:
            if created_session and session is not None:
                self.repository.delete_session(session)
            raise
