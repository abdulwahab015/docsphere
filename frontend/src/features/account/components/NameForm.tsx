import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'

import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useUpdateName } from '@/features/account/hooks'
import { nameFormSchema } from '@/features/account/schemas'
import { useSignedInMember } from '@/features/auth/hooks'
import { applyApiErrors } from '@/lib/form-errors'

export function NameForm() {
  const user = useSignedInMember()
  const updateName = useUpdateName()
  const form = useForm({
    resolver: zodResolver(nameFormSchema),
    defaultValues: { name: user.name },
  })
  const { errors, isDirty } = form.formState

  const onSubmit = form.handleSubmit(({ name }) =>
    updateName.mutate(
      { name },
      {
        onSuccess: (updated) => {
          // The saved name becomes the form's starting point, so Save waits
          // for the next change.
          form.reset({ name: updated.name })
          toast.success(updated.name ? 'Name saved.' : 'Name removed.')
        },
        onError: (error) => applyApiErrors(error, form),
      },
    ),
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Name</h2>
        </CardTitle>
        <CardDescription>
          How your team sees you when you share, ask for access or invite them. Without a name, they
          see your email address.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className="flex max-w-md flex-col gap-4">
          <FormAlert message={errors.root?.server?.message} />
          <TextField
            label="Your name"
            autoComplete="name"
            error={errors.name?.message}
            {...form.register('name')}
          />
          <SubmitButton isPending={updateName.isPending} disabled={!isDirty} className="self-start">
            Save name
          </SubmitButton>
        </form>
      </CardContent>
    </Card>
  )
}
