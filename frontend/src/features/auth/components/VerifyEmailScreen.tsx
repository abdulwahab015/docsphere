import { toast } from 'sonner'

import { actionErrorMessage } from '@/api/errors'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { AuthCard } from '@/features/auth/components/AuthCard'
import { LogoutButton } from '@/features/auth/components/LogoutButton'
import { useResendVerificationEmail } from '@/features/auth/hooks'

/** What a new signup sees until they verify their address. Verifying in
 * another tab of this browser lets them in here at once; on another device,
 * when they come back to this tab. */
export function VerifyEmailScreen({ email }: { email: string }) {
  const resend = useResendVerificationEmail()

  const sendNewLink = () =>
    resend.mutate(undefined, {
      onSuccess: () => toast.success(`A new link is on its way to ${email}.`),
      onError: (error) =>
        toast.error(actionErrorMessage(error, "Couldn't send a new link. Try again later.")),
    })

  return (
    <AuthCard
      title="Check your email"
      description={
        <>
          We sent a link to <span className="font-medium break-all text-foreground">{email}</span>.
          Open it to verify your address and start using DocSphere.
        </>
      }
      footer="Wrong address? Log out and sign up again."
    >
      <div className="flex flex-col gap-2">
        <Button disabled={resend.isPending} onClick={sendNewLink}>
          {resend.isPending && <Spinner aria-hidden />}
          Send a new link
        </Button>
        <LogoutButton className="w-full" />
      </div>
    </AuthCard>
  )
}
