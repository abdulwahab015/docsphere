import { TriangleAlertIcon } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/lib/format'

interface EditConflictAlertProps {
  /** When the other version was saved. */
  savedAt: string
  isSaving: boolean
  onOverwrite: () => void
  onReload: () => void
}

/** Shown when a save was refused because someone else saved the document
 * after it was opened here: keep these changes over theirs, or take theirs. */
export function EditConflictAlert({
  savedAt,
  isSaving,
  onOverwrite,
  onReload,
}: EditConflictAlertProps) {
  return (
    <Alert variant="destructive">
      <TriangleAlertIcon />
      <AlertTitle>Someone else saved this document</AlertTitle>
      <AlertDescription className="flex flex-col items-start gap-3">
        Their version was saved on {formatDateTime(savedAt)}, after you opened it, so your changes
        haven&apos;t been saved. Keep yours to replace their version, or discard yours to see
        theirs.
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" disabled={isSaving} onClick={onOverwrite}>
            Overwrite with mine
          </Button>
          <Button type="button" size="sm" variant="outline" disabled={isSaving} onClick={onReload}>
            Reload theirs
          </Button>
        </div>
      </AlertDescription>
    </Alert>
  )
}
