import json
import logging
import os
import time
import uuid

logger = logging.getLogger("rag.llm")


def _get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing OPENAI_API_KEY. Add it to your environment or .env file."
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "openai is not installed. Install dependencies from requirements.txt."
        ) from exc

    return OpenAI(api_key=api_key)


def _extract_usage_metadata(response) -> dict:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")

    if usage is None:
        return {}

    if isinstance(usage, dict):
        return usage

    usage_dict = {}
    for field_name in ("input_tokens", "output_tokens", "total_tokens"):
        value = getattr(usage, field_name, None)
        if value is not None:
            usage_dict[field_name] = value

    prompt_tokens = getattr(usage, "prompt_tokens", None)
    if prompt_tokens is not None:
        usage_dict["prompt_tokens"] = prompt_tokens

    return usage_dict


def _extract_json_payload(text: str) -> dict:
    clean_text = (text or "").strip()
    if not clean_text:
        raise RuntimeError("LLM response did not include JSON text.")

    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        start = clean_text.find("{")
        end = clean_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError("LLM response did not contain valid JSON.")

        try:
            return json.loads(clean_text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM response contained invalid JSON.") from exc


def _build_rerank_prompt(question: str, chunks: list[dict]) -> str:
    chunk_lines = []
    for chunk in chunks:
        chunk_lines.append(
            (
                f"id: {chunk.get('id', '')}\n"
                f"text: {chunk.get('text', '')}"
            )
        )

    chunk_block = "\n\n".join(chunk_lines)
    return (
        "You are ranking study-note chunks for retrieval.\n"
        "For each chunk, give a relevance score from 0 to 10 for how useful it is "
        "for answering the question.\n"
        "Return strict JSON in this exact shape:\n"
        "{\"scores\": [{\"id\": \"chunk_id\", \"score\": 8.5}]}\n"
        "Use every chunk id exactly once. Do not include any extra text.\n\n"
        f"Question:\n{question}\n\n"
        f"Candidate chunks:\n{chunk_block}"
    )


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


def generate_embedding(text: str) -> list[float]:
    clean_text = (text or "").strip()
    if not clean_text:
        return []

    client = _get_openai_client()
    embedding_model = os.getenv(
        "OPENAI_EMBEDDING_MODEL",
        "text-embedding-3-small",
    )
    request_id = uuid.uuid4().hex[:8]
    started_at = time.perf_counter()

    logger.info(
        "embedding request started | provider=openai request_id=%s model=%s text_chars=%d",
        request_id,
        embedding_model,
        len(clean_text),
    )

    try:
        response = client.embeddings.create(
            model=embedding_model,
            input=clean_text,
        )
    except Exception as exc:
        logger.exception(
            "embedding request failed | provider=openai request_id=%s model=%s",
            request_id,
            embedding_model,
        )
        raise RuntimeError(f"OpenAI embedding failed: {exc}") from exc

    vector = []
    if getattr(response, "data", None):
        vector = list(response.data[0].embedding)

    if not vector:
        raise RuntimeError("OpenAI embedding response did not include vector values.")

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    usage = _extract_usage_metadata(response)
    logger.info(
        "embedding request completed | provider=openai request_id=%s dim=%d elapsed_ms=%s usage=%s",
        request_id,
        len(vector),
        elapsed_ms,
        usage or "{}",
    )

    return vector


def score_chunks_for_reranking(question: str, chunks: list[dict]) -> dict[str, float]:
    clean_question = (question or "").strip()
    if not clean_question:
        raise ValueError("Question is required for reranking.")
    if not chunks:
        return {}

    client = _get_openai_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    prompt = _build_rerank_prompt(clean_question, chunks)
    request_id = uuid.uuid4().hex[:8]
    started_at = time.perf_counter()

    logger.info(
        "rerank request started | provider=openai request_id=%s model=%s candidate_chunks=%d",
        request_id,
        model,
        len(chunks),
    )

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
        )
    except Exception as exc:
        logger.exception(
            "rerank request failed | provider=openai request_id=%s model=%s",
            request_id,
            model,
        )
        raise RuntimeError(f"OpenAI reranking failed: {exc}") from exc

    response_text = (getattr(response, "output_text", None) or "").strip()
    payload = _extract_json_payload(response_text)
    scores = payload.get("scores", [])

    score_map = {}
    for item in scores:
        if not isinstance(item, dict):
            continue
        chunk_id = item.get("id")
        score = item.get("score")
        if chunk_id is None or score is None:
            continue
        try:
            score_map[str(chunk_id)] = float(score)
        except (TypeError, ValueError):
            continue

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    usage = _extract_usage_metadata(response)
    logger.info(
        "rerank request completed | provider=openai request_id=%s scored_chunks=%d elapsed_ms=%s usage=%s",
        request_id,
        len(score_map),
        elapsed_ms,
        usage or "{}",
    )

    return score_map


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
            "answer request skipped | provider=openai reason=no_context question_chars=%d",
            len(clean_question),
        )
        return (
            "I could not find enough relevant context in the stored notes "
            "to answer this question."
        )

    client = _get_openai_client()
    model = model_name or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
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
        "answer request started | provider=openai request_id=%s model=%s question_chars=%d context_chunks=%d prompt_chars=%d",
        request_id,
        model,
        len(clean_question),
        len(context_chunks),
        len(prompt),
    )

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
        )
    except Exception as exc:
        logger.exception(
            "answer request failed | provider=openai request_id=%s model=%s",
            request_id,
            model,
        )
        raise RuntimeError(f"OpenAI answer generation failed: {exc}") from exc

    answer = (getattr(response, "output_text", None) or "").strip()
    if not answer:
        raise RuntimeError("OpenAI response did not include answer text.")

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    usage = _extract_usage_metadata(response)
    logger.info(
        "answer request completed | provider=openai request_id=%s answer_chars=%d elapsed_ms=%s usage=%s",
        request_id,
        len(answer),
        elapsed_ms,
        usage or "{}",
    )

    return answer
