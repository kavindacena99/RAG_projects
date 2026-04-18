import { Button } from '../../../shared/components/Button';
import { MessageBubble } from './MessageBubble';

export function AssistantMessage({ message, onShowSources }) {
  const hasSources = Array.isArray(message.sources) && message.sources.length > 0;

  return (
    <MessageBubble
      actions={hasSources ? (
        <Button onClick={() => onShowSources(message)} size="sm" type="button" variant="ghost">
          Show sources
        </Button>
      ) : null}
      label="Assistant"
      message={message}
    />
  );
}
