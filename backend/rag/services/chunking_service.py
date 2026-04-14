import logging
import re

logger = logging.getLogger("rag.pipeline")


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"[ \t]+", " ", (text or "").strip())


def _split_into_sentences(text: str) -> list[str]:
    clean_text = _normalize_whitespace(text)
    if not clean_text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", clean_text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def semantic_chunk_text(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text or "")
    semantic_paragraphs = []

    for paragraph in paragraphs:
        clean_paragraph = _normalize_whitespace(paragraph)
        if len(clean_paragraph) < 50:
            continue
        semantic_paragraphs.append(clean_paragraph)

    return semantic_paragraphs


def merge_small_chunks(chunks: list[str], min_length: int = 200) -> list[str]:
    if min_length <= 0:
        raise ValueError("min_length must be greater than 0.")

    merged_chunks = []
    buffer = ""

    for chunk in chunks:
        clean_chunk = _normalize_whitespace(chunk)
        if not clean_chunk:
            continue

        if not buffer:
            buffer = clean_chunk
            continue

        if len(buffer) < min_length:
            buffer = f"{buffer}\n\n{clean_chunk}"
            continue

        merged_chunks.append(buffer)
        buffer = clean_chunk

    if buffer:
        if merged_chunks and len(buffer) < min_length:
            merged_chunks[-1] = f"{merged_chunks[-1]}\n\n{buffer}"
        else:
            merged_chunks.append(buffer)

    return merged_chunks


def split_large_chunks(chunks: list[str], max_length: int = 500) -> list[str]:
    if max_length <= 0:
        raise ValueError("max_length must be greater than 0.")

    split_chunks = []

    for chunk in chunks:
        clean_chunk = _normalize_whitespace(chunk)
        if not clean_chunk:
            continue

        if len(clean_chunk) <= max_length:
            split_chunks.append(clean_chunk)
            continue

        sentences = _split_into_sentences(clean_chunk)
        if not sentences:
            split_chunks.append(clean_chunk[:max_length].strip())
            remainder = clean_chunk[max_length:].strip()
            if remainder:
                split_chunks.append(remainder)
            continue

        current_chunk = ""
        for sentence in sentences:
            candidate = sentence if not current_chunk else f"{current_chunk} {sentence}"
            if len(candidate) <= max_length:
                current_chunk = candidate
                continue

            if current_chunk:
                split_chunks.append(current_chunk.strip())
                current_chunk = ""

            if len(sentence) <= max_length:
                current_chunk = sentence
                continue

            words = sentence.split()
            word_buffer = ""
            for word in words:
                word_candidate = word if not word_buffer else f"{word_buffer} {word}"
                if len(word_candidate) <= max_length:
                    word_buffer = word_candidate
                    continue

                if word_buffer:
                    split_chunks.append(word_buffer.strip())
                word_buffer = word

            if word_buffer:
                current_chunk = word_buffer.strip()

        if current_chunk:
            split_chunks.append(current_chunk.strip())

    return split_chunks


def semantic_chunk_pipeline(text: str) -> list[str]:
    semantic_chunks = semantic_chunk_text(text)
    merged_chunks = merge_small_chunks(semantic_chunks)
    final_chunks = split_large_chunks(merged_chunks)

    logger.info("semantic chunking completed | total_chunks_created=%d", len(final_chunks))
    if final_chunks:
        logger.info("semantic chunking sample | sample_chunk=%s", final_chunks[0][:160])

    return final_chunks
