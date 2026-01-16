import * as React from "react"
import { cn } from "../../lib/utils"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'secondary' | 'destructive' | 'outline' | 'success' | 'warning'
}

function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-md px-2.5 py-0.5 text-xs font-semibold transition-colors",
        {
          'bg-blue-600 text-white': variant === 'default',
          'bg-gray-200 text-gray-800': variant === 'secondary',
          'bg-red-600 text-white': variant === 'destructive',
          'border border-gray-300 text-gray-700 bg-white': variant === 'outline',
          'bg-green-600 text-white': variant === 'success',
          'bg-amber-500 text-white': variant === 'warning',
        },
        className
      )}
      {...props}
    />
  )
}

export { Badge }
