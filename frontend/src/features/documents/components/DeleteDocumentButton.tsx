import { Trash2Icon } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { PATHS } from '@/app/paths'
import type { Document } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Button } from '@/components/ui/button'
import { useDeleteDocument } from '@/features/documents/hooks'

export function DeleteDocumentButton({ document }: { document: Document }) {
  const navigate = useNavigate()
  const [confirming, setConfirming] = useState(false)
  const deleteDocument = useDeleteDocument(document.id)

  const moveToTrash = () =>
    deleteDocument.mutate(undefined, {
      onSuccess: () => {
        toast.success(`Moved "${document.title}" to your trash.`)
        void navigate(PATHS.documents)
      },
      onError: () => {
        toast.error(`Couldn't delete "${document.title}".`)
        setConfirming(false)
      },
    })

  return (
    <ConfirmDialog
      open={confirming}
      onOpenChange={setConfirming}
      trigger={
        <Button variant="destructive">
          <Trash2Icon aria-hidden />
          Delete
        </Button>
      }
      title={`Delete "${document.title}"?`}
      description="It disappears for everyone. You can restore it from your document trash."
      confirmLabel="Delete document"
      onConfirm={moveToTrash}
      isPending={deleteDocument.isPending}
      destructive
    />
  )
}
