import { AssistantMessage } from './AssistantMessage';

export function StreamingAssistantBubble({ message, onShowSources }) {
  return <AssistantMessage message={message} onShowSources={onShowSources} />;
}
