import re

TOPIC_MAP = {
    "generativeai": "genai",
    "generative_ai": "genai",
    "gen ai": "genai",
    "gen_ai": "genai",
    "genai": "genai",
    "ml": "machine_learning",
    "machine learning": "machine_learning",
    "machine_learning": "machine_learning",
    "dl": "deep_learning",
    "deep learning": "deep_learning",
    "deep_learning": "deep_learning",
    "software engineering": "software_engineering",
    "software_engineering": "software_engineering",
    "softwareengineer": "software_engineering",
    "software_engineer": "software_engineering",
    "devops": "devops",
}


def normalize_topic(term: str) -> str:
    if not term:
        return term

    clean_term = (term or "").lower().strip()
    if not clean_term:
        return ""

    direct_match = TOPIC_MAP.get(clean_term)
    if direct_match:
        return direct_match

    normalized_term = re.sub(r"[^a-z0-9]+", "_", clean_term).strip("_")
    if normalized_term in TOPIC_MAP:
        return TOPIC_MAP[normalized_term]

    compact_term = re.sub(r"[^a-z0-9]+", "", clean_term)
    if compact_term in TOPIC_MAP:
        return TOPIC_MAP[compact_term]

    return normalized_term or clean_term


def normalize_topics(terms: list[str]) -> list[str]:
    normalized_terms = []
    seen = set()

    for term in terms:
        normalized_term = normalize_topic(term)
        if not normalized_term or normalized_term in seen:
            continue
        seen.add(normalized_term)
        normalized_terms.append(normalized_term)

    return normalized_terms
