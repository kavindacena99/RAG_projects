import logging
import os

from .chroma_service import (
    add_note_chunks,
    get_active_collection_name,
    query_similar_chunks,
)
from .chunking_service import semantic_chunk_pipeline
from .hybrid_search_service import rank_hybrid_candidates
from .llm_service import generate_answer, generate_embedding, get_llm_provider
from .query_analysis_service import (
    extract_comparison_terms,
    is_comparison_question,
    normalize_comparison_term_to_topic,
)
from .reranking_service import (
    rerank_candidate_chunks,
    select_balanced_final_chunks,
)
from rag.utils.topic_normalizer import normalize_topic, normalize_topics

logger = logging.getLogger("rag.pipeline")

def _build_chunk_preview(text: str, limit: int = 100) -> str:
    clean_text = (text or "").strip()
    if len(clean_text) <= limit:
        return clean_text
    return f"{clean_text[:limit]}..."


def _parse_top_k() -> int:
    raw_value = os.getenv("RAG_TOP_K", "3")
    try:
        top_k = int(raw_value)
    except (TypeError, ValueError):
        top_k = 3
    return max(top_k, 1)


def _parse_retrieve_k() -> int:
    raw_value = os.getenv("RAG_RETRIEVE_K", "8")
    try:
        retrieve_k = int(raw_value)
    except (TypeError, ValueError):
        retrieve_k = 8
    return max(retrieve_k, 1)


def _parse_final_top_n() -> int:
    raw_value = os.getenv("RAG_FINAL_TOP_N", str(_parse_top_k()))
    try:
        final_top_n = int(raw_value)
    except (TypeError, ValueError):
        final_top_n = _parse_top_k()
    return max(final_top_n, 1)


def _is_reranking_enabled() -> bool:
    return os.getenv("RAG_ENABLE_RERANKING", "true").strip().lower() == "true"


def _is_hybrid_search_enabled() -> bool:
    return os.getenv("RAG_ENABLE_HYBRID_SEARCH", "true").strip().lower() == "true"


def _parse_float_env(var_name: str, default: float) -> float:
    raw_value = os.getenv(var_name, str(default))
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return float(default)


def _parse_hybrid_vector_weight() -> float:
    return max(_parse_float_env("RAG_HYBRID_VECTOR_WEIGHT", 0.7), 0.0)


def _parse_hybrid_keyword_weight() -> float:
    return max(_parse_float_env("RAG_HYBRID_KEYWORD_WEIGHT", 0.3), 0.0)


def _parse_hybrid_candidate_k(retrieve_k: int) -> int:
    raw_value = os.getenv("RAG_HYBRID_CANDIDATE_K", str(max(retrieve_k, 8)))
    try:
        candidate_k = int(raw_value)
    except (TypeError, ValueError):
        candidate_k = max(retrieve_k, 8)
    return max(candidate_k, retrieve_k, 1)


def ingest_note(
    title: str,
    content: str,
    topic: str | None = None,
    source: str | None = None,
) -> dict:
    clean_title = (title or "").strip()
    clean_content = (content or "").strip()

    if not clean_title:
        raise ValueError("title is required.")
    if not clean_content:
        raise ValueError("content is required.")

    logger.info(
        "manual ingest started | title=%s content_chars=%d chunking_strategy=semantic",
        clean_title,
        len(clean_content),
    )

    chunks = semantic_chunk_pipeline(clean_content)
    if not chunks:
        raise ValueError("No chunks generated from content.")

    storage_result = add_note_chunks(
        title=clean_title,
        chunks=chunks,
        topic=topic,
        source=source,
    )

    response_chunks = []
    for index, chunk_id in enumerate(storage_result["ids"]):
        chunk_text_value = storage_result["documents"][index]
        metadata = storage_result["metadatas"][index]
        response_chunks.append(
            {
                "id": chunk_id,
                "index": index,
                "text_preview": _build_chunk_preview(chunk_text_value),
                "metadata": metadata,
            }
        )

    logger.info(
        "manual ingest completed | title=%s chunks_stored=%d",
        storage_result["title"],
        len(response_chunks),
    )

    return {
        "message": "Note ingested, embedded, and stored successfully",
        "chunking_strategy": "semantic",
        "provider": get_llm_provider(),
        "collection": storage_result["collection"],
        "title": storage_result["title"],
        "topic": storage_result["topic"],
        "source": storage_result["source"],
        "total_chunks": len(response_chunks),
        "total_chunks_generated": storage_result["total_chunks_generated"],
        "new_chunks_stored": storage_result["new_chunks_stored"],
        "duplicate_chunks_skipped": storage_result["duplicate_chunks_skipped"],
        "chunks": response_chunks,
    }


def _normalize_chroma_results(query_results: dict) -> list[dict]:
    ids_list = query_results.get("ids") or [[]]
    documents_list = query_results.get("documents") or [[]]
    metadatas_list = query_results.get("metadatas") or [[]]
    distances_list = query_results.get("distances") or [[]]

    ids = ids_list[0] if ids_list else []
    documents = documents_list[0] if documents_list else []
    metadatas = metadatas_list[0] if metadatas_list else []
    distances = distances_list[0] if distances_list else []

    normalized = []
    seen_chunk_ids = set()
    seen_texts = set()
    for index, chunk_id in enumerate(ids):
        normalized_text = " ".join(
            str(documents[index] if index < len(documents) else "").split()
        ).strip()

        if chunk_id in seen_chunk_ids:
            continue
        if normalized_text and normalized_text in seen_texts:
            continue

        chunk_payload = {
            "id": chunk_id,
            "text": documents[index] if index < len(documents) else "",
            "metadata": dict(metadatas[index] if index < len(metadatas) else {}),
            "retrieval_position": index + 1,
        }
        metadata = chunk_payload["metadata"]
        if metadata.get("topic"):
            metadata["topic"] = normalize_topic(metadata.get("topic"))

        if index < len(distances):
            distance_value = distances[index]
            chunk_payload["distance"] = (
                float(distance_value) if distance_value is not None else None
            )

        seen_chunk_ids.add(chunk_id)
        if normalized_text:
            seen_texts.add(normalized_text)
        normalized.append(chunk_payload)

    return normalized


def _annotate_retrieval_results(
    chunks: list[dict],
    query_text: str,
    retrieval_label: str,
) -> list[dict]:
    annotated_chunks = []
    for chunk in chunks:
        updated_chunk = dict(chunk)
        updated_chunk["retrieval_query"] = query_text
        updated_chunk["retrieval_label"] = retrieval_label
        annotated_chunks.append(updated_chunk)
    return annotated_chunks


def _extract_unique_topics(chunks: list[dict]) -> list[str]:
    unique_topics = []
    seen = set()

    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        topic = normalize_topic((metadata.get("topic") or "").strip())
        if not topic:
            continue

        normalized = topic.lower()
        if normalized in seen:
            continue

        seen.add(normalized)
        unique_topics.append(topic)

    return unique_topics


def _assign_fallback_rerank_positions(chunks: list[dict]) -> list[dict]:
    fallback_chunks = [dict(chunk) for chunk in chunks]
    for position, chunk in enumerate(fallback_chunks, start=1):
        chunk["rerank_position"] = position
    return fallback_chunks


def _chunk_sort_key(chunk: dict) -> tuple:
    distance = chunk.get("distance")
    if distance is None:
        distance = float("inf")

    retrieval_position = chunk.get("retrieval_position")
    if retrieval_position is None:
        retrieval_position = 10**6

    return (float(distance), int(retrieval_position))


def merge_and_diversify_chunks(
    chunks: list[dict],
    max_candidates: int = 8,
) -> list[dict]:
    if max_candidates <= 0 or not chunks:
        return []

    deduplicated_chunks = []
    seen_ids = set()
    seen_texts = set()

    for chunk in sorted(chunks, key=_chunk_sort_key):
        chunk_id = str(chunk.get("id", "")).strip()
        chunk_text = " ".join((chunk.get("text") or "").split())

        if chunk_id and chunk_id in seen_ids:
            continue
        if chunk_text and chunk_text in seen_texts:
            continue

        if chunk_id:
            seen_ids.add(chunk_id)
        if chunk_text:
            seen_texts.add(chunk_text)

        deduplicated_chunks.append(dict(chunk))

    topic_groups = {}
    topic_order = []
    for chunk in deduplicated_chunks:
        metadata = chunk.get("metadata") or {}
        topic = normalize_topic((metadata.get("topic") or "unknown").strip() or "unknown")

        if topic not in topic_groups:
            topic_groups[topic] = []
            topic_order.append(topic)
        topic_groups[topic].append(chunk)

    diversified_chunks = []
    used_ids = set()

    for topic in topic_order:
        if len(diversified_chunks) >= max_candidates:
            break

        topic_chunks = sorted(topic_groups[topic], key=_chunk_sort_key)
        best_chunk = topic_chunks[0]
        chunk_id = str(best_chunk.get("id", "")).strip()
        if chunk_id and chunk_id in used_ids:
            continue

        diversified_chunks.append(best_chunk)
        if chunk_id:
            used_ids.add(chunk_id)

    for chunk in deduplicated_chunks:
        if len(diversified_chunks) >= max_candidates:
            break

        chunk_id = str(chunk.get("id", "")).strip()
        if chunk_id and chunk_id in used_ids:
            continue

        diversified_chunks.append(chunk)
        if chunk_id:
            used_ids.add(chunk_id)

    return diversified_chunks[:max_candidates]


def _retrieve_chunks_for_query(query_text: str, top_k: int, retrieval_label: str) -> list[dict]:
    query_embedding = generate_embedding(query_text)
    if not query_embedding:
        raise RuntimeError(f"Embedding generation returned an empty vector for query: {query_text}")

    query_results = query_similar_chunks(query_embedding, top_k=top_k)
    normalized_chunks = _normalize_chroma_results(query_results)
    return _annotate_retrieval_results(normalized_chunks, query_text, retrieval_label)


def _run_standard_retrieval(clean_question: str, retrieve_k: int) -> tuple[list[dict], list[dict]]:
    retrieved_chunks_initial = _retrieve_chunks_for_query(
        clean_question,
        top_k=retrieve_k,
        retrieval_label="full_question",
    )
    return retrieved_chunks_initial, list(retrieved_chunks_initial)


def _run_comparison_aware_retrieval(
    clean_question: str,
    comparison_terms: list[str],
    retrieve_k: int,
) -> tuple[list[dict], list[dict]]:
    retrieved_chunks_initial = _retrieve_chunks_for_query(
        clean_question,
        top_k=retrieve_k,
        retrieval_label="full_question",
    )

    candidate_chunks = list(retrieved_chunks_initial)
    for comparison_term in comparison_terms:
        term_chunks = _retrieve_chunks_for_query(
            comparison_term,
            top_k=retrieve_k,
            retrieval_label="comparison_term",
        )
        candidate_chunks.extend(term_chunks)

    retrieved_chunks_diversified = merge_and_diversify_chunks(
        candidate_chunks,
        max_candidates=retrieve_k,
    )
    return retrieved_chunks_initial, retrieved_chunks_diversified


def retrieve_context_for_question(question: str, top_k: int | None = None) -> dict:
    clean_question = (question or "").strip()
    if not clean_question:
        raise ValueError("question is required.")

    retrieve_k = _parse_retrieve_k()
    final_top_n = top_k or _parse_final_top_n()
    reranking_enabled = _is_reranking_enabled()
    hybrid_search_enabled = _is_hybrid_search_enabled()
    hybrid_vector_weight = _parse_hybrid_vector_weight()
    hybrid_keyword_weight = _parse_hybrid_keyword_weight()
    hybrid_candidate_k = _parse_hybrid_candidate_k(retrieve_k)
    retrieval_top_k = hybrid_candidate_k if hybrid_search_enabled else retrieve_k
    comparison_question_detected = is_comparison_question(clean_question)
    comparison_terms = normalize_topics(extract_comparison_terms(clean_question))
    retrieval_strategy = "standard"
    logger.info(
        "ask flow started | question_chars=%d retrieve_k=%d final_top_n=%d reranking_enabled=%s hybrid_search_enabled=%s",
        len(clean_question),
        retrieval_top_k,
        final_top_n,
        reranking_enabled,
        hybrid_search_enabled,
    )
    logger.info("normalized comparison terms | terms=%s", comparison_terms)

    try:
        if comparison_question_detected and comparison_terms:
            retrieval_strategy = "comparison_aware"
            retrieved_chunks_initial, retrieved_chunks_diversified = (
                _run_comparison_aware_retrieval(
                    clean_question,
                    comparison_terms,
                    retrieve_k=retrieval_top_k,
                )
            )
        else:
            retrieved_chunks_initial, retrieved_chunks_diversified = _run_standard_retrieval(
                clean_question,
                retrieve_k=retrieval_top_k,
            )
    except Exception as exc:
        if comparison_question_detected:
            logger.warning(
                "comparison-aware retrieval failed, falling back to standard retrieval | error=%s",
                exc,
            )
            retrieval_strategy = "standard_fallback"
            retrieved_chunks_initial, retrieved_chunks_diversified = _run_standard_retrieval(
                clean_question,
                retrieve_k=retrieval_top_k,
            )
        else:
            raise

    logger.info(
        "ask retrieval completed | strategy=%s retrieved_chunks_initial=%d retrieved_chunks_diversified=%d",
        retrieval_strategy,
        len(retrieved_chunks_initial),
        len(retrieved_chunks_diversified),
    )

    reranking_fallback_used = False
    reranking_error = None
    hybrid_search_fallback_used = False
    expected_comparison_topics = []
    available_candidate_topics = []
    missing_expected_topics = []
    balanced_selection_applied = False
    balanced_selection_fallback_used = False
    filtered_out_candidate_ids = []
    hybrid_filtered_out_candidate_ids = []
    retrieved_chunks_hybrid_ranked = list(retrieved_chunks_diversified)

    if hybrid_search_enabled:
        try:
            hybrid_result = rank_hybrid_candidates(
                clean_question,
                retrieved_chunks_diversified,
                vector_weight=hybrid_vector_weight,
                keyword_weight=hybrid_keyword_weight,
            )
            ranked_hybrid_chunks = hybrid_result["ranked_chunks"]
            hybrid_filtered_out_candidate_ids = hybrid_result["filtered_out_chunk_ids"]
            if ranked_hybrid_chunks:
                retrieved_chunks_hybrid_ranked = ranked_hybrid_chunks
            else:
                hybrid_search_fallback_used = True
                logger.warning(
                    "hybrid search returned no ranked candidates, using vector-only candidate order"
                )
        except Exception as exc:
            hybrid_search_fallback_used = True
            logger.warning(
                "hybrid search failed, using vector-only candidate order | error=%s",
                exc,
            )
            retrieved_chunks_hybrid_ranked = list(retrieved_chunks_diversified)

    if reranking_enabled:
        try:
            retrieved_chunks_reranked = rerank_candidate_chunks(
                clean_question,
                retrieved_chunks_hybrid_ranked,
            )
        except Exception as exc:
            reranking_fallback_used = True
            reranking_error = str(exc)
            logger.warning(
                "reranking failed, using retrieval order fallback | error=%s",
                reranking_error,
            )
            retrieved_chunks_reranked = _assign_fallback_rerank_positions(
                retrieved_chunks_hybrid_ranked
            )
    else:
        retrieved_chunks_reranked = _assign_fallback_rerank_positions(
            retrieved_chunks_hybrid_ranked
        )

    if comparison_question_detected and comparison_terms:
        balanced_selection_result = select_balanced_final_chunks(
            retrieved_chunks_reranked,
            comparison_terms=comparison_terms,
            final_top_n=final_top_n,
        )
        retrieved_chunks_final = balanced_selection_result["selected_chunks"]
        balanced_selection_applied = balanced_selection_result["balanced_selection_applied"]
        balanced_selection_fallback_used = balanced_selection_result[
            "balanced_selection_fallback_used"
        ]
        expected_comparison_topics = balanced_selection_result[
            "expected_comparison_topics"
        ]
        available_candidate_topics = balanced_selection_result[
            "available_candidate_topics"
        ]
        missing_expected_topics = balanced_selection_result["missing_expected_topics"]
        filtered_out_candidate_ids = balanced_selection_result["filtered_out_chunk_ids"]
    else:
        retrieved_chunks_final = retrieved_chunks_reranked[:final_top_n]
        expected_comparison_topics = normalize_topics(
            [
                normalize_comparison_term_to_topic(term)
                for term in comparison_terms
                if normalize_comparison_term_to_topic(term)
            ]
        )
        available_candidate_topics = _extract_unique_topics(retrieved_chunks_reranked)
        missing_expected_topics = [
            topic
            for topic in expected_comparison_topics
            if topic not in {normalize_topic(candidate_topic) for candidate_topic in available_candidate_topics}
        ]

    logger.info(
        "final selection topics | expected_topics=%s final_topics=%s",
        expected_comparison_topics,
        [normalize_topic((chunk.get('metadata') or {}).get('topic', '')) for chunk in retrieved_chunks_final],
    )

    return {
        "provider": get_llm_provider(),
        "collection": get_active_collection_name(),
        "question": clean_question,
        "comparison_question_detected": comparison_question_detected,
        "comparison_terms": comparison_terms,
        "retrieval_strategy": retrieval_strategy,
        "hybrid_search_enabled": hybrid_search_enabled,
        "hybrid_search_fallback_used": hybrid_search_fallback_used,
        "hybrid_vector_weight": hybrid_vector_weight,
        "hybrid_keyword_weight": hybrid_keyword_weight,
        "hybrid_candidate_count": len(retrieved_chunks_hybrid_ranked),
        "hybrid_filtered_out_candidate_ids": hybrid_filtered_out_candidate_ids,
        "reranking_enabled": reranking_enabled,
        "reranking_fallback_used": reranking_fallback_used,
        "reranking_error": reranking_error,
        "balanced_selection_applied": balanced_selection_applied,
        "balanced_selection_fallback_used": balanced_selection_fallback_used,
        "expected_comparison_topics": expected_comparison_topics,
        "available_candidate_topics": available_candidate_topics,
        "missing_expected_topics": missing_expected_topics,
        "filtered_out_candidate_ids": filtered_out_candidate_ids,
        "total_retrieved_initial": len(retrieved_chunks_initial),
        "total_retrieved_diversified": len(retrieved_chunks_diversified),
        "total_retrieved_hybrid_ranked": len(retrieved_chunks_hybrid_ranked),
        "total_retrieved_reranked": len(retrieved_chunks_reranked),
        "total_retrieved_final": len(retrieved_chunks_final),
        "unique_topics_initial": _extract_unique_topics(retrieved_chunks_initial),
        "unique_topics_diversified": _extract_unique_topics(retrieved_chunks_diversified),
        "unique_topics_hybrid_ranked": _extract_unique_topics(retrieved_chunks_hybrid_ranked),
        "unique_topics_reranked": _extract_unique_topics(retrieved_chunks_reranked),
        "unique_topics_final": _extract_unique_topics(retrieved_chunks_final),
        "retrieved_chunks_initial": retrieved_chunks_initial,
        "retrieved_chunks_diversified": retrieved_chunks_diversified,
        "retrieved_chunks_hybrid_ranked": retrieved_chunks_hybrid_ranked,
        "retrieved_chunks_reranked": retrieved_chunks_reranked,
        "retrieved_chunks_final": retrieved_chunks_final,
    }


def ask_question(question: str, top_k: int | None = None) -> dict:
    retrieval_result = retrieve_context_for_question(question=question, top_k=top_k)
    answer = generate_answer(
        retrieval_result["question"],
        retrieval_result["retrieved_chunks_final"],
        is_comparison=retrieval_result["comparison_question_detected"],
    )
    logger.info("ask flow completed | answer_chars=%d", len(answer))
    return {
        **retrieval_result,
        "answer": answer,
    }
