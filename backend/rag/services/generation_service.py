import logging

from django.conf import settings

from core.exceptions import GenerationError
from .llm_service import generate_text_from_prompt
from .prompt_builder import build_structure_retry_warning, validate_response_structure

logger = logging.getLogger("rag.pipeline")


def _chunk_text_for_streaming(text: str, words_per_chunk: int = 8):
    words = text.split()
    buffer = []
    for word in words:
        buffer.append(word)
        if len(buffer) >= words_per_chunk:
            yield " ".join(buffer) + " "
            buffer = []
    if buffer:
        yield " ".join(buffer)


def generate_answer_text(
    prompt: str,
    response_schema: dict | None = None,
    output_mode: str = "standard",
) -> str:
    answer = generate_text_from_prompt(
        prompt,
        max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
    )
    clean_answer = (answer or "").strip()
    if not clean_answer:
        raise GenerationError("Model did not return any answer text.")

    if response_schema and not validate_response_structure(
        clean_answer,
        response_schema,
        mode=output_mode,
    ):
        logger.warning(
            "response structure validation failed | mode=%s sections=%s retrying_once=True",
            output_mode,
            response_schema.get("sections", []),
        )
        retry_prompt = (
            f"{prompt}\n\n"
            f"{build_structure_retry_warning(response_schema, output_mode)}"
        )
        retry_answer = generate_text_from_prompt(
            retry_prompt,
            max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
        )
        retry_clean_answer = (retry_answer or "").strip()
        if retry_clean_answer:
            clean_answer = retry_clean_answer

    return clean_answer


def generate_answer_stream(
    prompt: str,
    response_schema: dict | None = None,
    output_mode: str = "standard",
):
    answer = generate_answer_text(
        prompt,
        response_schema=response_schema,
        output_mode=output_mode,
    )
    for chunk in _chunk_text_for_streaming(answer):
        yield chunk


def build_generation_metadata(
    *,
    session_id: int,
    standalone_question: str,
    history: list[dict],
    chunks: list[dict],
    structured_context: dict | None = None,
    answer_plan: dict | None = None,
    retrieval_result: dict,
) -> dict:
    return {
        "session_id": session_id,
        "standalone_question": standalone_question,
        "history_count": len(history),
        "retrieved_chunk_count": len(chunks),
        "structured_mode": (structured_context or {}).get("mode"),
        "structured_topics": (structured_context or {}).get("structured_topics", []),
        "deduped_chunk_count": (structured_context or {}).get("deduped_chunk_count"),
        "synthesis_mode": (answer_plan or {}).get("mode"),
        "synthesis_sections": [
            section.get("name") for section in (answer_plan or {}).get("sections", [])
        ],
        "synthesis_topics": (answer_plan or {}).get("topics", []),
        "comparison_question_detected": retrieval_result.get("comparison_question_detected"),
        "unique_topics_final": retrieval_result.get("unique_topics_final"),
    }
