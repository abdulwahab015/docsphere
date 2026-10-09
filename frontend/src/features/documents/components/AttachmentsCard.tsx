import { DownloadIcon, PaperclipIcon, Trash2Icon } from 'lucide-react'
import { type ChangeEvent, useId, useState } from 'react'
import { toast } from 'sonner'

import type { Attachment, Document } from '@/api/types'
import { actionErrorMessage } from '@/api/errors'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ErrorState } from '@/components/ErrorState'
import { Pagination } from '@/components/Pagination'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldError, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  ATTACHMENT_ACCEPT,
  ATTACHMENT_HINT,
  ATTACHMENT_TOO_LARGE_MESSAGE,
  MAX_ATTACHMENT_BYTES,
} from '@/features/documents/attachments'
import {
  useAttachments,
  useDeleteAttachment,
  useDownloadAttachment,
  useUploadAttachment,
} from '@/features/documents/hooks'
import { can } from '@/lib/access'
import { formatBytes, formatDate } from '@/lib/format'
import { displayName } from '@/lib/people'

const FIRST_PAGE = 1
const PERCENT = 100

/** The files attached to a document. Anyone who can open the document can
 * download them; its Editors and Owners attach and delete them. */
export function AttachmentsCard({ document }: { document: Document }) {
  const [page, setPage] = useState(FIRST_PAGE)
  const attachments = useAttachments(document.id, page)
  const canEdit = can(document.access_level, 'WRITE')

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Attachments</h2>
        </CardTitle>
        <CardDescription>Anyone who can open this document can download these.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {attachments.isError ? (
          <ErrorState error={attachments.error} onRetry={() => void attachments.refetch()} />
        ) : !attachments.data ? (
          <Skeleton className="h-16 w-full" aria-label="Loading attachments" />
        ) : attachments.data.count ? (
          <>
            <ul aria-label="Attachments" className="flex flex-col divide-y">
              {attachments.data.results.map((attachment) => (
                <AttachmentRow
                  key={attachment.id}
                  documentId={document.id}
                  attachment={attachment}
                  canDelete={canEdit}
                />
              ))}
            </ul>
            <Pagination page={page} count={attachments.data.count} onPageChange={setPage} />
          </>
        ) : (
          <p className="text-sm text-muted-foreground">No files attached.</p>
        )}
        {canEdit && <AttachFileField documentId={document.id} />}
      </CardContent>
    </Card>
  )
}

interface AttachmentRowProps {
  documentId: number
  attachment: Attachment
  canDelete: boolean
}

function AttachmentRow({ documentId, attachment, canDelete }: AttachmentRowProps) {
  const download = useDownloadAttachment(documentId)
  const deleteAttachment = useDeleteAttachment(documentId)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const uploader = displayName({
    name: attachment.uploaded_by_name,
    email: attachment.uploaded_by_email,
  })

  const startDownload = () =>
    download.mutate(attachment, {
      onError: (error) =>
        toast.error(actionErrorMessage(error, "Couldn't download this file. Try again.")),
    })

  const confirmDelete = () =>
    deleteAttachment.mutate(attachment, {
      onSuccess: () => {
        setConfirmingDelete(false)
        toast.success(`Deleted ${attachment.name}.`)
      },
      onError: (error) => {
        setConfirmingDelete(false)
        toast.error(actionErrorMessage(error, "Couldn't delete this file. Try again."))
      },
    })

  return (
    <li className="flex items-start justify-between gap-2 py-2 text-sm">
      <div className="flex min-w-0 flex-col">
        <span className="font-medium break-all">{attachment.name}</span>
        <span className="text-muted-foreground">
          {formatBytes(attachment.size)} · {uploader} · {formatDate(attachment.created)}
        </span>
      </div>
      <div className="flex shrink-0 gap-1">
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Download ${attachment.name}`}
          disabled={download.isPending}
          onClick={startDownload}
        >
          <DownloadIcon aria-hidden />
        </Button>
        {canDelete && (
          <ConfirmDialog
            trigger={
              <Button variant="ghost" size="icon" aria-label={`Delete ${attachment.name}`}>
                <Trash2Icon aria-hidden />
              </Button>
            }
            title={`Delete ${attachment.name}?`}
            description="Nobody will be able to download it any more. This can't be undone."
            confirmLabel="Delete file"
            onConfirm={confirmDelete}
            isPending={deleteAttachment.isPending}
            open={confirmingDelete}
            onOpenChange={setConfirmingDelete}
            destructive
          />
        )}
      </div>
    </li>
  )
}

/** Picking a file attaches it straight away, showing how far the upload has
 * got. Files over the size limit are refused before uploading; the API checks
 * everything else, and its reason shows under the field. */
function AttachFileField({ documentId }: { documentId: number }) {
  const inputId = useId()
  const descriptionId = useId()
  const errorId = useId()
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | undefined>()
  const upload = useUploadAttachment(documentId, setProgress)

  const attach = (event: ChangeEvent<HTMLInputElement>) => {
    const input = event.target
    const file = input.files?.[0]
    if (!file) {
      return
    }
    // Lets the same file be picked again after a refusal.
    input.value = ''
    if (file.size > MAX_ATTACHMENT_BYTES) {
      setError(ATTACHMENT_TOO_LARGE_MESSAGE)
      return
    }
    setError(undefined)
    setProgress(0)
    upload.mutate(file, {
      onSuccess: (attachment) => toast.success(`Attached ${attachment.name}.`),
      onError: (uploadError) =>
        setError(actionErrorMessage(uploadError, "Couldn't attach this file. Try again.")),
    })
  }

  return (
    <Field data-invalid={Boolean(error) || undefined}>
      <FieldLabel htmlFor={inputId}>
        <PaperclipIcon aria-hidden className="size-4" />
        Attach a file
      </FieldLabel>
      <Input
        id={inputId}
        type="file"
        accept={ATTACHMENT_ACCEPT}
        disabled={upload.isPending}
        aria-invalid={Boolean(error) || undefined}
        aria-describedby={error ? `${descriptionId} ${errorId}` : descriptionId}
        onChange={attach}
      />
      <FieldDescription id={descriptionId}>{ATTACHMENT_HINT}</FieldDescription>
      {upload.isPending && (
        <progress
          aria-label="Uploading"
          className="h-1.5 w-full"
          max={PERCENT}
          value={Math.round(progress * PERCENT)}
        />
      )}
      {error && <FieldError id={errorId}>{error}</FieldError>}
    </Field>
  )
}
