import { Button } from '../../../shared/components/Button';
import { MessageBubble } from './MessageBubble';

export function AssistantMessage({ message, onShowSources }) {
  return (
    <MessageBubble
      actions={
        <Button onClick={() => onShowSources(message)} size="sm" type="button" variant="ghost">
          Show sources
        </Button>
      }
      label="Assistant"
      message={message}
    />
  );
}
