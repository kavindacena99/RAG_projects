from .chroma_service import (
    delete_chunks_by_ids,
    get_active_collection_name,
    get_collection_records,
)


def _normalize_duplicate_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _build_record_sort_key(record: dict) -> tuple:
    metadata = record.get("metadata") or {}
    chunk_index = metadata.get("chunk_index")
    if chunk_index is None:
        chunk_index = 10**6

    return (
        str(metadata.get("source", "")).strip(),
        int(chunk_index),
        _normalize_duplicate_text(record.get("text", "")),
        str(record.get("id", "")).strip(),
    )


def _build_duplicate_keys(record: dict) -> list[tuple]:
    metadata = record.get("metadata") or {}
    source = str(metadata.get("source", "")).strip()
    chunk_index = metadata.get("chunk_index")
    normalized_text = _normalize_duplicate_text(record.get("text", ""))

    duplicate_keys = []
    if source and chunk_index is not None and normalized_text:
        duplicate_keys.append(("source_chunk_text", source, int(chunk_index), normalized_text))
    if source and chunk_index is not None:
        duplicate_keys.append(("source_chunk_index", source, int(chunk_index)))
    if normalized_text:
        duplicate_keys.append(("text_only", normalized_text))

    return duplicate_keys


def _group_duplicate_records(records: list[dict]) -> list[list[dict]]:
    duplicate_groups_by_key = {}
    for record in records:
        for duplicate_key in _build_duplicate_keys(record):
            duplicate_groups_by_key.setdefault(duplicate_key, []).append(record)

    records_by_id = {
        str(record.get("id", "")).strip(): record
        for record in records
        if str(record.get("id", "")).strip()
    }
    related_ids = {record_id: set() for record_id in records_by_id}

    for records_for_key in duplicate_groups_by_key.values():
        unique_ids = []
        seen_ids = set()
        for record in records_for_key:
            record_id = str(record.get("id", "")).strip()
            if not record_id or record_id in seen_ids:
                continue
            seen_ids.add(record_id)
            unique_ids.append(record_id)

        if len(unique_ids) <= 1:
            continue

        for record_id in unique_ids:
            related_ids[record_id].update(
                candidate_id for candidate_id in unique_ids if candidate_id != record_id
            )

    visited = set()
    duplicate_groups = []

    for record_id in related_ids:
        if record_id in visited or not related_ids[record_id]:
            continue

        stack = [record_id]
        component_ids = set()
        while stack:
            current_id = stack.pop()
            if current_id in visited:
                continue

            visited.add(current_id)
            component_ids.add(current_id)
            stack.extend(related_ids[current_id] - visited)

        if len(component_ids) <= 1:
            continue

        duplicate_groups.append(
            sorted(
                [records_by_id[current_id] for current_id in component_ids],
                key=_build_record_sort_key,
            )
        )

    return duplicate_groups


def cleanup_duplicate_chunks(dry_run: bool = True) -> dict:
    collection_records = get_collection_records(include=["documents", "metadatas"])
    ids = collection_records.get("ids") or []
    documents = collection_records.get("documents") or []
    metadatas = collection_records.get("metadatas") or []

    records = []
    for index, chunk_id in enumerate(ids):
        records.append(
            {
                "id": chunk_id,
                "text": documents[index] if index < len(documents) else "",
                "metadata": metadatas[index] if index < len(metadatas) else {},
            }
        )

    if not records:
        return {
            "message": "No chunks found in the active collection.",
            "collection": get_active_collection_name(),
            "dry_run": dry_run,
            "total_chunks_seen": 0,
            "duplicate_groups_found": 0,
            "duplicate_chunks_found": 0,
            "ids_kept": [],
            "ids_to_delete": [],
            "deleted_count": 0,
            "duplicate_groups": [],
        }

    duplicate_groups = _group_duplicate_records(records)
    ids_kept = []
    ids_to_delete = []
    duplicate_group_summaries = []

    for duplicate_group in duplicate_groups:
        canonical_record = duplicate_group[0]
        duplicate_records = duplicate_group[1:]
        ids_kept.append(canonical_record["id"])
        ids_to_delete.extend(record["id"] for record in duplicate_records)
        duplicate_group_summaries.append(
            {
                "kept_id": canonical_record["id"],
                "duplicate_ids": [record["id"] for record in duplicate_records],
                "source": (canonical_record.get("metadata") or {}).get("source"),
                "chunk_index": (canonical_record.get("metadata") or {}).get("chunk_index"),
                "text_preview": (_normalize_duplicate_text(canonical_record.get("text", ""))[:120]),
            }
        )

    deleted_count = 0
    if not dry_run and ids_to_delete:
        deleted_count = delete_chunks_by_ids(ids_to_delete)

    return {
        "message": "Duplicate cleanup analysis completed successfully",
        "collection": get_active_collection_name(),
        "dry_run": dry_run,
        "total_chunks_seen": len(records),
        "duplicate_groups_found": len(duplicate_groups),
        "duplicate_chunks_found": len(ids_to_delete),
        "ids_kept": ids_kept,
        "ids_to_delete": ids_to_delete,
        "deleted_count": deleted_count,
        "duplicate_groups": duplicate_group_summaries,
    }
