import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'

import type { Organization } from '@/api/types'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useUpdateOrganization } from '@/features/organization/hooks'
import { organizationSettingsSchema } from '@/features/organization/schemas'
import { applyApiErrors } from '@/lib/form-errors'

export function OrganizationSettingsForm({ organization }: { organization: Organization }) {
  const update = useUpdateOrganization()
  const form = useForm({
    resolver: zodResolver(organizationSettingsSchema),
    values: { name: organization.name, billing_email: organization.billing_email ?? '' },
  })
  const { errors, isDirty } = form.formState

  const onSubmit = form.handleSubmit(({ name, billing_email }) =>
    update.mutate(
      { name, billing_email: billing_email || null },
      {
        onSuccess: () => toast.success('Organization details saved.'),
        onError: (error) => applyApiErrors(error, form),
      },
    ),
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Details</h2>
        </CardTitle>
        <CardDescription>How your organization appears to its members.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className="flex max-w-md flex-col gap-4">
          <FormAlert message={errors.root?.server?.message} />
          <TextField
            label="Organization name"
            autoComplete="organization"
            error={errors.name?.message}
            {...form.register('name')}
          />
          <TextField
            label="Billing email"
            type="email"
            autoComplete="email"
            description="Where invoices go. Leave blank if you don't have one yet."
            error={errors.billing_email?.message}
            {...form.register('billing_email')}
          />
          <SubmitButton isPending={update.isPending} disabled={!isDirty} className="self-start">
            Save changes
          </SubmitButton>
        </form>
      </CardContent>
    </Card>
  )
}
