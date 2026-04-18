import { forwardRef } from 'react';

import { cn } from '../utils/cn';
import { Spinner } from './Spinner';

const sizeClasses = {
  lg: 'h-12 px-5 text-sm',
  md: 'h-11 px-4 text-sm',
  sm: 'h-9 px-3 text-xs',
};

const variantClasses = {
  danger:
    'bg-rose-500 text-white hover:bg-rose-600 disabled:bg-rose-300 dark:bg-rose-500 dark:text-white dark:hover:bg-rose-400',
  ghost:
    'border border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50 disabled:text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-800 dark:disabled:text-slate-500',
  primary:
    'bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-400 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white dark:disabled:bg-slate-600 dark:disabled:text-slate-300',
  secondary:
    'bg-sky-500 text-white hover:bg-sky-600 disabled:bg-sky-300 dark:bg-sky-500 dark:text-slate-950 dark:hover:bg-sky-400 dark:disabled:bg-sky-800 dark:disabled:text-slate-300',
};

export const Button = forwardRef(function Button(
  {
    children,
    className,
    disabled,
    isLoading = false,
    size = 'md',
    variant = 'primary',
    ...props
  },
  ref,
) {
  return (
    <button
      {...props}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-xl font-medium transition focus:outline-none focus:ring-2 focus:ring-sky-300 disabled:cursor-not-allowed',
        sizeClasses[size],
        variantClasses[variant],
        className,
      )}
      disabled={disabled || isLoading}
      ref={ref}
    >
      {isLoading ? <Spinner /> : null}
      <span>{children}</span>
    </button>
  );
});
