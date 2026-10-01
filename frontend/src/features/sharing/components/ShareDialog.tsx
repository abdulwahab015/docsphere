import { UserPlusIcon } from 'lucide-react'
import { useState } from 'react'

import type { Visibility } from '@/api/types'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { useSignedInMember } from '@/features/auth/hooks'
import type { SharedResource, SharedResourceKind } from '@/features/sharing/api'
import { SharePanel } from '@/features/sharing/components/SharePanel'

const SHARING_DESCRIPTIONS: Record<SharedResourceKind, string> = {
  // Project access grants nothing on the documents inside it.
  project:
    "Choose who can open this project. Sharing it doesn't share its documents: share each one from its own page.",
  document: 'Choose who can open this document, and what they can do with it.',
}

interface ShareDialogProps {
  resource: SharedResource
  name: string
  visibility: Visibility
}

/** Who has access to a project or document, for its Owners to change. */
export function ShareDialog({ resource, name, visibility }: ShareDialogProps) {
  const user = useSignedInMember()
  const [open, setOpen] = useState(false)
  const isPublic = visibility === 'PUBLIC'

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <UserPlusIcon aria-hidden />
          Share
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Share &ldquo;{name}&rdquo;</DialogTitle>
          <DialogDescription>
            {SHARING_DESCRIPTIONS[resource.kind]}
            {isPublic &&
              ` Everyone in ${user.organization.name} can already view it, because it's public.`}
          </DialogDescription>
        </DialogHeader>
        <SharePanel
          resource={resource}
          isPublic={isPublic}
          onSharingGivenUp={() => setOpen(false)}
        />
      </DialogContent>
    </Dialog>
  )
}
