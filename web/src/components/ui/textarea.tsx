import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export function Textarea({ className, ...props }: ComponentProps<'textarea'>) {
  return (
    <textarea
      className={cn(
        'flex min-h-36 w-full rounded-sm border border-ink-700 bg-ink-950/70 px-4 py-3 text-base leading-relaxed text-ink-100 placeholder:text-ink-500 focus-visible:border-ink-300 focus-visible:outline-none disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}
