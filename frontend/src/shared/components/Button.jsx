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
    'bg-rose-500 text-white hover:bg-rose-600 disabled:bg-rose-300',
  ghost:
    'border border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50 disabled:text-slate-400',
  primary:
    'bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-400',
  secondary:
    'bg-sky-500 text-white hover:bg-sky-600 disabled:bg-sky-300',
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
