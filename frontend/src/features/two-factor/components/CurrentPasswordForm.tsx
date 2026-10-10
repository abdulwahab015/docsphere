import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'

import type { CurrentPasswordPayload } from '@/api/types'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { useSignedInUser } from '@/features/auth/hooks'
import { currentPasswordSchema } from '@/features/two-factor/schemas'
import { applyApiErrors } from '@/lib/form-errors'

interface CurrentPasswordFormProps {
  /** Names the form for assistive technology. */
  label: string
  submitLabel: string
  destructive?: boolean
  isPending: boolean
  /** Called with the password and a callback that puts the API's reasons on the form. */
  onSubmit: (values: CurrentPasswordPayload, reportError: (error: unknown) => void) => void
}

/** A change to two-factor sign-in, confirmed with the person's password. */
export function CurrentPasswordForm({
  label,
  submitLabel,
  destructive,
  isPending,
  onSubmit,
}: CurrentPasswordFormProps) {
  const user = useSignedInUser()
  const form = useForm({
    resolver: zodResolver(currentPasswordSchema),
    defaultValues: { current_password: '' },
  })
  const { errors } = form.formState

  const submit = form.handleSubmit((values) =>
    onSubmit(values, (error) => applyApiErrors(error, form)),
  )

  return (
    <form onSubmit={submit} noValidate aria-label={label} className="flex flex-col gap-4">
      {/* Tells password managers which account the password belongs to. */}
      <input type="email" autoComplete="username" value={user.email} readOnly hidden />
      <FormAlert message={errors.root?.server?.message} />
      <TextField
        label="Current password"
        type="password"
        autoComplete="current-password"
        error={errors.current_password?.message}
        {...form.register('current_password')}
      />
      <SubmitButton
        isPending={isPending}
        variant={destructive ? 'destructive' : 'default'}
        className="self-start"
      >
        {submitLabel}
      </SubmitButton>
    </form>
  )
}
