import { Button } from '../../../shared/components/Button';

export function NewChatButton({ disabled, onClick }) {
  return (
    <Button
      className="w-full rounded-2xl bg-sky-500 text-white hover:bg-sky-600 dark:bg-sky-500 dark:text-slate-950 dark:hover:bg-sky-400"
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      New chat
    </Button>
  );
}
