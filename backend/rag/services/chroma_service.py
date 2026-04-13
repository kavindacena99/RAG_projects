import os
import re
from pathlib import Path
from uuid import uuid4

from django.conf import settings

from .llm_service import generate_embedding, get_embedding_model_name, get_llm_provider


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

    clean_topic = (topic or "").strip() or "general"
    clean_source = (source or "").strip() or _build_default_source(clean_title)
    batch_id = uuid4().hex[:8]
    safe_source_for_id = _sanitize_id_part(clean_source)

    ids = []
    documents = []
    metadatas = []
    embeddings = []

    for chunk_index, chunk_text in enumerate(clean_chunks):
        chunk_id = f"{safe_source_for_id}_{batch_id}_{chunk_index}"
        metadata = {
            "title": clean_title,
            "topic": clean_topic,
            "source": clean_source,
            "chunk_index": chunk_index,
        }

        embedding = generate_embedding(chunk_text)
        if not embedding:
            raise RuntimeError(
                f"Embedding generation returned empty vector for chunk {chunk_index}."
            )

        ids.append(chunk_id)
        documents.append(chunk_text)
        metadatas.append(metadata)
        embeddings.append(embedding)

    collection = get_collection()
    try:
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to store note chunks in Chroma: {exc}") from exc

    return {
        "collection": get_active_collection_name(),
        "title": clean_title,
        "topic": clean_topic,
        "source": clean_source,
        "ids": ids,
        "documents": documents,
        "metadatas": metadatas,
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
