import logging
import re

from .llm_service import score_chunks_for_reranking
from .query_analysis_service import normalize_comparison_term_to_topic
from rag.utils.topic_normalizer import normalize_topic

logger = logging.getLogger("rag.pipeline")


def _get_chunk_topic(chunk: dict) -> str:
    metadata = chunk.get("metadata") or {}
    return normalize_topic(str(metadata.get("topic", "")).strip().lower())


def _normalize_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")


def _is_noisy_candidate(chunk: dict) -> bool:
    text = _normalize_text(chunk.get("text", ""))
    if not text:
        return True

    metadata = chunk.get("metadata") or {}
    topic = _normalize_label(normalize_topic(metadata.get("topic", "")))
    title = _normalize_label(metadata.get("title", ""))
    source = str(metadata.get("source", "")).strip().split("/")[-1].split(".")[0]
    source = _normalize_label(source)
    normalized_text = _normalize_label(text)

    if normalized_text and normalized_text in {topic, title, source}:
        return True

    word_count = len(text.split())
    if len(text) < 20 and word_count < 4:
        return True

    return False


def rerank_candidate_chunks(question: str, chunks: list[dict]) -> list[dict]:
    if not question or not question.strip():
        raise ValueError("question is required for reranking.")

    if not chunks:
        return []

    score_map = score_chunks_for_reranking(question, chunks)
    if not score_map:
        raise RuntimeError("Reranking returned no usable scores.")

    scored_chunks = []
    for index, chunk in enumerate(chunks):
        updated_chunk = dict(chunk)
        rerank_score = score_map.get(updated_chunk["id"])
        if rerank_score is None:
            rerank_score = 0.0

        updated_chunk["rerank_score"] = float(rerank_score)
        updated_chunk["_initial_index"] = index
        scored_chunks.append(updated_chunk)

    scored_chunks.sort(
        key=lambda chunk: (
            -chunk["rerank_score"],
            chunk.get("distance", float("inf")),
            chunk["_initial_index"],
        )
    )

    for position, chunk in enumerate(scored_chunks, start=1):
        chunk["rerank_position"] = position
        chunk.pop("_initial_index", None)

    return scored_chunks


def select_balanced_final_chunks(
    reranked_chunks: list[dict],
    comparison_terms: list[str],
    final_top_n: int = 3,
) -> dict:
    if final_top_n <= 0:
        raise ValueError("final_top_n must be greater than 0.")

    expected_topics = []
    seen_expected_topics = set()
    for comparison_term in comparison_terms:
        normalized_topic = normalize_comparison_term_to_topic(comparison_term)
        if not normalized_topic or normalized_topic in seen_expected_topics:
            continue
        seen_expected_topics.add(normalized_topic)
        expected_topics.append(normalized_topic)

    filtered_candidates = []
    filtered_out_chunk_ids = []
    for chunk in reranked_chunks:
        if _is_noisy_candidate(chunk):
            filtered_out_chunk_ids.append(chunk.get("id"))
            continue
        filtered_candidates.append(chunk)

    topic_groups = {}
    available_topics = []
    seen_available_topics = set()
    for chunk in filtered_candidates:
        topic = _get_chunk_topic(chunk)
        if not topic:
            continue
        topic_groups.setdefault(topic, []).append(chunk)
        if topic in seen_available_topics:
            continue
        seen_available_topics.add(topic)
        available_topics.append(topic)

    missing_expected_topics = [
        topic for topic in expected_topics if topic not in set(available_topics)
    ]

    if filtered_out_chunk_ids:
        logger.info(
            "balanced selection skipped noisy candidates | filtered_out=%d ids=%s",
            len(filtered_out_chunk_ids),
            filtered_out_chunk_ids,
        )

    if len(expected_topics) < 2:
        fallback_chunks = filtered_candidates[:final_top_n] or reranked_chunks[:final_top_n]
        logger.info(
            "balanced selection fallback used | expected_topics=%s available_topics=%s selected_chunks=%d",
            expected_topics,
            available_topics,
            len(fallback_chunks),
        )
        return {
            "selected_chunks": fallback_chunks,
            "balanced_selection_applied": False,
            "balanced_selection_fallback_used": True,
            "expected_comparison_topics": expected_topics,
            "available_candidate_topics": available_topics,
            "missing_expected_topics": missing_expected_topics,
            "filtered_out_chunk_ids": filtered_out_chunk_ids,
        }

    selected_chunks = []
    used_chunk_ids = set()

    for expected_topic in expected_topics:
        for chunk in topic_groups.get(expected_topic, []):
            chunk_id = str(chunk.get("id", "")).strip()
            if not chunk_id or chunk_id in used_chunk_ids:
                continue
            selected_chunks.append(chunk)
            used_chunk_ids.add(chunk_id)
            break

    if len(selected_chunks) < len(expected_topics):
        fallback_chunks = []
        used_chunk_ids.clear()
        for chunk in filtered_candidates[:final_top_n] or reranked_chunks[:final_top_n]:
            chunk_id = str(chunk.get("id", "")).strip()
            if not chunk_id or chunk_id in used_chunk_ids:
                continue
            fallback_chunks.append(chunk)
            used_chunk_ids.add(chunk_id)

        logger.info(
            "balanced selection fallback used | expected_topics=%s available_topics=%s selected_chunks=%d",
            expected_topics,
            available_topics,
            len(fallback_chunks),
        )
        return {
            "selected_chunks": fallback_chunks,
            "balanced_selection_applied": True,
            "balanced_selection_fallback_used": True,
            "expected_comparison_topics": expected_topics,
            "available_candidate_topics": available_topics,
            "missing_expected_topics": missing_expected_topics,
            "filtered_out_chunk_ids": filtered_out_chunk_ids,
        }

    for chunk in filtered_candidates:
        if len(selected_chunks) >= final_top_n:
            break

        chunk_id = str(chunk.get("id", "")).strip()
        if not chunk_id or chunk_id in used_chunk_ids:
            continue

        selected_chunks.append(chunk)
        used_chunk_ids.add(chunk_id)

    logger.info(
        "balanced selection applied | expected_topics=%s final_topics=%s selected_chunks=%d",
        expected_topics,
        [_get_chunk_topic(chunk) for chunk in selected_chunks[:final_top_n]],
        len(selected_chunks[:final_top_n]),
    )

    return {
        "selected_chunks": selected_chunks[:final_top_n],
        "balanced_selection_applied": True,
        "balanced_selection_fallback_used": False,
        "expected_comparison_topics": expected_topics,
        "available_candidate_topics": available_topics,
        "missing_expected_topics": missing_expected_topics,
        "filtered_out_chunk_ids": filtered_out_chunk_ids,
    }


def rerank_chunks(
    question: str,
    chunks: list[dict],
    final_top_n: int = 3,
) -> list[dict]:
    if not question or not question.strip():
        raise ValueError("question is required for reranking.")

    if final_top_n <= 0:
        raise ValueError("final_top_n must be greater than 0.")

    if not chunks:
        return []
    scored_chunks = rerank_candidate_chunks(question, chunks)
    final_chunks = scored_chunks[:final_top_n]

    logger.info(
        "reranking completed | candidate_chunks=%d final_chunks=%d",
        len(chunks),
        len(final_chunks),
    )

    return final_chunks
