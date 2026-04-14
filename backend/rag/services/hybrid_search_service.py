import math
import re

from rag.utils.topic_normalizer import normalize_topic


def _tokenize_text(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_+#.-]+", (text or "").lower())


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")


def _is_valid_hybrid_candidate(chunk: dict) -> bool:
    text = " ".join((chunk.get("text") or "").split()).strip()
    if not text:
        return False

    metadata = chunk.get("metadata") or {}
    topic = _normalize_label(normalize_topic(metadata.get("topic", "")))
    title = _normalize_label(metadata.get("title", ""))
    source_name = str(metadata.get("source", "")).strip().split("/")[-1].split(".")[0]
    source_name = _normalize_label(source_name)
    normalized_text = _normalize_label(text)

    if normalized_text and normalized_text in {topic, title, source_name}:
        return False

    if len(text) < 20 and len(text.split()) < 4:
        return False

    return True


def _min_max_normalize(values: list[float]) -> list[float]:
    if not values:
        return []

    minimum = min(values)
    maximum = max(values)
    if math.isclose(minimum, maximum):
        return [1.0 if value > 0 else 0.0 for value in values]

    return [(value - minimum) / (maximum - minimum) for value in values]


def _compute_keyword_scores_fallback(query_tokens: list[str], tokenized_documents: list[list[str]]) -> list[float]:
    if not query_tokens or not tokenized_documents:
        return [0.0 for _ in tokenized_documents]

    document_count = len(tokenized_documents)
    average_document_length = (
        sum(len(document_tokens) for document_tokens in tokenized_documents) / document_count
        if document_count
        else 0.0
    )
    average_document_length = average_document_length or 1.0

    document_frequency = {}
    for document_tokens in tokenized_documents:
        for token in set(document_tokens):
            document_frequency[token] = document_frequency.get(token, 0) + 1

    scores = []
    k1 = 1.5
    b = 0.75

    for document_tokens in tokenized_documents:
        token_counts = {}
        for token in document_tokens:
            token_counts[token] = token_counts.get(token, 0) + 1

        document_length = len(document_tokens) or 1
        score = 0.0
        for token in query_tokens:
            term_frequency = token_counts.get(token, 0)
            if term_frequency <= 0:
                continue

            df = document_frequency.get(token, 0)
            idf = math.log(1 + ((document_count - df + 0.5) / (df + 0.5)))
            numerator = term_frequency * (k1 + 1)
            denominator = term_frequency + k1 * (
                1 - b + b * (document_length / average_document_length)
            )
            score += idf * (numerator / denominator)

        scores.append(score)

    return scores


def score_candidates_with_keywords(query: str, chunks: list[dict]) -> list[dict]:
    query_tokens = _tokenize_text(query)
    tokenized_documents = [_tokenize_text(chunk.get("text", "")) for chunk in chunks]

    fallback_scores = _compute_keyword_scores_fallback(query_tokens, tokenized_documents)
    raw_scores = None
    try:
        from rank_bm25 import BM25Okapi

        bm25 = BM25Okapi(tokenized_documents)
        raw_scores = list(bm25.get_scores(query_tokens))
        if not any(float(score) > 0 for score in raw_scores):
            raw_scores = fallback_scores
    except Exception:
        raw_scores = fallback_scores

    scored_chunks = []
    for index, chunk in enumerate(chunks):
        updated_chunk = dict(chunk)
        updated_chunk["keyword_score_raw"] = (
            float(raw_scores[index]) if index < len(raw_scores) else 0.0
        )
        scored_chunks.append(updated_chunk)

    return scored_chunks


def normalize_vector_scores(chunks: list[dict]) -> list[dict]:
    raw_scores = []
    for chunk in chunks:
        distance = chunk.get("distance")
        if distance is None:
            raw_scores.append(0.0)
        else:
            raw_scores.append(1.0 / (1.0 + max(float(distance), 0.0)))

    normalized_scores = _min_max_normalize(raw_scores)

    normalized_chunks = []
    for index, chunk in enumerate(chunks):
        updated_chunk = dict(chunk)
        updated_chunk["vector_score"] = (
            float(normalized_scores[index]) if index < len(normalized_scores) else 0.0
        )
        normalized_chunks.append(updated_chunk)

    return normalized_chunks


def normalize_keyword_scores(chunks: list[dict]) -> list[dict]:
    raw_scores = [float(chunk.get("keyword_score_raw", 0.0) or 0.0) for chunk in chunks]
    normalized_scores = _min_max_normalize(raw_scores)

    normalized_chunks = []
    for index, chunk in enumerate(chunks):
        updated_chunk = dict(chunk)
        updated_chunk["keyword_score"] = (
            float(normalized_scores[index]) if index < len(normalized_scores) else 0.0
        )
        normalized_chunks.append(updated_chunk)

    return normalized_chunks


def apply_hybrid_scoring(
    chunks: list[dict],
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> list[dict]:
    total_weight = vector_weight + keyword_weight
    if total_weight <= 0:
        vector_weight = 0.7
        keyword_weight = 0.3
        total_weight = 1.0

    normalized_vector_weight = vector_weight / total_weight
    normalized_keyword_weight = keyword_weight / total_weight

    scored_chunks = []
    for chunk in chunks:
        updated_chunk = dict(chunk)
        vector_score = float(updated_chunk.get("vector_score", 0.0) or 0.0)
        keyword_score = float(updated_chunk.get("keyword_score", 0.0) or 0.0)
        updated_chunk["hybrid_score"] = (
            normalized_vector_weight * vector_score
            + normalized_keyword_weight * keyword_score
        )
        scored_chunks.append(updated_chunk)

    scored_chunks.sort(
        key=lambda chunk: (
            -float(chunk.get("hybrid_score", 0.0) or 0.0),
            chunk.get("distance", float("inf")),
            chunk.get("retrieval_position", 10**6),
        )
    )

    for position, chunk in enumerate(scored_chunks, start=1):
        chunk["hybrid_position"] = position

    return scored_chunks


def rank_hybrid_candidates(
    query: str,
    chunks: list[dict],
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> dict:
    filtered_chunks = []
    filtered_out_chunk_ids = []

    for chunk in chunks:
        if _is_valid_hybrid_candidate(chunk):
            filtered_chunks.append(dict(chunk))
        else:
            filtered_out_chunk_ids.append(chunk.get("id"))

    if not filtered_chunks:
        return {
            "ranked_chunks": [],
            "filtered_out_chunk_ids": filtered_out_chunk_ids,
        }

    vector_scored_chunks = normalize_vector_scores(filtered_chunks)
    keyword_scored_chunks = score_candidates_with_keywords(query, vector_scored_chunks)
    normalized_keyword_chunks = normalize_keyword_scores(keyword_scored_chunks)
    hybrid_ranked_chunks = apply_hybrid_scoring(
        normalized_keyword_chunks,
        vector_weight=vector_weight,
        keyword_weight=keyword_weight,
    )

    return {
        "ranked_chunks": hybrid_ranked_chunks,
        "filtered_out_chunk_ids": filtered_out_chunk_ids,
    }
