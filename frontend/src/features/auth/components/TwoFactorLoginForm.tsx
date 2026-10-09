import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { parseApiError } from '@/api/errors'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { Button } from '@/components/ui/button'
import { useLoginWithTwoFactor } from '@/features/auth/hooks'
import { twoFactorLoginSchema } from '@/features/auth/schemas'
import { applyApiErrors } from '@/lib/form-errors'

interface TwoFactorLoginFormProps {
  /** From the password step: proof the password was right, for a few minutes. */
  token: string
  /** The password step has to be done again (its token expired); says why. */
  onExpired: (message: string) => void
}

/** The second step of logging in to an account with two-factor sign-in on: a
 * code from the authenticator app, or one of the recovery codes. On success
 * `RequireGuest` sees the new session and redirects. */
export function TwoFactorLoginForm({ token, onExpired }: TwoFactorLoginFormProps) {
  const [withRecoveryCode, setWithRecoveryCode] = useState(false)
  const login = useLoginWithTwoFactor()
  const form = useForm({ resolver: zodResolver(twoFactorLoginSchema), defaultValues: { otp: '' } })
  const { errors } = form.formState

  const onSubmit = form.handleSubmit(({ otp }) =>
    login.mutate(
      { two_factor_token: token, otp },
      {
        onError: (error) => {
          const expired = parseApiError(error).fieldErrors.two_factor_token
          if (expired) {
            onExpired(expired)
          } else {
            applyApiErrors(error, form)
          }
        },
      },
    ),
  )

  const switchCodeKind = () => {
    setWithRecoveryCode((current) => !current)
    form.reset({ otp: '' })
  }

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <FormAlert message={errors.root?.server?.message} />
      <TextField
        // A fresh input for the other kind of code, so the browser's
        // suggestions and keyboard follow.
        key={withRecoveryCode ? 'recovery-code' : 'app-code'}
        label={withRecoveryCode ? 'Recovery code' : 'Code from your app'}
        inputMode={withRecoveryCode ? 'text' : 'numeric'}
        autoComplete={withRecoveryCode ? 'off' : 'one-time-code'}
        error={errors.otp?.message}
        {...form.register('otp')}
      />
      <SubmitButton isPending={login.isPending}>Verify</SubmitButton>
      <Button type="button" variant="link" className="self-center" onClick={switchCodeKind}>
        {withRecoveryCode ? 'Use a code from your app' : 'Use a recovery code'}
      </Button>
    </form>
  )
}
