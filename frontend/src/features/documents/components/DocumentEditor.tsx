import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, type KeyboardEvent, useEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'

import type { Document } from '@/api/types'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextareaField } from '@/components/form/TextareaField'
import { TextField } from '@/components/form/TextField'
import { Card, CardContent } from '@/components/ui/card'
import { UnsavedChangesGuard } from '@/components/UnsavedChangesGuard'
import { editConflictDocument } from '@/features/documents/api'
import { EditConflictAlert } from '@/features/documents/components/EditConflictAlert'
import { useUpdateDocument } from '@/features/documents/hooks'
import { documentContentSchema, type DocumentContentValues } from '@/features/documents/schemas'
import { applyApiErrors } from '@/lib/form-errors'
import { formatDateTime } from '@/lib/format'

const CONTENT_ROWS = 18

function contentValues(document: Document): DocumentContentValues {
  return { title: document.title, content: document.content ?? '' }
}

/** Edits a document's title and content (Editor and above). A save says
 * which revision the text started from; if someone else saved in between, the
 * API refuses it and the editor offers to overwrite theirs or reload it.
 * Leaving with unsaved changes asks first. */
export function DocumentEditor({ document }: { document: Document }) {
  const update = useUpdateDocument(document.id)
  const form = useForm<DocumentContentValues>({
    resolver: zodResolver(documentContentSchema),
    defaultValues: contentValues(document),
  })
  const { errors, isDirty } = form.formState
  const [hasConflict, setHasConflict] = useState(false)
  // The revision the text in the form started from - what a save says it's
  // based on. Only read when saving, so it needn't re-render anything.
  const baseRevision = useRef(document.revision)

  const startFrom = (version: Document) => {
    form.reset(contentValues(version))
    baseRevision.current = version.revision
  }

  // A newer revision fetched in the background replaces the text only while
  // nothing is unsaved: it must never overwrite what's being typed, and the
  // next save is then checked against it.
  useEffect(() => {
    if (document.revision !== baseRevision.current && !isDirty) {
      form.reset(contentValues(document))
      baseRevision.current = document.revision
    }
  }, [document, form, isDirty])

  /** Saves the form; `revision` replaces the one the text started from. */
  const saveFrom = (revision?: number) =>
    form.handleSubmit(({ title, content }) =>
      update.mutate(
        { title, content, base_revision: revision || baseRevision.current },
        {
          onSuccess: (saved) => {
            setHasConflict(false)
            startFrom(saved)
            toast.success('Document saved.')
          },
          onError: (error) => {
            // The hook has already put their version in the cache.
            if (editConflictDocument(error)) {
              setHasConflict(true)
            } else {
              applyApiErrors(error, form)
            }
          },
        },
      ),
    )
  const save = (event?: BaseSyntheticEvent) => saveFrom()(event)

  const reloadTheirs = () => {
    setHasConflict(false)
    startFrom(document)
  }

  // ⌘S / Ctrl+S while typing saves, instead of the browser's "save page".
  const saveOnShortcut = (event: KeyboardEvent) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
      event.preventDefault()
      void save()
    }
  }

  return (
    <Card>
      <CardContent>
        <form onSubmit={save} noValidate className="flex flex-col gap-4">
          {hasConflict && (
            <EditConflictAlert
              savedAt={document.modified}
              isSaving={update.isPending}
              // Theirs is in the cache now: saving from it replaces it with this text.
              onOverwrite={() => void saveFrom(document.revision)()}
              onReload={reloadTheirs}
            />
          )}
          <FormAlert message={errors.root?.server?.message} />
          <TextField
            label="Title"
            autoComplete="off"
            onKeyDown={saveOnShortcut}
            error={errors.title?.message}
            {...form.register('title')}
          />
          <TextareaField
            label="Content"
            rows={CONTENT_ROWS}
            className="font-mono text-sm"
            onKeyDown={saveOnShortcut}
            error={errors.content?.message}
            {...form.register('content')}
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {isDirty ? 'Unsaved changes' : `Saved ${formatDateTime(document.modified)}`}
            </p>
            <SubmitButton isPending={update.isPending} disabled={!isDirty}>
              Save
            </SubmitButton>
          </div>
        </form>
        <UnsavedChangesGuard when={isDirty} />
      </CardContent>
    </Card>
  )
}
