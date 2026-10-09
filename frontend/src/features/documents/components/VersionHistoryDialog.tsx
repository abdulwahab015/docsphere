import { ArrowLeftIcon, HistoryIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import type { Document, DocumentVersionDetail } from '@/api/types'
import { actionErrorMessage } from '@/api/errors'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ErrorState } from '@/components/ErrorState'
import { Pagination } from '@/components/Pagination'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { editConflictDocument } from '@/features/documents/api'
import {
  useDocumentVersion,
  useDocumentVersions,
  useUpdateDocument,
} from '@/features/documents/hooks'
import { formatDateTime } from '@/lib/format'
import { creatorName } from '@/lib/people'

const FIRST_PAGE = 1

/** Every saved version of a document's title and text, for its Editors and
 * Owners: read any of them, and restore one - which saves it as a new
 * version, so nothing in the history is ever lost. */
export function VersionHistoryDialog({ document }: { document: Document }) {
  const [open, setOpen] = useState(false)
  const [revision, setRevision] = useState<number | null>(null)

  const changeOpen = (nextOpen: boolean) => {
    setOpen(nextOpen)
    // Opening again starts from the list.
    if (!nextOpen) {
      setRevision(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <HistoryIcon aria-hidden />
          History
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        {revision ? (
          <VersionView
            document={document}
            revision={revision}
            onBack={() => setRevision(null)}
            onRestored={() => changeOpen(false)}
          />
        ) : (
          <VersionList document={document} onOpen={setRevision} />
        )}
      </DialogContent>
    </Dialog>
  )
}

interface VersionListProps {
  document: Document
  onOpen: (revision: number) => void
}

function VersionList({ document, onOpen }: VersionListProps) {
  const [page, setPage] = useState(FIRST_PAGE)
  const versions = useDocumentVersions(document.id, page)

  return (
    <>
      <DialogHeader>
        <DialogTitle>Version history</DialogTitle>
        <DialogDescription>
          A version is kept each time the title or text is saved. Open one to read it or restore it.
        </DialogDescription>
      </DialogHeader>
      {versions.isError ? (
        <ErrorState error={versions.error} onRetry={() => void versions.refetch()} />
      ) : !versions.data ? (
        <Skeleton className="h-40 w-full" aria-label="Loading versions" />
      ) : (
        <>
          <ul aria-label="Versions" className="flex flex-col divide-y rounded-lg border">
            {versions.data.results.map((version) => (
              <li key={version.revision}>
                <button
                  type="button"
                  onClick={() => onOpen(version.revision)}
                  className="flex w-full flex-col gap-1 px-3 py-2 text-left text-sm hover:bg-muted focus-visible:bg-muted focus-visible:outline-none"
                >
                  <span className="flex items-center gap-2 font-medium">
                    Version {version.revision}
                    {version.revision === document.revision && (
                      <Badge variant="secondary">Current</Badge>
                    )}
                  </span>
                  <span className="break-words">{version.title}</span>
                  <span className="text-muted-foreground">
                    {creatorName(version)} · {formatDateTime(version.created)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <Pagination page={page} count={versions.data.count} onPageChange={setPage} />
        </>
      )}
    </>
  )
}

interface VersionViewProps {
  document: Document
  revision: number
  onBack: () => void
  onRestored: () => void
}

function VersionView({ document, revision, onBack, onRestored }: VersionViewProps) {
  const version = useDocumentVersion(document.id, revision)

  return (
    <>
      <DialogHeader>
        <DialogTitle>Version {revision}</DialogTitle>
        <DialogDescription>
          {version.data
            ? `Saved by ${creatorName(version.data)} on ${formatDateTime(version.data.created)}.`
            : 'Loading this version.'}
        </DialogDescription>
      </DialogHeader>
      <Button variant="ghost" size="sm" className="self-start" onClick={onBack}>
        <ArrowLeftIcon aria-hidden />
        All versions
      </Button>
      {version.isError ? (
        <ErrorState error={version.error} onRetry={() => void version.refetch()} />
      ) : !version.data ? (
        <Skeleton className="h-40 w-full" aria-label="Loading version" />
      ) : (
        <>
          <article
            aria-label={`Version ${revision}`}
            className="flex flex-col gap-2 rounded-lg border p-4"
          >
            <h3 className="font-semibold break-words">{version.data.title}</h3>
            <p className="text-sm break-words whitespace-pre-wrap">
              {version.data.content || 'No text.'}
            </p>
          </article>
          {version.data.revision === document.revision ? (
            <p className="text-sm text-muted-foreground">This is the current version.</p>
          ) : (
            <RestoreVersionButton
              document={document}
              version={version.data}
              onRestored={onRestored}
            />
          )}
        </>
      )}
    </>
  )
}

interface RestoreVersionButtonProps {
  document: Document
  version: DocumentVersionDetail
  onRestored: () => void
}

/** Restoring is an ordinary save of the version's title and text, based on
 * the revision the history was opened against: if someone saved since, it's
 * refused like any stale save, and nothing is overwritten. */
function RestoreVersionButton({ document, version, onRestored }: RestoreVersionButtonProps) {
  const [confirming, setConfirming] = useState(false)
  const updateDocument = useUpdateDocument(document.id)

  const restore = () =>
    updateDocument.mutate(
      { title: version.title, content: version.content, base_revision: document.revision },
      {
        onSuccess: () => {
          setConfirming(false)
          onRestored()
          toast.success(`Restored version ${version.revision}.`)
        },
        onError: (error) => {
          setConfirming(false)
          toast.error(
            editConflictDocument(error)
              ? 'Someone saved this document since you opened its history. Check the newest version before restoring.'
              : actionErrorMessage(error, "Couldn't restore this version. Try again."),
          )
        },
      },
    )

  return (
    <ConfirmDialog
      trigger={<Button className="self-start">Restore this version</Button>}
      title={`Restore version ${version.revision}?`}
      description="The title and text go back to how they were in this version. It's saved as a new version, so nothing in the history is lost."
      confirmLabel="Restore"
      onConfirm={restore}
      isPending={updateDocument.isPending}
      open={confirming}
      onOpenChange={setConfirming}
    />
  )
}
