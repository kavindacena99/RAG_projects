import os
from rag.utils.topic_normalizer import normalize_topic

SUPPORTED_PROVIDERS = {"gemini", "openai"}
NO_CONTEXT_ANSWER_MESSAGE = "No sufficient information found in knowledge base."
EMPTY_ANSWER_FALLBACK_MESSAGE = "No sufficient information found in knowledge base."


def get_llm_provider() -> str:
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
        raise RuntimeError(
            f"Unsupported LLM_PROVIDER '{provider}'. Supported providers: {supported}."
        )
    return provider


def get_embedding_model_name() -> str:
    provider = get_llm_provider()
    if provider == "gemini":
        return os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004").strip()
    if provider == "openai":
        return os.getenv(
            "OPENAI_EMBEDDING_MODEL",
            "text-embedding-3-small",
        ).strip()
    raise RuntimeError(f"Unsupported LLM provider: {provider}")


def generate_embedding(text: str) -> list[float]:
    provider = get_llm_provider()
    if provider == "gemini":
        from . import gemini_service

        return gemini_service.generate_embedding(text)
    if provider == "openai":
        from . import openai_service

        return openai_service.generate_embedding(text)
    raise RuntimeError(f"Unsupported LLM provider: {provider}")


def generate_answer(
    question: str,
    context_chunks: list[dict],
    is_comparison: bool = False,
    model_name: str | None = None,
) -> str:
    provider = get_llm_provider()
    if provider == "gemini":
        from . import gemini_service

        return gemini_service.generate_answer(
            question,
            context_chunks,
            is_comparison=is_comparison,
            model_name=model_name,
        )
    if provider == "openai":
        from . import openai_service

        return openai_service.generate_answer(
            question,
            context_chunks,
            is_comparison=is_comparison,
            model_name=model_name,
        )
    raise RuntimeError(f"Unsupported LLM provider: {provider}")


def score_chunks_for_reranking(
    question: str,
    chunks: list[dict],
) -> dict[str, float]:
    provider = get_llm_provider()
    if provider == "gemini":
        from . import gemini_service

        return gemini_service.score_chunks_for_reranking(question, chunks)
    if provider == "openai":
        from . import openai_service

        return openai_service.score_chunks_for_reranking(question, chunks)
    raise RuntimeError(f"Unsupported LLM provider: {provider}")


def extract_context_topics(context_chunks: list[dict]) -> list[str]:
    topics = []
    seen = set()

    for chunk in context_chunks:
        metadata = chunk.get("metadata") or {}
        topic = normalize_topic((metadata.get("topic") or "").strip())
        if not topic:
            continue

        normalized_topic = topic.lower()
        if normalized_topic in seen:
            continue

        seen.add(normalized_topic)
        topics.append(topic)

    return topics


def format_chunks(retrieved_chunks: list[dict]) -> str:
    if not retrieved_chunks:
        return "No context chunks were found."

    context_parts = []

    for position, chunk in enumerate(retrieved_chunks, start=1):
        metadata = chunk.get("metadata") or {}
        context_parts.append(
            (
                f"[CHUNK {position} | Topic: {metadata.get('topic', '')}]\n"
                f"{chunk.get('text', '')}"
            )
        )

    return "\n\n".join(context_parts)


def build_rag_prompt(
    question: str,
    retrieved_chunks: list[dict],
    is_comparison: bool = False,
) -> str:
    context_text = format_chunks(retrieved_chunks)
    comparison_instructions = ""
    if is_comparison:
        comparison_instructions = (
            "COMPARISON MODE:\n"
            "This is a comparison question.\n"
            "You MUST:\n"
            "1. Explain concept A using the provided chunks.\n"
            "2. Explain concept B using the provided chunks.\n"
            "3. Clearly describe their relationship, similarity, or difference.\n"
            "4. Make sure both concepts are covered with balanced attention.\n\n"
        )

    return (
        "ROLE:\n"
        "You are an AI assistant using retrieved study notes.\n"
        "Your job is to produce a clear, grounded answer by combining evidence from all provided chunks.\n\n"
        "CONTEXT:\n"
        "---------------------\n"
        f"{context_text}\n"
        "---------------------\n\n"
        "INSTRUCTIONS:\n"
        "- Use ALL provided chunks.\n"
        "- Do NOT ignore any chunk unless it is clearly irrelevant to the question.\n"
        "- Base your answer ONLY on the given chunks.\n"
        "- Do NOT add external knowledge, assumptions, or hallucinated details.\n"
        "- Combine information from multiple chunks into one coherent explanation.\n"
        "- If the chunks provide partial information, give the best grounded answer possible from those chunks.\n"
        "- Keep the explanation clear, structured, and easy to understand.\n\n"
        f"{comparison_instructions}"
        "ANSWER STRUCTURE:\n"
        "**Explanation:**\n"
        "<combined explanation using multiple chunks>\n\n"
        "**Key Points:**\n"
        "- point 1\n"
        "- point 2\n"
        "- point 3\n\n"
        "QUESTION:\n"
        "---------------------\n"
        f"{question}\n"
        "---------------------\n\n"
        "FINAL ANSWER:\n"
    )
