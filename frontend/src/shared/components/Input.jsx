import { forwardRef } from 'react';

import { cn } from '../utils/cn';

export const Input = forwardRef(function Input({ className, ...props }, ref) {
  return (
    <input
      {...props}
      className={cn(
        'h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-sky-400 focus:ring-4 focus:ring-sky-100',
        className,
      )}
      ref={ref}
    />
  );
});
