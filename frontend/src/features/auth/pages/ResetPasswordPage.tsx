import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useSearchParams } from 'react-router'

import { PATHS } from '@/app/paths'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { TextLink } from '@/components/TextLink'
import { AuthCard } from '@/features/auth/components/AuthCard'
import { useConfirmPasswordReset } from '@/features/auth/hooks'
import { PASSWORD_HINT, resetPasswordSchema } from '@/features/auth/schemas'
import { applyApiErrors } from '@/lib/form-errors'

const requestNewLink = <TextLink to={PATHS.forgotPassword}>Request a new link</TextLink>

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const uid = searchParams.get('uid')
  const token = searchParams.get('token')

  if (!uid || !token) {
    return (
      <AuthCard
        title="Invalid reset link"
        description="This password reset link is incomplete. Use the full link from your email."
        footer={requestNewLink}
      />
    )
  }

  return <ResetPasswordForm uid={uid} token={token} />
}

function ResetPasswordForm({ uid, token }: { uid: string; token: string }) {
  const confirmReset = useConfirmPasswordReset()
  const form = useForm({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: '', confirm_password: '' },
  })
  const { errors } = form.formState

  const onSubmit = form.handleSubmit(({ new_password }) =>
    confirmReset.mutate(
      { uid, token, new_password },
      { onError: (error) => applyApiErrors(error, form) },
    ),
  )

  if (confirmReset.isSuccess) {
    return (
      <AuthCard
        title="Password updated"
        description="Your password has been changed and you've been signed out everywhere."
        footer={<TextLink to={PATHS.login}>Log in with your new password</TextLink>}
      />
    )
  }

  return (
    <AuthCard title="Choose a new password" footer={requestNewLink}>
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <FormAlert message={errors.root?.server?.message} />
        <TextField
          label="New password"
          type="password"
          autoComplete="new-password"
          description={PASSWORD_HINT}
          error={errors.new_password?.message}
          {...form.register('new_password')}
        />
        <TextField
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          error={errors.confirm_password?.message}
          {...form.register('confirm_password')}
        />
        <SubmitButton isPending={confirmReset.isPending}>Update password</SubmitButton>
      </form>
    </AuthCard>
  )
}
