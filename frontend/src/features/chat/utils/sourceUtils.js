function readString(value) {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

function readNumber(value) {
  return typeof value === 'number' ? value : undefined;
}

function normalizeChunk(chunk, index) {
  if (!chunk || typeof chunk !== 'object') {
    return null;
  }

  const metadata =
    chunk.metadata && typeof chunk.metadata === 'object' ? chunk.metadata : {};

  const text = readString(chunk.text);
  if (!text) {
    return null;
  }

  return {
    chunk_index:
      readNumber(chunk.chunk_index) ?? readNumber(metadata.chunk_index) ?? index + 1,
    id: readString(chunk.id) ?? `source-${index + 1}`,
    source: readString(chunk.source) ?? readString(metadata.source) ?? null,
    text,
    topic: readString(chunk.topic) ?? readString(metadata.topic) ?? null,
  };
}

export function normalizeSourceContext(value) {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const topics = Array.isArray(value.topics)
    ? value.topics.map(readString).filter(Boolean)
    : [];

  const retrievedChunkCount =
    readNumber(value.retrievedChunkCount) ?? readNumber(value.retrieved_chunk_count);
  const standaloneQuestion =
    readString(value.standaloneQuestion) ?? readString(value.standalone_question);

  if (!topics.length && !retrievedChunkCount && !standaloneQuestion) {
    return null;
  }

  return {
    retrievedChunkCount,
    standaloneQuestion,
    topics,
  };
}

export function normalizeSources(value) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map((chunk, index) => normalizeChunk(chunk, index)).filter(Boolean);
}

export function extractSourcesFromMetadata(event) {
  const rawChunks = Array.isArray(event.retrieved_chunks_final)
    ? event.retrieved_chunks_final
    : Array.isArray(event.chunks)
      ? event.chunks
      : Array.isArray(event.sources)
        ? event.sources
        : [];

  return normalizeSources(rawChunks);
}

export function extractSourceContext(event) {
  const directSourceContext = normalizeSourceContext(event.source_context);
  if (directSourceContext) {
    return directSourceContext;
  }

  const topics = [
    ...(event.structured_topics ?? []),
    ...(event.unique_topics_final ?? []),
  ].filter(Boolean);

  if (!topics.length && !event.retrieved_chunk_count && !event.standalone_question) {
    return null;
  }

  return {
    retrievedChunkCount: event.retrieved_chunk_count,
    standaloneQuestion: event.standalone_question,
    topics: [...new Set(topics)],
  };
}
