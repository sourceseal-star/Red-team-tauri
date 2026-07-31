import * as React from 'react'
import { cn } from '../../lib/utils'

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary'
}
export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold',
        variant === 'default' && 'bg-blue-600 text-white',
        variant === 'destructive' && 'bg-red-600 text-white',
        variant === 'outline' && 'border border-border',
        variant === 'secondary' && 'bg-muted text-muted-foreground',
        className
      )}
      {...props}
    />
  )
}
