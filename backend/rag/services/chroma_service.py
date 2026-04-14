import hashlib
import logging
import os
import re
from pathlib import Path

from django.conf import settings

from .llm_service import generate_embedding, get_embedding_model_name, get_llm_provider
from rag.utils.topic_normalizer import normalize_topic

logger = logging.getLogger("rag.pipeline")


def _get_chroma_module():
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError(
            "chromadb is not installed. Install dependencies from requirements.txt."
        ) from exc

    return chromadb


def _get_persist_dir() -> str:
    configured_path = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    persist_path = Path(configured_path)

    if not persist_path.is_absolute():
        persist_path = Path(settings.BASE_DIR) / persist_path

    persist_path.mkdir(parents=True, exist_ok=True)
    return str(persist_path)


def _build_default_source(title: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_").lower()
    if not normalized:
        normalized = "study_note"
    return normalized


def _sanitize_id_part(raw_value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw_value).strip("_")
    if not normalized:
        return "chunk"
    return normalized


def _normalize_chunk_text(chunk_text: str) -> str:
    return " ".join((chunk_text or "").split()).strip()


def _build_stable_chunk_id(
    source: str,
    chunk_index: int,
    chunk_text: str,
) -> str:
    safe_source = _sanitize_id_part(source)
    normalized_text = _normalize_chunk_text(chunk_text)
    chunk_hash = hashlib.sha256(
        f"{source}::{chunk_index}::{normalized_text}".encode("utf-8")
    ).hexdigest()[:16]
    return f"{safe_source}_{chunk_index}_{chunk_hash}"


def get_active_collection_name() -> str:
    base_collection_name = os.getenv("CHROMA_COLLECTION_NAME", "study_notes").strip()
    if not base_collection_name:
        base_collection_name = "study_notes"

    provider = get_llm_provider()
    embedding_model = get_embedding_model_name()
    safe_model_name = _sanitize_id_part(embedding_model.lower())

    return f"{base_collection_name}_{provider}_{safe_model_name}"


def get_collection():
    chromadb = _get_chroma_module()
    persist_dir = _get_persist_dir()
    collection_name = get_active_collection_name()

    try:
        client = chromadb.PersistentClient(path=persist_dir)
        collection = client.get_or_create_collection(name=collection_name)
    except Exception as exc:
        raise RuntimeError(f"Chroma initialization failed: {exc}") from exc

    return collection


def get_collection_records(
    include: list[str] | None = None,
) -> dict:
    collection = get_collection()
    include_fields = include or ["documents", "metadatas"]

    try:
        total_records = collection.count()
        if total_records == 0:
            return {
                "ids": [],
                "documents": [],
                "metadatas": [],
            }

        return collection.get(
            limit=total_records,
            include=include_fields,
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch collection records from Chroma: {exc}") from exc


def delete_chunks_by_ids(chunk_ids: list[str]) -> int:
    clean_ids = [str(chunk_id).strip() for chunk_id in chunk_ids if str(chunk_id).strip()]
    if not clean_ids:
        return 0

    collection = get_collection()
    try:
        collection.delete(ids=clean_ids)
    except Exception as exc:
        raise RuntimeError(f"Failed to delete chunks from Chroma: {exc}") from exc

    return len(clean_ids)


def _get_existing_chunk_ids(collection, candidate_ids: list[str]) -> set[str]:
    if not candidate_ids:
        return set()

    try:
        existing_records = collection.get(ids=candidate_ids, include=[])
    except Exception as exc:
        raise RuntimeError(f"Failed to check existing chunk ids in Chroma: {exc}") from exc

    existing_ids = existing_records.get("ids") or []
    return {str(chunk_id).strip() for chunk_id in existing_ids if str(chunk_id).strip()}


def add_note_chunks(
    title: str,
    chunks: list[str],
    topic: str | None = None,
    source: str | None = None,
) -> dict:
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("title is required.")

    clean_chunks = [chunk for chunk in chunks if (chunk or "").strip()]
    if not clean_chunks:
        raise ValueError("No valid chunks found to store.")

    clean_topic = normalize_topic((topic or "").strip() or "general")
    clean_source = (source or "").strip() or _build_default_source(clean_title)
    collection = get_collection()

    candidate_chunks = []
    candidate_ids = []
    for chunk_index, chunk_text in enumerate(clean_chunks):
        chunk_id = _build_stable_chunk_id(
            source=clean_source,
            chunk_index=chunk_index,
            chunk_text=chunk_text,
        )
        metadata = {
            "title": clean_title,
            "topic": clean_topic,
            "source": clean_source,
            "chunk_index": chunk_index,
        }
        candidate_chunks.append(
            {
                "id": chunk_id,
                "text": chunk_text,
                "metadata": metadata,
            }
        )
        candidate_ids.append(chunk_id)

    existing_chunk_ids = _get_existing_chunk_ids(collection, candidate_ids)

    ids = []
    documents = []
    metadatas = []
    embeddings = []
    duplicate_ids = []

    for candidate_chunk in candidate_chunks:
        chunk_id = candidate_chunk["id"]
        if chunk_id in existing_chunk_ids:
            duplicate_ids.append(chunk_id)
            continue

        embedding = generate_embedding(candidate_chunk["text"])
        if not embedding:
            raise RuntimeError(
                "Embedding generation returned empty vector for one of the generated chunks."
            )

        ids.append(chunk_id)
        documents.append(candidate_chunk["text"])
        metadatas.append(candidate_chunk["metadata"])
        embeddings.append(embedding)

    if ids:
        try:
            collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to store note chunks in Chroma: {exc}") from exc

    logger.info(
        "chunk storage completed | source=%s chunks_generated=%d new_chunks_stored=%d duplicate_chunks_skipped=%d",
        clean_source,
        len(clean_chunks),
        len(ids),
        len(duplicate_ids),
    )

    return {
        "collection": get_active_collection_name(),
        "title": clean_title,
        "topic": clean_topic,
        "source": clean_source,
        "total_chunks_generated": len(clean_chunks),
        "new_chunks_stored": len(ids),
        "duplicate_chunks_skipped": len(duplicate_ids),
        "ids": ids,
        "documents": documents,
        "metadatas": metadatas,
        "duplicate_ids": duplicate_ids,
    }


def query_similar_chunks(query_embedding: list[float], top_k: int = 5) -> dict:
    if not query_embedding:
        raise ValueError("query_embedding cannot be empty.")
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0.")

    collection = get_collection()

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        raise RuntimeError(f"Chroma query failed: {exc}") from exc

    return results
