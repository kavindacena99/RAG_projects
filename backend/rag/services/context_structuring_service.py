import logging
import re
from typing import Any

from rag.services.query_analysis_service import (
    extract_comparison_terms,
    normalize_comparison_term_to_topic,
)
from rag.utils.topic_normalizer import normalize_topic, normalize_topics

logger = logging.getLogger("rag.pipeline")

_WHITESPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[\W_]+")


def _clean_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", (text or "").strip())


def _normalized_text_key(text: str) -> str:
    return _NON_WORD_RE.sub(" ", _clean_text(text).lower()).strip()


def _chunk_preference_key(chunk: dict[str, Any]) -> tuple[float, float, float, float]:
    rerank_score = float(chunk.get("rerank_score") or 0.0)
    hybrid_score = float(chunk.get("hybrid_score") or 0.0)

    distance = chunk.get("distance")
    distance_value = float(distance) if distance is not None else float("inf")

    position = chunk.get("rerank_position")
    if position is None:
        position = chunk.get("hybrid_position")
    if position is None:
        position = chunk.get("retrieval_position")
    position_value = float(position or 10**6)

    return (-rerank_score, -hybrid_score, distance_value, position_value)


def normalize_chunk_text(chunk: dict[str, Any]) -> dict[str, Any]:
    normalized_chunk = dict(chunk)
    normalized_chunk["text"] = _clean_text(chunk.get("text", ""))

    metadata = dict(chunk.get("metadata") or {})
    metadata["topic"] = normalize_topic(metadata.get("topic") or "unknown") or "unknown"
    normalized_chunk["metadata"] = metadata
    return normalized_chunk


def deduplicate_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_chunks = []
    for raw_chunk in chunks:
        normalized_chunk = normalize_chunk_text(raw_chunk)
        if normalized_chunk.get("text"):
            normalized_chunks.append(normalized_chunk)

    deduplicated_chunks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_texts: set[str] = set()
    for normalized_chunk in sorted(normalized_chunks, key=_chunk_preference_key):
        chunk_id = str(normalized_chunk.get("id") or "").strip()
        text_key = _normalized_text_key(normalized_chunk.get("text", ""))

        if chunk_id and chunk_id in seen_ids:
            continue
        if text_key and text_key in seen_texts:
            continue

        deduplicated_chunks.append(normalized_chunk)
        if chunk_id:
            seen_ids.add(chunk_id)
        if text_key:
            seen_texts.add(text_key)

    return deduplicated_chunks


def group_chunks_by_topic(chunks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped_chunks: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        topic = normalize_topic(metadata.get("topic") or "unknown") or "unknown"
        grouped_chunks.setdefault(topic, []).append(chunk)

    for topic_chunks in grouped_chunks.values():
        topic_chunks.sort(key=_chunk_preference_key)

    return grouped_chunks


def summarize_topic_context(
    topic: str,
    chunks: list[dict[str, Any]],
    *,
    max_chunks: int = 2,
) -> dict[str, Any]:
    key_chunks = []
    for chunk in chunks[:max_chunks]:
        metadata = chunk.get("metadata") or {}
        key_chunks.append(
            {
                "id": chunk.get("id"),
                "text": chunk.get("text", ""),
                "chunk_index": metadata.get("chunk_index"),
                "source": metadata.get("source"),
                "scores": {
                    "distance": chunk.get("distance"),
                    "rerank_score": chunk.get("rerank_score"),
                    "hybrid_score": chunk.get("hybrid_score"),
                },
            }
        )

    return {
        "topic": topic,
        "chunk_count": len(chunks),
        "key_chunks": key_chunks,
    }


def _expected_topics_for_question(question: str, is_comparison: bool) -> list[str]:
    if not is_comparison:
        return []

    comparison_terms = normalize_topics(extract_comparison_terms(question))
    return normalize_topics(
        [
            normalize_comparison_term_to_topic(term)
            for term in comparison_terms
            if normalize_comparison_term_to_topic(term)
        ]
    )


def build_structured_context(
    chunks: list[dict[str, Any]],
    question: str,
    is_comparison: bool = False,
) -> dict[str, Any]:
    raw_chunk_count = len(chunks)
    deduplicated_chunks = deduplicate_chunks(chunks)
    grouped_chunks = group_chunks_by_topic(deduplicated_chunks)
    grouped_topics = list(grouped_chunks.keys())
    expected_topics = _expected_topics_for_question(question, is_comparison)

    if is_comparison:
        topic_order = [topic for topic in expected_topics if topic in grouped_chunks]
        topic_order.extend(topic for topic in grouped_topics if topic not in topic_order)
        topics = [
            summarize_topic_context(topic, grouped_chunks[topic], max_chunks=2)
            for topic in topic_order
        ]
        structured_context = {
            "mode": "comparison",
            "question": question,
            "expected_topics": expected_topics,
            "structured_topics": [topic_block["topic"] for topic_block in topics],
            "raw_chunk_count": raw_chunk_count,
            "deduped_chunk_count": len(deduplicated_chunks),
            "topics": topics,
        }
    else:
        primary_topic = grouped_topics[0] if grouped_topics else "unknown"
        structured_context = {
            "mode": "standard",
            "question": question,
            "primary_topic": primary_topic,
            "structured_topics": grouped_topics,
            "raw_chunk_count": raw_chunk_count,
            "deduped_chunk_count": len(deduplicated_chunks),
            "chunks": [
                {
                    "id": chunk.get("id"),
                    "text": chunk.get("text", ""),
                    "chunk_index": (chunk.get("metadata") or {}).get("chunk_index"),
                    "source": (chunk.get("metadata") or {}).get("source"),
                    "topic": (chunk.get("metadata") or {}).get("topic", "unknown"),
                    "scores": {
                        "distance": chunk.get("distance"),
                        "rerank_score": chunk.get("rerank_score"),
                        "hybrid_score": chunk.get("hybrid_score"),
                    },
                }
                for chunk in deduplicated_chunks[:3]
            ],
        }

    logger.info(
        "context structuring | raw=%d deduped=%d topics=%s mode=%s",
        raw_chunk_count,
        len(deduplicated_chunks),
        structured_context.get("structured_topics") or [structured_context.get("primary_topic")],
        structured_context["mode"],
    )
    return structured_context


def format_structured_context_for_prompt(structured_context: dict[str, Any]) -> str:
    if not structured_context:
        return "No structured context available."

    if structured_context.get("mode") == "comparison":
        topic_sections = []
        for topic_block in structured_context.get("topics", []):
            chunk_lines = []
            for index, chunk in enumerate(topic_block.get("key_chunks", []), start=1):
                source = chunk.get("source") or "unknown"
                chunk_lines.append(
                    f"- Chunk {index} | Source: {source}\n  {chunk.get('text', '')}"
                )
            section_body = "\n".join(chunk_lines) if chunk_lines else "- No chunk evidence available."
            topic_sections.append(f"Topic: {topic_block.get('topic', 'unknown')}\n{section_body}")
        return "\n\n".join(topic_sections) if topic_sections else "No structured context available."

    primary_topic = structured_context.get("primary_topic") or "unknown"
    chunk_lines = []
    for index, chunk in enumerate(structured_context.get("chunks", []), start=1):
        source = chunk.get("source") or "unknown"
        chunk_lines.append(
            f"- Chunk {index} | Source: {source}\n  {chunk.get('text', '')}"
        )

    if not chunk_lines:
        return f"Primary Topic: {primary_topic}\n- No chunk evidence available."

    return f"Primary Topic: {primary_topic}\n" + "\n".join(chunk_lines)
