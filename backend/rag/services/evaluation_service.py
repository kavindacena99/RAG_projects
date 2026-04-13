import json
from pathlib import Path

from django.conf import settings

from .rag_service import ask_question


def _resolve_evaluation_file_path(file_path: str | None = None) -> Path:
    if file_path and file_path.strip():
        candidate_path = Path(file_path.strip())
        if not candidate_path.is_absolute():
            candidate_path = Path(settings.BASE_DIR) / candidate_path
    else:
        candidate_path = Path(settings.BASE_DIR) / "rag" / "evaluation" / "test_questions.json"

    return candidate_path.resolve()


def _to_backend_relative_path(path: Path) -> str:
    try:
        return path.relative_to(settings.BASE_DIR).as_posix()
    except ValueError:
        return path.as_posix()


def _normalize_topic(value: str | None) -> str:
    return (value or "").strip().lower()


def _extract_chunk_topics(chunks: list[dict]) -> list[str]:
    topics = []
    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        topics.append((metadata.get("topic") or "").strip())
    return topics


def _extract_chunk_ids(chunks: list[dict]) -> list[str]:
    return [str(chunk.get("id", "")).strip() for chunk in chunks]


def _extract_chunk_distances(chunks: list[dict]) -> list[float | None]:
    distances = []
    for chunk in chunks:
        distance = chunk.get("distance")
        if distance is None:
            distances.append(None)
            continue

        try:
            distances.append(float(distance))
        except (TypeError, ValueError):
            distances.append(None)

    return distances


def _find_topic_position(topics: list[str], expected_topic: str) -> int | None:
    normalized_expected_topic = _normalize_topic(expected_topic)
    for index, topic in enumerate(topics, start=1):
        if _normalize_topic(topic) == normalized_expected_topic:
            return index
    return None


def _match_keywords(answer: str, expected_keywords: list[str]) -> list[str]:
    clean_answer = (answer or "").lower()
    matched_keywords = []

    for keyword in expected_keywords:
        clean_keyword = (keyword or "").strip()
        if not clean_keyword:
            continue

        if clean_keyword.lower() in clean_answer and clean_keyword not in matched_keywords:
            matched_keywords.append(clean_keyword)

    return matched_keywords


def _calculate_retrieval_score(expected_topic_position: int | None) -> int:
    if expected_topic_position == 1:
        return 2
    if expected_topic_position is not None and expected_topic_position <= 3:
        return 1
    return 0


def _calculate_answer_score(keyword_match_count: int) -> int:
    if keyword_match_count >= 2:
        return 2
    if keyword_match_count == 1:
        return 1
    return 0


def _build_case_notes(
    expected_topic_in_top_1: bool,
    expected_topic_in_top_3: bool,
    expected_topic_in_final_results: bool,
    expected_topic_only_appeared_after_rerank: bool,
    reranking_improved_topic_placement: bool,
    keyword_match_count: int,
) -> str:
    notes = []

    if expected_topic_in_top_1:
        notes.append("Expected topic found in top 1.")
    elif expected_topic_in_top_3:
        notes.append("Expected topic found in top 3.")
    elif expected_topic_in_final_results:
        notes.append("Expected topic appeared only lower in final results.")
    else:
        notes.append("Expected topic was not found in final results.")

    if expected_topic_only_appeared_after_rerank:
        notes.append("Expected topic only appeared after reranking.")
    elif reranking_improved_topic_placement:
        notes.append("Reranking improved topic placement.")

    if keyword_match_count >= 2:
        notes.append("Answer matched multiple expected keywords.")
    elif keyword_match_count == 1:
        notes.append("Answer matched one expected keyword.")
    else:
        notes.append("Answer missed expected keywords.")

    return " ".join(notes)


def load_evaluation_cases(file_path: str | None = None) -> list[dict]:
    resolved_path = _resolve_evaluation_file_path(file_path)

    if not resolved_path.exists():
        raise FileNotFoundError(f"Evaluation file does not exist: {resolved_path}")

    if not resolved_path.is_file():
        raise ValueError(f"Evaluation path is not a file: {resolved_path}")

    try:
        raw_payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Evaluation file contains invalid JSON: {resolved_path}") from exc

    if not isinstance(raw_payload, list):
        raise ValueError("Evaluation file must contain a JSON list of cases.")

    normalized_cases = []
    for index, item in enumerate(raw_payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Evaluation case {index} must be a JSON object.")

        question = (item.get("question") or "").strip()
        expected_topic = (item.get("expected_topic") or "").strip()
        expected_keywords = item.get("expected_keywords") or []

        if not question:
            raise ValueError(f"Evaluation case {index} is missing a question.")

        if not expected_topic:
            raise ValueError(f"Evaluation case {index} is missing an expected_topic.")

        if not isinstance(expected_keywords, list):
            raise ValueError(
                f"Evaluation case {index} expected_keywords must be a list of strings."
            )

        clean_keywords = []
        for keyword in expected_keywords:
            if not isinstance(keyword, str):
                raise ValueError(
                    f"Evaluation case {index} expected_keywords must only contain strings."
                )

            clean_keyword = keyword.strip()
            if clean_keyword:
                clean_keywords.append(clean_keyword)

        normalized_cases.append(
            {
                "question": question,
                "expected_topic": expected_topic,
                "expected_keywords": clean_keywords,
            }
        )

    if not normalized_cases:
        raise ValueError("Evaluation file did not contain any cases.")

    return normalized_cases


def evaluate_single_case(case: dict) -> dict:
    question = (case.get("question") or "").strip()
    expected_topic = (case.get("expected_topic") or "").strip()
    expected_keywords = case.get("expected_keywords") or []

    if not question:
        raise ValueError("Evaluation case question is required.")

    if not expected_topic:
        raise ValueError("Evaluation case expected_topic is required.")

    ask_result = ask_question(question=question)

    initial_chunks = ask_result.get("retrieved_chunks_initial") or []
    final_chunks = ask_result.get("retrieved_chunks_final") or []
    answer = ask_result.get("answer") or ""

    initial_topics = _extract_chunk_topics(initial_chunks)
    final_topics = _extract_chunk_topics(final_chunks)
    initial_ids = _extract_chunk_ids(initial_chunks)
    final_ids = _extract_chunk_ids(final_chunks)
    initial_distances = _extract_chunk_distances(initial_chunks)
    final_distances = _extract_chunk_distances(final_chunks)

    initial_expected_topic_position = _find_topic_position(initial_topics, expected_topic)
    final_expected_topic_position = _find_topic_position(final_topics, expected_topic)

    expected_topic_in_top_1 = final_expected_topic_position == 1
    expected_topic_in_top_3 = (
        final_expected_topic_position is not None and final_expected_topic_position <= 3
    )
    expected_topic_in_final_results = final_expected_topic_position is not None

    matched_keywords = _match_keywords(answer, expected_keywords)
    keyword_match_count = len(matched_keywords)

    retrieval_score = _calculate_retrieval_score(final_expected_topic_position)
    answer_score = _calculate_answer_score(keyword_match_count)

    initial_top_1_chunk_id = initial_ids[0] if initial_ids else None
    final_top_1_chunk_id = final_ids[0] if final_ids else None
    initial_top_1_topic = initial_topics[0] if initial_topics else None
    final_top_1_topic = final_topics[0] if final_topics else None

    reranking_enabled = bool(ask_result.get("reranking_enabled"))
    top_1_chunk_changed_after_rerank = (
        reranking_enabled
        and initial_top_1_chunk_id is not None
        and final_top_1_chunk_id is not None
        and initial_top_1_chunk_id != final_top_1_chunk_id
    )
    expected_topic_only_appeared_after_rerank = (
        reranking_enabled
        and initial_expected_topic_position is None
        and final_expected_topic_position is not None
    )
    reranking_improved_topic_placement = (
        reranking_enabled
        and final_expected_topic_position is not None
        and (
            initial_expected_topic_position is None
            or final_expected_topic_position < initial_expected_topic_position
        )
    )

    notes = _build_case_notes(
        expected_topic_in_top_1=expected_topic_in_top_1,
        expected_topic_in_top_3=expected_topic_in_top_3,
        expected_topic_in_final_results=expected_topic_in_final_results,
        expected_topic_only_appeared_after_rerank=expected_topic_only_appeared_after_rerank,
        reranking_improved_topic_placement=reranking_improved_topic_placement,
        keyword_match_count=keyword_match_count,
    )

    return {
        "question": question,
        "expected_topic": expected_topic,
        "expected_keywords": expected_keywords,
        "provider": ask_result.get("provider"),
        "collection": ask_result.get("collection"),
        "top_1_topic": final_top_1_topic,
        "top_1_chunk_id": final_top_1_chunk_id,
        "top_1_distance": final_distances[0] if final_distances else None,
        "initial_top_1_topic": initial_top_1_topic,
        "initial_top_1_chunk_id": initial_top_1_chunk_id,
        "initial_expected_topic_position": initial_expected_topic_position,
        "final_expected_topic_position": final_expected_topic_position,
        "expected_topic_in_top_1": expected_topic_in_top_1,
        "expected_topic_in_top_3": expected_topic_in_top_3,
        "expected_topic_in_final_results": expected_topic_in_final_results,
        "expected_topic_in_initial_top_3": (
            initial_expected_topic_position is not None
            and initial_expected_topic_position <= 3
        ),
        "retrieval_score": retrieval_score,
        "matched_keywords": matched_keywords,
        "keyword_match_count": keyword_match_count,
        "answer_score": answer_score,
        "total_score": retrieval_score + answer_score,
        "reranking_enabled": reranking_enabled,
        "reranking_fallback_used": bool(ask_result.get("reranking_fallback_used")),
        "reranking_error": ask_result.get("reranking_error"),
        "top_1_chunk_changed_after_rerank": top_1_chunk_changed_after_rerank,
        "expected_topic_only_appeared_after_rerank": expected_topic_only_appeared_after_rerank,
        "reranking_improved_topic_placement": reranking_improved_topic_placement,
        "total_retrieved_initial": int(ask_result.get("total_retrieved_initial") or 0),
        "total_retrieved_final": int(ask_result.get("total_retrieved_final") or 0),
        "initial_chunk_ids": initial_ids,
        "initial_chunk_topics": initial_topics,
        "initial_chunk_distances": initial_distances,
        "final_chunk_ids": final_ids,
        "final_chunk_topics": final_topics,
        "final_chunk_distances": final_distances,
        "answer": answer,
        "notes": notes,
    }


def evaluate_all_cases(file_path: str | None = None) -> dict:
    resolved_path = _resolve_evaluation_file_path(file_path)
    evaluation_cases = load_evaluation_cases(str(resolved_path))
    evaluated_cases = [evaluate_single_case(case) for case in evaluation_cases]

    total_cases = len(evaluated_cases)
    retrieval_score_total = sum(case["retrieval_score"] for case in evaluated_cases)
    answer_score_total = sum(case["answer_score"] for case in evaluated_cases)
    total_score_total = sum(case["total_score"] for case in evaluated_cases)

    first_case = evaluated_cases[0] if evaluated_cases else {}

    return {
        "message": "Evaluation completed successfully",
        "file_path": _to_backend_relative_path(resolved_path),
        "provider": first_case.get("provider"),
        "collection": first_case.get("collection"),
        "total_cases": total_cases,
        "cases_with_expected_topic_in_top_1": sum(
            1 for case in evaluated_cases if case["expected_topic_in_top_1"]
        ),
        "cases_with_expected_topic_in_top_3": sum(
            1 for case in evaluated_cases if case["expected_topic_in_top_3"]
        ),
        "cases_with_keyword_match": sum(
            1 for case in evaluated_cases if case["keyword_match_count"] > 0
        ),
        "average_retrieval_score": round(retrieval_score_total / total_cases, 2),
        "average_answer_score": round(answer_score_total / total_cases, 2),
        "average_total_score": round(total_score_total / total_cases, 2),
        "cases": evaluated_cases,
    }
