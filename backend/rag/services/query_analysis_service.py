import re

from rag.utils.topic_normalizer import normalize_topic

COMPARISON_KEYWORDS = (
    "difference",
    "different",
    "compare",
    "comparison",
    "relation",
    "related",
    "relationship",
    "versus",
    "vs",
)

BETWEEN_AND_PATTERN = re.compile(
    r"\bbetween\s+(?P<left>.+?)\s+and\s+(?P<right>.+?)(?:[?.!,]|$)",
    flags=re.IGNORECASE,
)
COMPARE_PATTERN = re.compile(
    r"\bcompare\s+(?P<left>.+?)\s+(?:and|with|to)\s+(?P<right>.+?)(?:[?.!,]|$)",
    flags=re.IGNORECASE,
)
VERSUS_PATTERN = re.compile(
    r"(?P<left>.+?)\s+(?:vs\.?|versus)\s+(?P<right>.+?)(?:[?.!,]|$)",
    flags=re.IGNORECASE,
)
RELATED_PATTERN = re.compile(
    r"\bhow\s+(?:is|are)\s+(?P<left>.+?)\s+and\s+(?P<right>.+?)\s+related(?:[?.!,]|$)",
    flags=re.IGNORECASE,
)
def _clean_term(term: str) -> str:
    cleaned = re.sub(r"^[\s'\"`]+|[\s'\"`]+$", "", term or "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(
        r"^(?:what\s+is|what's|compare|explain|describe|tell\s+me\s+about)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip(" ?!.,:;")


def _extract_terms_from_pattern(question: str, pattern: re.Pattern[str]) -> list[str]:
    match = pattern.search(question or "")
    if not match:
        return []

    terms = [_clean_term(match.group("left")), _clean_term(match.group("right"))]
    return [term for term in terms if term]


def is_comparison_question(question: str) -> bool:
    clean_question = (question or "").strip()
    if not clean_question:
        return False

    lowered = clean_question.lower()
    if any(keyword in lowered for keyword in COMPARISON_KEYWORDS):
        return True

    return bool(
        BETWEEN_AND_PATTERN.search(clean_question)
        or COMPARE_PATTERN.search(clean_question)
        or VERSUS_PATTERN.search(clean_question)
        or RELATED_PATTERN.search(clean_question)
    )


def extract_comparison_terms(question: str) -> list[str]:
    clean_question = (question or "").strip()
    if not clean_question:
        return []

    for pattern in (
        BETWEEN_AND_PATTERN,
        COMPARE_PATTERN,
        RELATED_PATTERN,
        VERSUS_PATTERN,
    ):
        terms = _extract_terms_from_pattern(clean_question, pattern)
        if terms:
            deduplicated_terms = []
            seen = set()
            for term in terms:
                normalized = term.lower()
                if normalized in seen:
                    continue
                seen.add(normalized)
                deduplicated_terms.append(term)
            return deduplicated_terms

    return []


def normalize_comparison_term_to_topic(term: str) -> str:
    clean_term = _clean_term(term).lower()
    return normalize_topic(clean_term)
