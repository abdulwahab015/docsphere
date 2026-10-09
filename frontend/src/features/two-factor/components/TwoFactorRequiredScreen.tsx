import { AuthCard } from '@/features/auth/components/AuthCard'
import { LogoutButton } from '@/features/auth/components/LogoutButton'
import { TwoFactorSetup } from '@/features/two-factor/components/TwoFactorSetup'
import { useRereadTwoFactor } from '@/features/two-factor/hooks'

/** What someone sees, in place of the app, while their organization requires
 * two-factor sign-in and they haven't set it up. Once they've saved their
 * recovery codes, the session is re-read and lets them in. */
export function TwoFactorRequiredScreen({ organizationName }: { organizationName: string }) {
  const rereadTwoFactor = useRereadTwoFactor()

  return (
    <AuthCard
      title="Set up two-factor sign-in"
      description={`${organizationName} requires a code from an authenticator app each time you log in.`}
    >
      <div className="flex flex-col gap-4">
        <TwoFactorSetup onDone={rereadTwoFactor} />
        <LogoutButton className="w-full" />
      </div>
    </AuthCard>
  )
}
