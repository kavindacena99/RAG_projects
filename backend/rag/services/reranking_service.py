import logging

from .llm_service import score_chunks_for_reranking

logger = logging.getLogger("rag.pipeline")


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

    final_chunks = scored_chunks[:final_top_n]
    for position, chunk in enumerate(final_chunks, start=1):
        chunk["rerank_position"] = position
        chunk.pop("_initial_index", None)

    logger.info(
        "reranking completed | candidate_chunks=%d final_chunks=%d",
        len(chunks),
        len(final_chunks),
    )

    return final_chunks
