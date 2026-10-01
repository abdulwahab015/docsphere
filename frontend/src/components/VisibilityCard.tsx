import { useState } from 'react'
import { toast } from 'sonner'

import type { AccessLevel, Visibility } from '@/api/types'
import { VisibilityBadge } from '@/components/AccessBadges'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useSignedInMember } from '@/features/auth/hooks'
import { can, visibilityDescriptions } from '@/lib/access'

/** The part of a project's or document's update mutation this card uses. */
interface VisibilityUpdate {
  isPending: boolean
  mutate(
    payload: { visibility: Visibility },
    callbacks: { onSuccess: (updated: { visibility: Visibility }) => void; onError: () => void },
  ): void
}

interface VisibilityCardProps {
  /** e.g. "project" or "document", used in the wording. */
  resourceName: string
  visibility: Visibility
  accessLevel: AccessLevel | null
  /** The resource's update mutation; only `visibility` is sent. */
  update: VisibilityUpdate
}

/** Shows a project's or document's visibility, and lets its Owner flip it
 * after confirming (the same Owner-only bar as sharing). */
export function VisibilityCard({
  resourceName,
  visibility,
  accessLevel,
  update,
}: VisibilityCardProps) {
  const user = useSignedInMember()
  const [confirming, setConfirming] = useState(false)
  const descriptions = visibilityDescriptions(user.organization.name)
  const isPublic = visibility === 'PUBLIC'
  const nextVisibility = isPublic ? 'private' : 'public'
  const nextLabel = `Make ${nextVisibility}`
  const subject = resourceName.charAt(0).toUpperCase() + resourceName.slice(1)

  const changeVisibility = () =>
    update.mutate(
      { visibility: isPublic ? 'PRIVATE' : 'PUBLIC' },
      {
        onSuccess: (updated) => {
          toast.success(
            `${subject} is now ${updated.visibility === 'PUBLIC' ? 'public' : 'private'}.`,
          )
          setConfirming(false)
        },
        onError: () => {
          toast.error(`Couldn't change the ${resourceName}'s visibility.`)
          setConfirming(false)
        },
      },
    )

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Visibility</h2>
        </CardTitle>
        <CardDescription>{descriptions[visibility]}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center justify-between gap-3">
        <VisibilityBadge visibility={visibility} />
        {can(accessLevel, 'RESHARE') && (
          <ConfirmDialog
            open={confirming}
            onOpenChange={setConfirming}
            trigger={<Button variant="outline">{nextLabel}</Button>}
            title={`Make this ${resourceName} ${nextVisibility}?`}
            description={
              isPublic
                ? 'Members without a permission of their own will lose access.'
                : descriptions.PUBLIC
            }
            confirmLabel={nextLabel}
            onConfirm={changeVisibility}
            isPending={update.isPending}
          />
        )}
      </CardContent>
    </Card>
  )
}
