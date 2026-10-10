import type { Document } from '@/api/types'
import { Card, CardContent, CardDescription, CardHeader } from '@/components/ui/card'

/** A read-only view for Viewers. */
export function DocumentReader({ document }: { document: Document }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>
          You can view this document. Its owner can give you edit access.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {document.content ? (
          <p className="font-mono text-sm whitespace-pre-wrap">{document.content}</p>
        ) : (
          <p className="text-sm text-muted-foreground">This document is empty.</p>
        )}
      </CardContent>
    </Card>
  )
}
