import { zodResolver } from '@hookform/resolvers/zod'
import { useId } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'

import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useRequestEmailChange } from '@/features/account/hooks'
import { changeEmailSchema } from '@/features/account/schemas'
import { useSignedInMember } from '@/features/auth/hooks'
import { applyApiErrors } from '@/lib/form-errors'

const EMPTY_VALUES = { new_email: '', current_password: '' }

export function ChangeEmailForm() {
  const user = useSignedInMember()
  const requestChange = useRequestEmailChange()
  const form = useForm({
    resolver: zodResolver(changeEmailSchema),
    defaultValues: EMPTY_VALUES,
  })
  const { errors } = form.formState
  const headingId = useId()

  const onSubmit = form.handleSubmit((values) =>
    requestChange.mutate(values, {
      onSuccess: () => {
        form.reset(EMPTY_VALUES)
        toast.success(`Check ${values.new_email} for a link to confirm the change.`)
      },
      onError: (error) => applyApiErrors(error, form),
    }),
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2 id={headingId}>Change email</h2>
        </CardTitle>
        <CardDescription>
          We'll email a link to the new address. Your email changes when you open it, and you'll be
          signed out on every device.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          onSubmit={onSubmit}
          noValidate
          aria-labelledby={headingId}
          className="flex max-w-md flex-col gap-4"
        >
          {/* Tells password managers which account the password belongs to. */}
          <input type="email" autoComplete="username" value={user.email} readOnly hidden />
          <FormAlert message={errors.root?.server?.message} />
          <TextField
            label="New email"
            type="email"
            autoComplete="email"
            error={errors.new_email?.message}
            {...form.register('new_email')}
          />
          <TextField
            label="Current password"
            type="password"
            autoComplete="current-password"
            error={errors.current_password?.message}
            {...form.register('current_password')}
          />
          <SubmitButton isPending={requestChange.isPending} className="self-start">
            Send confirmation link
          </SubmitButton>
        </form>
      </CardContent>
    </Card>
  )
}
