import { zodResolver } from '@hookform/resolvers/zod'
import { useId } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'

import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useChangePassword } from '@/features/account/hooks'
import { changePasswordSchema } from '@/features/account/schemas'
import { useSignedInMember } from '@/features/auth/hooks'
import { PASSWORD_HINT } from '@/features/auth/schemas'
import { applyApiErrors } from '@/lib/form-errors'

const EMPTY_VALUES = { current_password: '', new_password: '', confirm_password: '' }

export function ChangePasswordForm() {
  const user = useSignedInMember()
  const changePassword = useChangePassword()
  const form = useForm({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: EMPTY_VALUES,
  })
  const { errors } = form.formState
  const headingId = useId()

  const onSubmit = form.handleSubmit(({ current_password, new_password }) =>
    changePassword.mutate(
      { current_password, new_password },
      {
        onSuccess: () => {
          form.reset(EMPTY_VALUES)
          toast.success('Password changed. Your other devices have been signed out.')
        },
        onError: (error) => applyApiErrors(error, form),
      },
    ),
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2 id={headingId}>Password</h2>
        </CardTitle>
        <CardDescription>
          Changing your password signs you out on your other devices. You stay signed in here.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          onSubmit={onSubmit}
          noValidate
          aria-labelledby={headingId}
          className="flex max-w-md flex-col gap-4"
        >
          {/* Tells password managers which account the new password belongs to. */}
          <input type="email" autoComplete="username" value={user.email} readOnly hidden />
          <FormAlert message={errors.root?.server?.message} />
          <TextField
            label="Current password"
            type="password"
            autoComplete="current-password"
            error={errors.current_password?.message}
            {...form.register('current_password')}
          />
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
          <SubmitButton isPending={changePassword.isPending} className="self-start">
            Change password
          </SubmitButton>
        </form>
      </CardContent>
    </Card>
  )
}
