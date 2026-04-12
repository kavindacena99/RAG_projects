import os
import time
import uuid
import logging

logger = logging.getLogger("rag.llm")

def _get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing GEMINI_API_KEY. Add it to your environment or .env file."
        )

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is not installed. Install dependencies from requirements.txt."
        ) from exc

    return genai.Client(api_key=api_key)


def _extract_embedding_values(embed_response) -> list[float]:
    embedding = getattr(embed_response, "embedding", None)
    if embedding is not None:
        values = getattr(embedding, "values", None)
        if values:
            return list(values)

    embeddings = getattr(embed_response, "embeddings", None)
    if embeddings:
        first_embedding = embeddings[0]
        values = getattr(first_embedding, "values", None)
        if values:
            return list(values)

        if isinstance(first_embedding, dict):
            dict_values = first_embedding.get("values")
            if dict_values:
                return list(dict_values)

    if isinstance(embed_response, dict):
        single_embedding = embed_response.get("embedding")
        if isinstance(single_embedding, dict) and single_embedding.get("values"):
            return list(single_embedding["values"])

        response_embeddings = embed_response.get("embeddings")
        if response_embeddings and isinstance(response_embeddings[0], dict):
            dict_values = response_embeddings[0].get("values")
            if dict_values:
                return list(dict_values)

    return []


def _extract_usage_metadata(response) -> dict:
    usage = getattr(response, "usage_metadata", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage_metadata")

    if usage is None:
        return {}

    if isinstance(usage, dict):
        return usage

    usage_dict = {}
    for field_name in (
        "prompt_token_count",
        "candidates_token_count",
        "total_token_count",
        "cached_content_token_count",
    ):
        value = getattr(usage, field_name, None)
        if value is not None:
            usage_dict[field_name] = value

    return usage_dict


def generate_embedding(text: str) -> list[float]:
    clean_text = (text or "").strip()
    if not clean_text:
        return []

    client = _get_gemini_client()
    embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004")
    request_id = uuid.uuid4().hex[:8]
    started_at = time.perf_counter()

    logger.info(
        "embedding request started | request_id=%s model=%s text_chars=%d",
        request_id,
        embedding_model,
        len(clean_text),
    )

    try:
        embed_response = client.models.embed_content(
            model=embedding_model,
            contents=clean_text,
        )
    except Exception as exc:
        logger.exception(
            "embedding request failed | request_id=%s model=%s",
            request_id,
            embedding_model,
        )
        raise RuntimeError(f"Gemini embedding failed: {exc}") from exc

    vector = _extract_embedding_values(embed_response)
    if not vector:
        raise RuntimeError(
            "Gemini embedding response did not include vector values."
        )

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    usage = _extract_usage_metadata(embed_response)
    logger.info(
        "embedding request completed | request_id=%s dim=%d elapsed_ms=%s usage=%s",
        request_id,
        len(vector),
        elapsed_ms,
        usage or "{}",
    )

    return vector


def _format_context_chunks(context_chunks: list[dict]) -> str:
    if not context_chunks:
        return "No context chunks were found."

    formatted_chunks = []
    for position, chunk in enumerate(context_chunks, start=1):
        metadata = chunk.get("metadata") or {}
        formatted_chunks.append(
            (
                f"Chunk {position}\n"
                f"- id: {chunk.get('id', '')}\n"
                f"- title: {metadata.get('title', '')}\n"
                f"- topic: {metadata.get('topic', '')}\n"
                f"- source: {metadata.get('source', '')}\n"
                f"- chunk_index: {metadata.get('chunk_index', '')}\n"
                f"- text: {chunk.get('text', '')}"
            )
        )

    return "\n\n".join(formatted_chunks)


def _extract_generated_text(generate_response) -> str:
    response_text = getattr(generate_response, "text", None)
    if response_text:
        return response_text.strip()

    candidates = getattr(generate_response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if content is None:
            continue

        parts = getattr(content, "parts", None) or []
        text_parts = []
        for part in parts:
            part_text = getattr(part, "text", None)
            if part_text:
                text_parts.append(part_text)

        if text_parts:
            return "\n".join(text_parts).strip()

    if isinstance(generate_response, dict):
        response_text = generate_response.get("text")
        if response_text:
            return str(response_text).strip()

    return ""


def generate_answer(
    question: str,
    context_chunks: list[dict],
    model_name: str | None = None,
) -> str:
    clean_question = (question or "").strip()
    if not clean_question:
        raise ValueError("Question is required to generate an answer.")

    if not context_chunks:
        logger.info(
            "answer request skipped | reason=no_context question_chars=%d",
            len(clean_question),
        )
        return (
            "I could not find enough relevant context in the stored notes "
            "to answer this question."
        )

    client = _get_gemini_client()
    model = model_name or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    context_text = _format_context_chunks(context_chunks)
    request_id = uuid.uuid4().hex[:8]

    prompt = (
        "You are a helpful study assistant.\n"
        "Answer only using the context below.\n"
        "If the answer is not present in the context, say clearly: "
        "\"I could not find this in the provided notes.\"\n\n"
        f"Question:\n{clean_question}\n\n"
        f"Context:\n{context_text}\n\n"
        "Answer:"
    )

    started_at = time.perf_counter()
    logger.info(
        "answer request started | request_id=%s model=%s question_chars=%d context_chunks=%d prompt_chars=%d",
        request_id,
        model,
        len(clean_question),
        len(context_chunks),
        len(prompt),
    )

    try:
        generate_response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
    except Exception as exc:
        logger.exception(
            "answer request failed | request_id=%s model=%s",
            request_id,
            model,
        )
        raise RuntimeError(f"Gemini answer generation failed: {exc}") from exc

    answer = _extract_generated_text(generate_response)
    if not answer:
        raise RuntimeError(
            "Gemini response did not include answer text."
        )

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    usage = _extract_usage_metadata(generate_response)
    logger.info(
        "answer request completed | request_id=%s answer_chars=%d elapsed_ms=%s usage=%s",
        request_id,
        len(answer),
        elapsed_ms,
        usage or "{}",
    )

    return answer
