import type { FormEvent } from 'react'
import { useSearchParams } from 'react-router'

import { actionErrorMessage, UNEXPECTED_ERROR_MESSAGE } from '@/api/errors'
import { PATHS } from '@/app/paths'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextLink } from '@/components/TextLink'
import { AuthCard } from '@/features/auth/components/AuthCard'
import { useConfirmEmailChange } from '@/features/auth/hooks'

export function ConfirmEmailPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')

  if (!token) {
    return (
      <AuthCard
        title="Invalid confirmation link"
        description="This confirmation link is incomplete. Use the full link from your email."
      />
    )
  }

  return <EmailChangeConfirmation token={token} />
}

/** Asks before changing anything: confirming signs the account out everywhere,
 * so it shouldn't happen just because a link was opened. */
function EmailChangeConfirmation({ token }: { token: string }) {
  const confirmChange = useConfirmEmailChange()

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    confirmChange.mutate({ token })
  }

  if (confirmChange.isSuccess) {
    return (
      <AuthCard
        title="Email changed"
        description="You've been signed out everywhere. Log in with your new email address."
        footer={<TextLink to={PATHS.login}>Log in</TextLink>}
      />
    )
  }

  return (
    <AuthCard
      title="Confirm your new email"
      description="You'll sign in with the address this link was sent to from now on. Confirming signs you out on every device."
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <FormAlert
          message={
            confirmChange.isError
              ? actionErrorMessage(confirmChange.error, UNEXPECTED_ERROR_MESSAGE)
              : undefined
          }
        />
        <SubmitButton isPending={confirmChange.isPending}>Confirm new email</SubmitButton>
      </form>
    </AuthCard>
  )
}
