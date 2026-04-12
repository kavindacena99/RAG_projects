import os
import logging

from .chroma_service import add_note_chunks, query_similar_chunks
from .chunking_service import chunk_text
from .gemini_service import generate_answer, generate_embedding

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

    effective_top_k = top_k or _parse_top_k()
    logger.info(
        "ask flow started | question_chars=%d top_k=%d",
        len(clean_question),
        effective_top_k,
    )
    question_embedding = generate_embedding(clean_question)
    if not question_embedding:
        raise RuntimeError("Question embedding generation returned an empty vector.")

    query_results = query_similar_chunks(question_embedding, top_k=effective_top_k)
    retrieved_chunks = _normalize_chroma_results(query_results)
    logger.info(
        "ask retrieval completed | retrieved_chunks=%d",
        len(retrieved_chunks),
    )
    answer = generate_answer(clean_question, retrieved_chunks)
    logger.info("ask flow completed | answer_chars=%d", len(answer))

    return {
        "question": clean_question,
        "answer": answer,
        "retrieved_chunks": retrieved_chunks,
        "total_retrieved": len(retrieved_chunks),
    }
