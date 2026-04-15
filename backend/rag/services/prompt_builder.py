import logging

from rag.services.context_structuring_service import format_structured_context_for_prompt

logger = logging.getLogger("rag.pipeline")


def _format_history(history: list[dict]) -> str:
    if not history:
        return "No prior conversation history."

    parts = []
    for index, item in enumerate(history, start=1):
        role = item.get("role", "user")
        content = item.get("content", "")
        parts.append(f"[History {index} | Role: {role}]\n{content}")
    return "\n\n".join(parts)


def _get_enforced_headings(response_schema: dict, mode: str) -> list[str]:
    sections = response_schema.get("sections", []) or ["Explanation", "Key Points"]
    if mode == "comparison" and len(sections) >= 4:
        return [
            sections[0],
            sections[1],
            "Key Differences",
            "Summary",
        ]
    if mode != "comparison":
        return ["Explanation", "Key Points"]
    return sections


def _build_anchored_heading_template(response_schema: dict, mode: str) -> str:
    sections = _get_enforced_headings(response_schema, mode)
    blocks = []
    for section_name in sections:
        if section_name == "Key Points":
            blocks.append(f"### {section_name}\n- point 1\n- point 2")
        else:
            blocks.append(f"### {section_name}\n")
    return "\n\n".join(blocks)


def build_strict_output_instructions(response_schema: dict, mode: str) -> str:
    sections = _get_enforced_headings(response_schema, mode)

    additional_rules = ""
    if mode == "comparison":
        topic_a = sections[0] if sections else "Concept A"
        topic_b = sections[1] if len(sections) > 1 else "Concept B"
        additional_rules = (
            "You MUST complete the following structure.\n"
            "Do NOT change headings.\n"
            "Do NOT add new sections.\n"
            "Do NOT skip any section.\n\n"
            f"### {topic_a}\n\n"
            f"Write the explanation of {topic_a} here.\n\n"
            f"### {topic_b}\n\n"
            f"Write the explanation of {topic_b} here.\n\n"
            "### Key Differences\n\n"
            f"Write clear differences between {topic_a} and {topic_b}.\n\n"
            "### Summary\n\n"
            f"Write a short summary connecting {topic_a} and {topic_b}.\n\n"
            "Rules:\n"
            "- DO NOT merge sections.\n"
            "- DO NOT output outside this structure.\n"
            "- DO NOT repeat the same idea.\n"
            "- DO NOT ignore any section.\n"
            "- Both topics must be explained separately.\n"
            "- One topic must not dominate.\n"
            "- Differences must be explicit.\n"
            "- Do NOT mix both topics in one section.\n"
            "- If structure is not followed, the answer is incorrect."
        )
    else:
        additional_rules = (
            "You MUST complete the following structure:\n\n"
            "### Explanation\n\n"
            "Write a clear explanation of the concept.\n\n"
            "### Key Points\n\n"
            "Write concise bullet points summarizing the concept.\n\n"
            "Rules:\n"
            "- DO NOT merge sections.\n"
            "- DO NOT skip sections.\n"
            "- DO NOT repeat content.\n"
            "- Key Points must be bullet points.\n"
            "- If structure is not followed, the answer is incorrect."
        )

    logger.info(
        "strict_output | mode=%s sections=%s enforced=True",
        mode,
        sections,
    )

    return "STRICT OUTPUT CONTRACT:\n" + additional_rules


def validate_response_structure(
    response_text: str,
    response_schema: dict,
    mode: str = "standard",
) -> bool:
    clean_text = (response_text or "").strip()
    if not clean_text:
        return False

    sections = _get_enforced_headings(response_schema, mode)
    for section_name in sections:
        if f"### {section_name}" not in clean_text:
            return False

    return True


def build_structure_retry_warning(response_schema: dict, mode: str) -> str:
    return (
        "Your previous answer did not follow the required structure. Fix it.\n\n"
        f"{build_strict_output_instructions(response_schema, mode)}\n\n"
        "Return the full answer again using only the required headings."
    )


def build_reformulation_prompt(history: list[dict], current_question: str) -> str:
    return (
        "You are helping with question reformulation for retrieval.\n"
        "Given the conversation history and the user's latest message, rewrite the latest "
        "message as a standalone question that preserves the intended meaning.\n"
        "Do not answer the question.\n"
        "Return only the standalone question text.\n\n"
        "CONVERSATION HISTORY:\n"
        f"{_format_history(history)}\n\n"
        "LATEST USER MESSAGE:\n"
        f"{current_question}\n\n"
        "STANDALONE QUESTION:"
    )


def build_answer_prompt(
    history: list[dict],
    standalone_question: str,
    structured_context: dict,
    answer_plan: dict,
    synthesis_instructions: str,
    response_schema: dict,
    is_comparison: bool = False,
) -> str:
    context_text = format_structured_context_for_prompt(structured_context)
    mode = answer_plan.get("mode", "standard")
    answer_plan_lines = "\n".join(
        f"- {section.get('name')}" for section in answer_plan.get("sections", [])
    ) or "- Explanation"
    schema_sections = _build_anchored_heading_template(response_schema, mode)
    strict_output_instructions = build_strict_output_instructions(response_schema, mode)
    comparison_instructions = ""
    if is_comparison:
        comparison_instructions = (
            "COMPARISON NOTE:\n"
            "- Use both topic sections.\n"
            "- Do not produce a one-sided answer.\n"
            "- Compare or relate the topics explicitly.\n\n"
        )

    return (
        "You are a helpful AI tutor answering with retrieved study notes.\n"
        "Use the conversation history for continuity, but ground the answer in the retrieved context.\n"
        "Use all relevant structured context sections.\n"
        "Do not hallucinate or add outside facts.\n"
        "If the retrieved chunks are partial, answer modestly using only supported information.\n"
        "Avoid repeating the same point when multiple chunks overlap.\n\n"
        "CONVERSATION HISTORY:\n"
        f"{_format_history(history)}\n\n"
        "STANDALONE QUESTION:\n"
        f"{standalone_question}\n\n"
        "STRUCTURED CONTEXT:\n"
        f"{context_text}\n\n"
        "ANSWER PLAN:\n"
        f"Mode: {mode}\n"
        f"Sections:\n{answer_plan_lines}\n\n"
        f"{synthesis_instructions}\n\n"
        f"{comparison_instructions}"
        f"{strict_output_instructions}\n\n"
        "FINAL ANSWER (STRICT FORMAT):\n"
        f"{schema_sections}\n\n"
        "FINAL INSTRUCTION:\n"
        "- STRICTLY FOLLOW the output contract.\n"
        "- Use the structured context and synthesis instructions to produce the answer.\n"
        "- Make the answer grounded, clear, and professionally structured.\n\n"
        "FINAL ANSWER:"
    )
