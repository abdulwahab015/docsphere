import { useState } from 'react'
import { toast } from 'sonner'

import { actionErrorMessage } from '@/api/errors'
import type { Organization } from '@/api/types'
import { PATHS } from '@/app/paths'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { TextLink } from '@/components/TextLink'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useSignedInMember } from '@/features/auth/hooks'
import { useUpdateOrganization } from '@/features/organization/hooks'

/** Whether everyone in the organization must sign in with a code from an
 * authenticator app. Requiring it is confirmed first, and needs the admin to
 * have it on themselves (the API refuses otherwise: they'd be the first one
 * asked to set it up). */
export function RequireTwoFactorCard({ organization }: { organization: Organization }) {
  const admin = useSignedInMember()
  const update = useUpdateOrganization()
  const [confirming, setConfirming] = useState(false)
  const required = organization.require_two_factor

  const save = (requireTwoFactor: boolean) =>
    update.mutate(
      { require_two_factor: requireTwoFactor },
      {
        onSuccess: () => {
          toast.success(
            requireTwoFactor
              ? 'Two-factor sign-in is now required.'
              : 'Two-factor sign-in is no longer required.',
          )
          setConfirming(false)
        },
        onError: (error) => {
          toast.error(actionErrorMessage(error, "Couldn't change the requirement."))
          setConfirming(false)
        },
      },
    )

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Two-factor sign-in</h2>
        </CardTitle>
        <CardDescription>
          {required
            ? 'Everyone must enter a code from an authenticator app when they log in. Anyone who hasn’t set one up is asked to before they can do anything else.'
            : 'Each member decides whether to log in with a code from an authenticator app as well as their password.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        {required ? (
          <Button
            variant="outline"
            className="self-start"
            disabled={update.isPending}
            onClick={() => save(false)}
          >
            Stop requiring it
          </Button>
        ) : (
          <>
            <Button
              className="self-start"
              disabled={!admin.two_factor_enabled}
              onClick={() => setConfirming(true)}
            >
              Require two-factor sign-in
            </Button>
            {!admin.two_factor_enabled && (
              <p className="text-muted-foreground">
                Turn it on for your own account first, in your{' '}
                <TextLink to={PATHS.account}>account settings</TextLink>.
              </p>
            )}
          </>
        )}
        <ConfirmDialog
          open={confirming}
          onOpenChange={setConfirming}
          title="Require two-factor sign-in?"
          description="Everyone who hasn’t set it up will be asked to before they can do anything else, and nobody will be able to turn it off."
          confirmLabel="Require it"
          onConfirm={() => save(true)}
          isPending={update.isPending}
        />
      </CardContent>
    </Card>
  )
}
