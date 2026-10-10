import type { ComponentProps } from 'react'
import { Link } from 'react-router'

import { cn } from '@/lib/utils'

export function TextLink({ className, ...linkProps }: ComponentProps<typeof Link>) {
  return (
    <Link
      className={cn('font-medium text-foreground underline underline-offset-4', className)}
      {...linkProps}
    />
  )
}
