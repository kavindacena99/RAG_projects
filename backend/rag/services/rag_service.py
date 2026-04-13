import logging
import os

from .chroma_service import (
    add_note_chunks,
    get_active_collection_name,
    query_similar_chunks,
)
from .chunking_service import chunk_text
from .llm_service import generate_answer, generate_embedding, get_llm_provider
from .reranking_service import rerank_chunks

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


def ingest_note(
    title: str,
    content: str,
    topic: str | None = None,
    source: str | None = None,
    chunk_size: int = 500,
    overlap: int = 0,
) -> dict:
    clean_title = (title or "").strip()
    clean_content = (content or "").strip()

    if not clean_title:
        raise ValueError("title is required.")
    if not clean_content:
        raise ValueError("content is required.")

    logger.info(
        "manual ingest started | title=%s content_chars=%d chunk_size=%d overlap=%d",
        clean_title,
        len(clean_content),
        chunk_size,
        overlap,
    )

    chunks = chunk_text(clean_content, chunk_size=chunk_size, overlap=overlap)
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
        "provider": get_llm_provider(),
        "collection": storage_result["collection"],
        "title": storage_result["title"],
        "topic": storage_result["topic"],
        "source": storage_result["source"],
        "total_chunks": len(response_chunks),
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
    for index, chunk_id in enumerate(ids):
        chunk_payload = {
            "id": chunk_id,
            "text": documents[index] if index < len(documents) else "",
            "metadata": metadatas[index] if index < len(metadatas) else {},
            "retrieval_position": index + 1,
        }

        if index < len(distances):
            distance_value = distances[index]
            chunk_payload["distance"] = (
                float(distance_value) if distance_value is not None else None
            )

        normalized.append(chunk_payload)

    return normalized


def ask_question(question: str, top_k: int | None = None) -> dict:
    clean_question = (question or "").strip()
    if not clean_question:
        raise ValueError("question is required.")

    retrieve_k = _parse_retrieve_k()
    final_top_n = top_k or _parse_final_top_n()
    reranking_enabled = _is_reranking_enabled()
    logger.info(
        "ask flow started | question_chars=%d retrieve_k=%d final_top_n=%d reranking_enabled=%s",
        len(clean_question),
        retrieve_k,
        final_top_n,
        reranking_enabled,
    )
    question_embedding = generate_embedding(clean_question)
    if not question_embedding:
        raise RuntimeError("Question embedding generation returned an empty vector.")

    query_results = query_similar_chunks(question_embedding, top_k=retrieve_k)
    retrieved_chunks_initial = _normalize_chroma_results(query_results)
    logger.info(
        "ask retrieval completed | retrieved_chunks_initial=%d",
        len(retrieved_chunks_initial),
    )

    reranking_fallback_used = False
    reranking_error = None

    if reranking_enabled:
        try:
            retrieved_chunks_final = rerank_chunks(
                clean_question,
                retrieved_chunks_initial,
                final_top_n=final_top_n,
            )
        except Exception as exc:
            reranking_fallback_used = True
            reranking_error = str(exc)
            logger.warning(
                "reranking failed, using retrieval order fallback | error=%s",
                reranking_error,
            )
            retrieved_chunks_final = [
                dict(chunk) for chunk in retrieved_chunks_initial[:final_top_n]
            ]
            for position, chunk in enumerate(retrieved_chunks_final, start=1):
                chunk["rerank_position"] = position
    else:
        retrieved_chunks_final = [
            dict(chunk) for chunk in retrieved_chunks_initial[:final_top_n]
        ]
        for position, chunk in enumerate(retrieved_chunks_final, start=1):
            chunk["rerank_position"] = position

    answer = generate_answer(clean_question, retrieved_chunks_final)
    logger.info("ask flow completed | answer_chars=%d", len(answer))

    return {
        "provider": get_llm_provider(),
        "collection": get_active_collection_name(),
        "question": clean_question,
        "reranking_enabled": reranking_enabled,
        "reranking_fallback_used": reranking_fallback_used,
        "reranking_error": reranking_error,
        "total_retrieved_initial": len(retrieved_chunks_initial),
        "total_retrieved_final": len(retrieved_chunks_final),
        "retrieved_chunks_initial": retrieved_chunks_initial,
        "retrieved_chunks_final": retrieved_chunks_final,
        "answer": answer,
    }
