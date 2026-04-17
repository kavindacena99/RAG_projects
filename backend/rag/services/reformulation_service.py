from .generation_service import generate_answer_text
from .prompt_builder import build_reformulation_prompt


def reformulate_question(history: list[dict], current_question: str) -> str:
    clean_question = (current_question or "").strip()
    if not clean_question:
        return ""

    prompt = build_reformulation_prompt(history, clean_question)
    try:
        rewritten_question = generate_answer_text(prompt)
        return rewritten_question.strip() or clean_question
    except Exception:
        return clean_question

