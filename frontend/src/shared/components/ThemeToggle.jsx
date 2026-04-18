import { Button } from './Button';
import { useTheme } from '../hooks/useTheme';

export function ThemeToggle({ className }) {
  const { isDark, toggleTheme } = useTheme();

  return (
    <Button
      className={className}
      onClick={toggleTheme}
      size="sm"
      type="button"
      variant="ghost"
    >
      {isDark ? 'Light mode' : 'Dark mode'}
    </Button>
  );
}
