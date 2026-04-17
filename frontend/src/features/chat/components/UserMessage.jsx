import { MessageBubble } from './MessageBubble';

export function UserMessage({ message }) {
  return <MessageBubble label="You" message={message} />;
}
