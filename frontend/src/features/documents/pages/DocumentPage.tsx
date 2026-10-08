import { ArrowLeftIcon } from 'lucide-react'
import { Link } from 'react-router'

import { PATHS } from '@/app/paths'
import type { Document } from '@/api/types'
import { AccessLevelBadge } from '@/components/AccessBadges'
import { ErrorState, NotFoundState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { VisibilityCard } from '@/components/VisibilityCard'
import { DeleteDocumentButton } from '@/features/documents/components/DeleteDocumentButton'
import { DocumentEditor } from '@/features/documents/components/DocumentEditor'
import { DocumentProjectLink } from '@/features/documents/components/DocumentProjectLink'
import { DocumentReader } from '@/features/documents/components/DocumentReader'
import { useDocument, useUpdateDocument } from '@/features/documents/hooks'
import { RequestEditAccessCard } from '@/features/sharing/components/RequestEditAccessCard'
import { ShareDialog } from '@/features/sharing/components/ShareDialog'
import { useIdParam } from '@/hooks/use-id-param'
import { can, canRequestEditAccess } from '@/lib/access'
import { formatDate } from '@/lib/format'
import { creatorName } from '@/lib/people'

export function DocumentPage() {
  const documentId = useIdParam('documentId')

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="self-start">
        <Link to={PATHS.documents}>
          <ArrowLeftIcon aria-hidden />
          Documents
        </Link>
      </Button>
      {documentId ? <DocumentLoader documentId={documentId} /> : <NotFoundState />}
    </>
  )
}

function DocumentLoader({ documentId }: { documentId: number }) {
  const document = useDocument(documentId)

  if (document.isError) {
    return <ErrorState error={document.error} onRetry={() => void document.refetch()} />
  }
  if (!document.data) {
    return <Skeleton className="h-96 w-full" aria-label="Loading document" />
  }
  return <DocumentView document={document.data} />
}

function DocumentView({ document }: { document: Document }) {
  const updateDocument = useUpdateDocument(document.id)

  return (
    <>
      <PageHeader
        title={document.title}
        actions={
          <>
            {can(document.access_level, 'RESHARE') && (
              <ShareDialog
                resource={{ kind: 'document', id: document.id }}
                name={document.title}
                visibility={document.visibility}
              />
            )}
            {can(document.access_level, 'DELETE') && <DeleteDocumentButton document={document} />}
          </>
        }
      />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        {can(document.access_level, 'WRITE') ? (
          <DocumentEditor document={document} />
        ) : (
          <DocumentReader document={document} />
        )}
        <div className="flex flex-col gap-6">
          {canRequestEditAccess(document.access_level) && (
            <RequestEditAccessCard documentId={document.id} />
          )}
          <Card>
            <CardHeader>
              <CardTitle>
                <h2>Details</h2>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
                <dt className="text-muted-foreground">Your access</dt>
                <dd>
                  <AccessLevelBadge level={document.access_level} />
                </dd>
                <dt className="text-muted-foreground">Project</dt>
                <dd>
                  {document.project ? (
                    <DocumentProjectLink projectId={document.project} />
                  ) : (
                    'None (personal document)'
                  )}
                </dd>
                <dt className="text-muted-foreground">Created by</dt>
                <dd className="break-all">{creatorName(document)}</dd>
                <dt className="text-muted-foreground">Created</dt>
                <dd>{formatDate(document.created)}</dd>
              </dl>
            </CardContent>
          </Card>
          <VisibilityCard
            resourceName="document"
            visibility={document.visibility}
            accessLevel={document.access_level}
            update={updateDocument}
          />
        </div>
      </div>
    </>
  )
}
