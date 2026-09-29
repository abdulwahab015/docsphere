import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'

import { PATHS } from '@/app/paths'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { TextLink } from '@/components/TextLink'
import { AuthCard } from '@/features/auth/components/AuthCard'
import { useRequestPasswordReset } from '@/features/auth/hooks'
import { forgotPasswordSchema } from '@/features/auth/schemas'
import { applyApiErrors } from '@/lib/form-errors'

const backToLogin = <TextLink to={PATHS.login}>Back to log in</TextLink>

export function ForgotPasswordPage() {
  const requestReset = useRequestPasswordReset()
  const form = useForm({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: '' },
  })
  const { errors } = form.formState

  const onSubmit = form.handleSubmit((values) =>
    requestReset.mutate(values, { onError: (error) => applyApiErrors(error, form) }),
  )

  // The API answers the same whether or not the address has an account, so
  // this message mustn't claim an email was sent.
  if (requestReset.isSuccess) {
    return (
      <AuthCard
        title="Check your email"
        description={`If an account exists for ${requestReset.variables.email}, we've sent a link to reset its password.`}
        footer={backToLogin}
      />
    )
  }

  return (
    <AuthCard
      title="Reset your password"
      description="Enter your account's email and we'll send you a reset link."
      footer={backToLogin}
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <FormAlert message={errors.root?.server?.message} />
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...form.register('email')}
        />
        <SubmitButton isPending={requestReset.isPending}>Send reset link</SubmitButton>
      </form>
    </AuthCard>
  )
}
