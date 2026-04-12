import logging
import os
from pathlib import Path

from django.conf import settings

from .chroma_service import add_note_chunks
from .chunking_service import chunk_text

logger = logging.getLogger(__name__)
SUPPORTED_EXTENSIONS = {".txt"}


def resolve_knowledge_base_path(base_path: str | None = None) -> Path:
    configured_base_path = (base_path or os.getenv("KNOWLEDGE_BASE_DIR", "../knowledge")).strip()
    if not configured_base_path:
        configured_base_path = "../knowledge"

    candidate_path = Path(configured_base_path)
    if not candidate_path.is_absolute():
        candidate_path = Path(settings.BASE_DIR) / candidate_path

    return candidate_path.resolve()


def scan_knowledge_files(base_path: str) -> list[Path]:
    base_dir = resolve_knowledge_base_path(base_path)

    if not base_dir.exists():
        raise FileNotFoundError(f"Knowledge directory does not exist: {base_dir}")

    if not base_dir.is_dir():
        raise NotADirectoryError(f"Knowledge path is not a directory: {base_dir}")

    file_paths = []
    for candidate in base_dir.rglob("*"):
        if not candidate.is_file():
            continue

        if candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
            file_paths.append(candidate)
        else:
            logger.info("Skipping unsupported file type: %s", candidate)

    return sorted(file_paths)


def read_text_file(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as file_handle:
        return file_handle.read()


def _to_project_relative_path(path: Path) -> str:
    project_root = Path(settings.BASE_DIR).parent
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _derive_topic_and_source(file_path: Path, base_dir: Path) -> tuple[str, str]:
    relative_from_base = file_path.relative_to(base_dir)
    topic = relative_from_base.parts[0] if len(relative_from_base.parts) > 1 else "general"
    source = _to_project_relative_path(file_path)
    return topic, source


def ingest_knowledge_directory(
    base_path: str | None = None,
    chunk_size: int = 500,
    overlap: int = 0,
) -> dict:
    base_dir = resolve_knowledge_base_path(base_path)
    files = scan_knowledge_files(str(base_dir))

    ingested_files = []
    skipped_files = []
    total_chunks_stored = 0

    for file_path in files:
        try:
            file_content = read_text_file(str(file_path))
        except Exception as exc:
            logger.warning("Skipping unreadable file %s: %s", file_path, exc)
            skipped_files.append(
                {"source": _to_project_relative_path(file_path), "reason": str(exc)}
            )
            continue

        if not file_content.strip():
            logger.info("Skipping empty file: %s", file_path)
            skipped_files.append(
                {
                    "source": _to_project_relative_path(file_path),
                    "reason": "File is empty.",
                }
            )
            continue

        topic, source = _derive_topic_and_source(file_path, base_dir)
        title = file_path.stem

        try:
            chunks = chunk_text(file_content, chunk_size=chunk_size, overlap=overlap)
            if not chunks:
                skipped_files.append(
                    {"source": source, "reason": "No chunks generated from file content."}
                )
                continue

            storage_result = add_note_chunks(
                title=title,
                chunks=chunks,
                topic=topic,
                source=source,
            )
        except Exception as exc:
            logger.warning("Skipping file due to ingest error %s: %s", file_path, exc)
            skipped_files.append({"source": source, "reason": str(exc)})
            continue

        chunk_count = len(storage_result["ids"])
        total_chunks_stored += chunk_count
        ingested_files.append(
            {
                "title": title,
                "topic": storage_result["topic"],
                "source": storage_result["source"],
                "chunks_stored": chunk_count,
            }
        )

    return {
        "message": "Knowledge directory ingested successfully",
        "base_path": _to_project_relative_path(base_dir),
        "total_files_found": len(files),
        "total_files_ingested": len(ingested_files),
        "total_chunks_stored": total_chunks_stored,
        "files": ingested_files,
        "skipped_files": skipped_files,
    }
