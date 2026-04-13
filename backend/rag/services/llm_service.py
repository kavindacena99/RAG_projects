import os

from . import gemini_service, openai_service

SUPPORTED_PROVIDERS = {"gemini", "openai"}


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
        return gemini_service.generate_embedding(text)
    if provider == "openai":
        return openai_service.generate_embedding(text)
    raise RuntimeError(f"Unsupported LLM provider: {provider}")


def generate_answer(
    question: str,
    context_chunks: list[dict],
    model_name: str | None = None,
) -> str:
    provider = get_llm_provider()
    if provider == "gemini":
        return gemini_service.generate_answer(question, context_chunks, model_name)
    if provider == "openai":
        return openai_service.generate_answer(question, context_chunks, model_name)
    raise RuntimeError(f"Unsupported LLM provider: {provider}")


def score_chunks_for_reranking(
    question: str,
    chunks: list[dict],
) -> dict[str, float]:
    provider = get_llm_provider()
    if provider == "gemini":
        return gemini_service.score_chunks_for_reranking(question, chunks)
    if provider == "openai":
        return openai_service.score_chunks_for_reranking(question, chunks)
    raise RuntimeError(f"Unsupported LLM provider: {provider}")
