import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'

import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { useDeleteOrganization } from '@/features/organization/hooks'
import { applyApiErrors } from '@/lib/form-errors'

const EMPTY_VALUES = { name: '' }

/** Deleting the organization, confirmed by typing its name. Offered on the
 * Organization page and on a lapsed organization's subscribe screen, since
 * an organization that stopped paying may be the one leaving. */
export function DeleteOrganizationCard({ organizationName }: { organizationName: string }) {
  const [open, setOpen] = useState(false)
  const deleteOrganization = useDeleteOrganization()
  const form = useForm({ defaultValues: EMPTY_VALUES })
  const { errors } = form.formState
  const typedName = useWatch({ control: form.control, name: 'name' })

  const changeOpen = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      form.reset(EMPTY_VALUES)
    }
  }

  const onSubmit = form.handleSubmit((values) =>
    deleteOrganization.mutate(values, { onError: (error) => applyApiErrors(error, form) }),
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Delete organization</h2>
        </CardTitle>
        <CardDescription>
          Everyone is signed out and the subscription is cancelled at once. An admin can restore the
          organization for 30 days; after that it&apos;s removed for good with everything in it.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Dialog open={open} onOpenChange={changeOpen}>
          <DialogTrigger asChild>
            <Button variant="destructive">Delete organization</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete {organizationName}?</DialogTitle>
              <DialogDescription>
                Its projects, documents, files and members go with it once 30 days have passed.
              </DialogDescription>
            </DialogHeader>
            <form
              onSubmit={onSubmit}
              noValidate
              aria-label={`Delete ${organizationName}`}
              className="flex flex-col gap-4"
            >
              <FormAlert message={errors.root?.server?.message} />
              <TextField
                label={`Type "${organizationName}" to confirm`}
                autoComplete="off"
                error={errors.name?.message}
                {...form.register('name')}
              />
              <SubmitButton
                isPending={deleteOrganization.isPending}
                disabled={typedName.trim() !== organizationName}
                variant="destructive"
                className="self-start"
              >
                Delete organization
              </SubmitButton>
            </form>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  )
}
