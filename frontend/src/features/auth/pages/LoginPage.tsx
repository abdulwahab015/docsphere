import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'

import { PATHS } from '@/app/paths'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { TextLink } from '@/components/TextLink'
import { AuthCard } from '@/features/auth/components/AuthCard'
import { useLogin } from '@/features/auth/hooks'
import { loginSchema } from '@/features/auth/schemas'
import { applyApiErrors } from '@/lib/form-errors'

export function LoginPage() {
  const login = useLogin()
  const form = useForm({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })
  const { errors } = form.formState

  // On success RequireGuest sees the new session and redirects.
  const onSubmit = form.handleSubmit((values) =>
    login.mutate(values, { onError: (error) => applyApiErrors(error, form) }),
  )

  return (
    <AuthCard
      title="Log in"
      description="Welcome back. Log in to your organization's workspace."
      footer={
        <p>
          New to DocSphere? <TextLink to={PATHS.signup}>Create an organization</TextLink>
        </p>
      }
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
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...form.register('password')}
        />
        <TextLink to={PATHS.forgotPassword} className="self-end text-sm">
          Forgot password?
        </TextLink>
        <SubmitButton isPending={login.isPending}>Log in</SubmitButton>
      </form>
    </AuthCard>
  )
}
