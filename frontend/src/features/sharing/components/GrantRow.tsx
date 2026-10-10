import { XIcon } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { PATHS } from '@/app/paths'
import { actionErrorMessage } from '@/api/errors'
import type { AccessLevel, Grant } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { PersonLabel } from '@/components/PersonLabel'
import { Button } from '@/components/ui/button'
import { useSignedInMember } from '@/features/auth/hooks'
import type { SharedResource, SharedResourceKind } from '@/features/sharing/api'
import { AccessLevelSelect } from '@/features/sharing/components/AccessLevelSelect'
import { useRevokeAccess, useShareResource } from '@/features/sharing/hooks'
import { ACCESS_LEVEL_LABELS, can } from '@/lib/access'
import { displayName } from '@/lib/people'

const LIST_PATHS: Record<SharedResourceKind, string> = {
  project: PATHS.projects,
  document: PATHS.documents,
}

interface GrantRowProps {
  resource: SharedResource
  grant: Grant
  isPublic: boolean
  onSharingGivenUp: () => void
  onRevoked: () => void
}

/** One person with access: their level, which an Owner can change, and a
 * button to remove them. The API refuses to lower or remove the last Owner,
 * and that refusal is shown as it comes. */
export function GrantRow({
  resource,
  grant,
  isPublic,
  onSharingGivenUp,
  onRevoked,
}: GrantRowProps) {
  const signedInUser = useSignedInMember()
  const navigate = useNavigate()
  const share = useShareResource(resource)
  const revoke = useRevokeAccess(resource)
  // A level the signed-in user picked for themselves that would end their
  // Owner access - held until they confirm it.
  const [levelToConfirm, setLevelToConfirm] = useState<AccessLevel | null>(null)
  const [confirmingRemoval, setConfirmingRemoval] = useState(false)

  const isSignedInUser = grant.user === signedInUser.id
  const person = { name: grant.user_name, email: grant.user_email }
  const who = displayName(person)
  const shownLevel = share.isPending ? share.variables.access_level : grant.access_level

  const changeLevel = (level: AccessLevel) =>
    share.mutate(
      { user: grant.user, access_level: level },
      {
        onSuccess: (updated) => {
          const label = ACCESS_LEVEL_LABELS[updated.access_level]
          toast.success(
            isSignedInUser ? `You now have ${label} access.` : `${who} now has ${label} access.`,
          )
          setLevelToConfirm(null)
          if (isSignedInUser && !can(updated.access_level, 'RESHARE')) {
            onSharingGivenUp()
          }
        },
        onError: (error) => {
          toast.error(actionErrorMessage(error, `Couldn't change ${who}'s access.`))
          setLevelToConfirm(null)
        },
      },
    )

  const onLevelChange = (level: AccessLevel) => {
    if (isSignedInUser && !can(level, 'RESHARE')) {
      setLevelToConfirm(level)
    } else {
      changeLevel(level)
    }
  }

  const removeAccess = () =>
    revoke.mutate(grant.user, {
      onSuccess: () => {
        setConfirmingRemoval(false)
        if (!isSignedInUser) {
          toast.success(`Removed ${who}.`)
          onRevoked()
          return
        }
        toast.success('Your access was removed.')
        onSharingGivenUp()
        // A private resource can't be opened any more.
        if (!isPublic) {
          void navigate(LIST_PATHS[resource.kind])
        }
      },
      onError: (error) => {
        toast.error(actionErrorMessage(error, `Couldn't remove ${who}.`))
        setConfirmingRemoval(false)
      },
    })

  const subject = isSignedInUser ? "You'll" : "They'll"
  const removalConsequence = isPublic
    ? `${subject} still be able to view this ${resource.kind}, because it's public.`
    : `${subject} no longer be able to open this ${resource.kind}.`

  return (
    <li className="flex items-center gap-3 py-2">
      <span className="min-w-0 flex-1 text-sm">
        <PersonLabel person={person} note={isSignedInUser ? '(you)' : undefined} />
      </span>
      <AccessLevelSelect
        aria-label={`Access level for ${who}`}
        value={shownLevel}
        onChange={onLevelChange}
        disabled={share.isPending || revoke.isPending}
      />
      <ConfirmDialog
        open={confirmingRemoval}
        onOpenChange={setConfirmingRemoval}
        trigger={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Remove ${who}`}
            disabled={share.isPending}
          >
            <XIcon aria-hidden />
          </Button>
        }
        title={isSignedInUser ? 'Remove your own access?' : `Remove ${who}?`}
        description={removalConsequence}
        confirmLabel="Remove"
        destructive
        onConfirm={removeAccess}
        isPending={revoke.isPending}
      />
      {levelToConfirm && (
        <ConfirmDialog
          open
          // There's no trigger: the dialog opens when a level is picked, so it only ever closes.
          onOpenChange={() => setLevelToConfirm(null)}
          title="Give up Owner access?"
          description={`You won't be able to change who has access to this ${resource.kind} any more.`}
          confirmLabel="Change my access"
          onConfirm={() => changeLevel(levelToConfirm)}
          isPending={share.isPending}
        />
      )}
    </li>
  )
}
