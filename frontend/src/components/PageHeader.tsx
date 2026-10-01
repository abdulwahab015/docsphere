import type { ReactNode } from 'react'

import { usePageTitle } from '@/hooks/use-page-title'

interface PageHeaderProps {
  title: string
  description?: ReactNode
  actions?: ReactNode
}

/** A page's heading. Also sets the browser tab's title to match, so the two
 * can't drift apart. */
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  usePageTitle(title)

  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  )
}
