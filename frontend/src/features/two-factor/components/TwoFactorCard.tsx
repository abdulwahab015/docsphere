import type { TwoFactorStatus } from '@/api/types'
import { ErrorState } from '@/components/ErrorState'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useSignedInMember } from '@/features/auth/hooks'
import { NewRecoveryCodesDialog } from '@/features/two-factor/components/NewRecoveryCodesDialog'
import { TurnOffTwoFactorDialog } from '@/features/two-factor/components/TurnOffTwoFactorDialog'
import { TurnOnTwoFactorDialog } from '@/features/two-factor/components/TurnOnTwoFactorDialog'
import { useTwoFactorStatus } from '@/features/two-factor/hooks'

// From this many recovery codes down, the card suggests making new ones.
const FEW_RECOVERY_CODES = 3

function recoveryCodesNote(left: number) {
  if (!left) {
    return 'You have no recovery codes left. Make new ones, so you can still log in if you lose your phone.'
  }
  const count = `You have ${left} recovery code${left === 1 ? '' : 's'} left.`
  return left <= FEW_RECOVERY_CODES ? `${count} Make new ones before you run out.` : count
}

/** The account's two-factor sign-in: turn it on, or - once it's on - make
 * new recovery codes or turn it off. */
export function TwoFactorCard() {
  const status = useTwoFactorStatus()

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2 className="flex items-center gap-2">
            Two-factor sign-in
            {status.data?.enabled && <Badge variant="secondary">On</Badge>}
          </h2>
        </CardTitle>
        <CardDescription>
          A code from an authenticator app each time you log in, as well as your password, so a
          stolen password alone can&apos;t get into your account.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {status.isError ? (
          <ErrorState error={status.error} onRetry={() => void status.refetch()} />
        ) : status.data ? (
          status.data.enabled ? (
            <TwoFactorOn status={status.data} />
          ) : (
            <TurnOnTwoFactorDialog />
          )
        ) : (
          <Skeleton className="h-9 w-56" aria-label="Loading two-factor sign-in" />
        )}
      </CardContent>
    </Card>
  )
}

function TwoFactorOn({ status }: { status: TwoFactorStatus }) {
  const member = useSignedInMember()
  const required = member.organization.require_two_factor

  return (
    <div className="flex flex-col gap-4 text-sm">
      <p className="text-muted-foreground">{recoveryCodesNote(status.recovery_codes_left)}</p>
      <div className="flex flex-wrap gap-2">
        <NewRecoveryCodesDialog />
        <TurnOffTwoFactorDialog disabled={required} />
      </div>
      {required && (
        <p className="text-muted-foreground">
          {member.organization.name} requires two-factor sign-in, so it can&apos;t be turned off.
        </p>
      )}
    </div>
  )
}
