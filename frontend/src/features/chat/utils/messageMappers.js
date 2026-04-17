export function mapChatMessageFromApi(message) {
  return {
    content: message.content,
    created_at: message.created_at,
    id: String(message.id),
    role: message.role,
    sourceContext: null,
    sources: [],
  };
}
