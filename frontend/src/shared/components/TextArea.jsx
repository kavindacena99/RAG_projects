import { forwardRef } from 'react';

import { cn } from '../utils/cn';

export const TextArea = forwardRef(function TextArea({ className, ...props }, ref) {
  return (
    <textarea
      {...props}
      className={cn(
        'min-h-[88px] w-full resize-none rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-sky-400 focus:ring-4 focus:ring-sky-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:border-sky-500 dark:focus:ring-sky-500/15',
        className,
      )}
      ref={ref}
    />
  );
});
