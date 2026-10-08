import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'

import { PATHS } from '@/app/paths'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { TextLink } from '@/components/TextLink'
import { AuthCard } from '@/features/auth/components/AuthCard'
import { useSignup } from '@/features/auth/hooks'
import { NAME_HINT, PASSWORD_HINT, signupSchema } from '@/features/auth/schemas'
import { applyApiErrors } from '@/lib/form-errors'

export function SignupPage() {
  const signup = useSignup()
  const form = useForm({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      name: '',
      billing_email: '',
      admin_name: '',
      admin_email: '',
      admin_password: '',
      confirm_password: '',
    },
  })
  const { errors } = form.formState

  // On success RequireGuest sees the new session and redirects.
  const onSubmit = form.handleSubmit(
    ({ name, billing_email, admin_name, admin_email, admin_password }) =>
      signup.mutate(
        { name, billing_email: billing_email || null, admin_name, admin_email, admin_password },
        { onError: (error) => applyApiErrors(error, form) },
      ),
  )

  return (
    <AuthCard
      title="Create your organization"
      description="You'll be its first admin, and can invite your team afterwards."
      footer={
        <p>
          Already have an account? <TextLink to={PATHS.login}>Log in</TextLink>
        </p>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <FormAlert message={errors.root?.server?.message} />
        <TextField
          label="Organization name"
          autoComplete="organization"
          error={errors.name?.message}
          {...form.register('name')}
        />
        <TextField
          label="Billing email (optional)"
          type="email"
          autoComplete="email"
          description="Where invoices go. Leave blank to decide later."
          error={errors.billing_email?.message}
          {...form.register('billing_email')}
        />
        <TextField
          label="Your name (optional)"
          autoComplete="name"
          description={NAME_HINT}
          error={errors.admin_name?.message}
          {...form.register('admin_name')}
        />
        <TextField
          label="Your email"
          type="email"
          autoComplete="email"
          error={errors.admin_email?.message}
          {...form.register('admin_email')}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          description={PASSWORD_HINT}
          error={errors.admin_password?.message}
          {...form.register('admin_password')}
        />
        <TextField
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          error={errors.confirm_password?.message}
          {...form.register('confirm_password')}
        />
        <SubmitButton isPending={signup.isPending}>Create organization</SubmitButton>
      </form>
    </AuthCard>
  )
}
