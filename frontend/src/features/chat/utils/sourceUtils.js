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

export function extractSourcesFromMetadata(event) {
  const rawChunks = Array.isArray(event.retrieved_chunks_final)
    ? event.retrieved_chunks_final
    : Array.isArray(event.chunks)
      ? event.chunks
      : [];

  return rawChunks
    .map((chunk, index) => normalizeChunk(chunk, index))
    .filter(Boolean);
}

export function extractSourceContext(event) {
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
