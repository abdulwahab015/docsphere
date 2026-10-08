import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useNavigate, useSearchParams } from 'react-router'

import { PATHS } from '@/app/paths'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { AuthCard } from '@/features/auth/components/AuthCard'
import { useAcceptInvitation } from '@/features/auth/hooks'
import { acceptInvitationSchema, NAME_HINT, PASSWORD_HINT } from '@/features/auth/schemas'
import { applyApiErrors } from '@/lib/form-errors'

export function AcceptInvitePage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')

  if (!token) {
    return (
      <AuthCard
        title="Invalid invitation link"
        description="This invitation link is incomplete. Use the full link from your email, or ask your admin to resend it."
      />
    )
  }

  return <AcceptInviteForm token={token} />
}

function AcceptInviteForm({ token }: { token: string }) {
  const navigate = useNavigate()
  const acceptInvitation = useAcceptInvitation()
  const form = useForm({
    resolver: zodResolver(acceptInvitationSchema),
    defaultValues: { name: '', password: '', confirm_password: '' },
  })
  const { errors } = form.formState

  const onSubmit = form.handleSubmit(({ name, password }) =>
    acceptInvitation.mutate(
      { token, name, password },
      {
        onSuccess: () => navigate(PATHS.home, { replace: true }),
        onError: (error) => applyApiErrors(error, form),
      },
    ),
  )

  return (
    <AuthCard
      title="Join your organization"
      description="Choose a password to finish setting up your account."
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <FormAlert message={errors.root?.server?.message} />
        <TextField
          label="Your name (optional)"
          autoComplete="name"
          description={NAME_HINT}
          error={errors.name?.message}
          {...form.register('name')}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          description={PASSWORD_HINT}
          error={errors.password?.message}
          {...form.register('password')}
        />
        <TextField
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          error={errors.confirm_password?.message}
          {...form.register('confirm_password')}
        />
        <SubmitButton isPending={acceptInvitation.isPending}>Create account</SubmitButton>
      </form>
    </AuthCard>
  )
}
