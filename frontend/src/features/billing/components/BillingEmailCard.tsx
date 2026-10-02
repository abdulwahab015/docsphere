import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'

import type { Organization } from '@/api/types'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { billingEmailSchema } from '@/features/billing/schemas'
import { useUpdateOrganization } from '@/features/organization/hooks'
import { applyApiErrors } from '@/lib/form-errors'

/** Where Stripe sends invoices and receipts. Checkout needs one. */
export function BillingEmailCard({ organization }: { organization: Organization }) {
  const update = useUpdateOrganization()
  const form = useForm({
    resolver: zodResolver(billingEmailSchema),
    values: { billing_email: organization.billing_email ?? '' },
  })
  const { errors, isDirty } = form.formState

  const onSubmit = form.handleSubmit(({ billing_email }) =>
    update.mutate(
      { billing_email: billing_email || null },
      {
        onSuccess: () => toast.success('Billing email saved.'),
        onError: (error) => applyApiErrors(error, form),
      },
    ),
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Billing email</h2>
        </CardTitle>
        <CardDescription>Where invoices and receipts are sent.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className="flex max-w-md flex-col gap-4">
          <FormAlert message={errors.root?.server?.message} />
          <TextField
            label="Billing email"
            type="email"
            autoComplete="email"
            error={errors.billing_email?.message}
            {...form.register('billing_email')}
          />
          <SubmitButton isPending={update.isPending} disabled={!isDirty} className="self-start">
            Save billing email
          </SubmitButton>
        </form>
      </CardContent>
    </Card>
  )
}
