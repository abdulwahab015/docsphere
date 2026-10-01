import { zodResolver } from '@hookform/resolvers/zod'
import type { KeyboardEvent } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'

import type { Document } from '@/api/types'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextareaField } from '@/components/form/TextareaField'
import { TextField } from '@/components/form/TextField'
import { Card, CardContent } from '@/components/ui/card'
import { UnsavedChangesGuard } from '@/components/UnsavedChangesGuard'
import { useUpdateDocument } from '@/features/documents/hooks'
import { documentContentSchema, type DocumentContentValues } from '@/features/documents/schemas'
import { applyApiErrors } from '@/lib/form-errors'
import { formatDateTime } from '@/lib/format'

const CONTENT_ROWS = 18

function contentValues(document: Document): DocumentContentValues {
  return { title: document.title, content: document.content ?? '' }
}

/** Edits a document's title and content (Editor and above). Saving replaces
 * the stored text - the API keeps whichever save arrives last - so leaving
 * with unsaved changes asks first. */
export function DocumentEditor({ document }: { document: Document }) {
  const update = useUpdateDocument(document.id)
  const form = useForm<DocumentContentValues>({
    resolver: zodResolver(documentContentSchema),
    values: contentValues(document),
    // A background refresh of the document must never overwrite what's being typed.
    resetOptions: { keepDirtyValues: true },
  })
  const { errors, isDirty } = form.formState

  const save = form.handleSubmit(({ title, content }) =>
    update.mutate(
      { title, content },
      {
        onSuccess: (saved) => {
          form.reset(contentValues(saved))
          toast.success('Document saved.')
        },
        onError: (error) => applyApiErrors(error, form),
      },
    ),
  )

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
