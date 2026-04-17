import logging

logger = logging.getLogger("rag.pipeline")

_RELATION_WORDS = (
    "difference",
    "compare",
    "comparison",
    "relation",
    "related",
    "versus",
    "vs",
)
_DEFINITION_PREFIXES = ("what is", "what are", "define", "definition of")
_EXPLANATION_PREFIXES = ("why", "how", "explain")


def _pretty_topic_label(topic: str) -> str:
    clean_topic = (topic or "unknown").strip().replace("_", " ")
    return " ".join(word.capitalize() for word in clean_topic.split())


def detect_answer_mode(question: str, is_comparison: bool = False) -> str:
    clean_question = (question or "").strip().lower()
    if is_comparison or any(word in clean_question for word in _RELATION_WORDS):
        return "comparison"
    if clean_question.startswith(_DEFINITION_PREFIXES):
        return "definition"
    if clean_question.startswith(_EXPLANATION_PREFIXES):
        return "explanation"
    return "standard"


def build_response_schema(answer_plan: dict) -> dict:
    mode = answer_plan.get("mode", "standard")
    return {
        "format_name": f"{mode}_response",
        "sections": [section.get("name", "") for section in answer_plan.get("sections", [])],
    }


def build_answer_plan(
    standalone_question: str,
    structured_context: dict,
    is_comparison: bool = False,
) -> dict:
    mode = detect_answer_mode(standalone_question, is_comparison=is_comparison)
    structured_topics = structured_context.get("structured_topics") or []

    if mode == "comparison":
        expected_topics = structured_context.get("expected_topics") or structured_topics
        topic_a = expected_topics[0] if expected_topics else (
            structured_topics[0] if structured_topics else "unknown"
        )
        topic_b = expected_topics[1] if len(expected_topics) > 1 else (
            structured_topics[1] if len(structured_topics) > 1 else "unknown"
        )
        sections = [
            {"name": _pretty_topic_label(topic_a), "topic": topic_a},
            {"name": _pretty_topic_label(topic_b), "topic": topic_b},
            {"name": "Key Differences or Relationship", "topics": [topic_a, topic_b]},
            {"name": "Summary"},
        ]
        requirements = [
            "use both topics",
            "avoid repetition",
            "compare explicitly",
            "stay grounded in provided context",
            "do not list chunks one by one",
        ]
        topics = [topic for topic in [topic_a, topic_b] if topic and topic != "unknown"]
    else:
        primary_topic = structured_context.get("primary_topic") or (
            structured_topics[0] if structured_topics else "unknown"
        )
        sections = [
            {"name": "Explanation", "topic": primary_topic},
            {"name": "Key Points", "topic": primary_topic},
        ]
        requirements = [
            "answer directly",
            "combine context chunks",
            "avoid repetition",
            "stay grounded in provided context",
            "lead with the clearest explanation first",
        ]
        topics = [primary_topic] if primary_topic and primary_topic != "unknown" else []

    answer_plan = {
        "mode": mode,
        "question": standalone_question,
        "topics": topics,
        "sections": sections,
        "requirements": requirements,
    }
    answer_plan["response_schema"] = build_response_schema(answer_plan)

    logger.info(
        "answer synthesis | mode=%s sections=%s topics=%s",
        mode,
        [section.get("name") for section in sections],
        topics,
    )
    return answer_plan


def build_synthesis_instructions(answer_plan: dict) -> str:
    mode = answer_plan.get("mode", "standard")
    section_names = [section.get("name", "") for section in answer_plan.get("sections", [])]
    requirements = answer_plan.get("requirements", [])

    lines = [
        "SYNTHESIS INSTRUCTIONS:",
        "- Synthesize the answer across the provided context sections instead of summarizing each chunk separately.",
        "- Merge overlapping ideas into one clear explanation.",
        "- Do not repeat the same definition or point multiple times.",
        "- Use only grounded details from the provided structured context.",
    ]

    if mode == "comparison":
        lines.extend(
            [
                "- This is a comparison answer.",
                "- Cover both topics with balanced attention.",
                "- Explicitly explain differences, similarities, or relationships.",
                "- Do not let one topic dominate the answer.",
            ]
        )
    elif mode == "definition":
        lines.extend(
            [
                "- Start with a direct definition.",
                "- Then expand with compact supporting detail.",
            ]
        )
    else:
        lines.extend(
            [
                "- Answer directly first.",
                "- Then provide concise supporting key points.",
            ]
        )

    if section_names:
        lines.append("REQUIRED SECTIONS:")
        lines.extend([f"- {section_name}" for section_name in section_names])

    if requirements:
        lines.append("REQUIREMENTS:")
        lines.extend([f"- {requirement}" for requirement in requirements])

    return "\n".join(lines)
