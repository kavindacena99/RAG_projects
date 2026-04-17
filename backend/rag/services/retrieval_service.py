from .rag_service import retrieve_context_for_question


def retrieve_context(question: str, top_k: int = 4) -> dict:
    return retrieve_context_for_question(question=question, top_k=top_k)
