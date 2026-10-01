import { zodResolver } from '@hookform/resolvers/zod'
import { MailPlusIcon } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'

import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { TextField } from '@/components/form/TextField'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { useSignedInMember } from '@/features/auth/hooks'
import { useCreateInvitation } from '@/features/team/hooks'
import { invitationSchema, type InvitationValues } from '@/features/team/schemas'
import { applyApiErrors } from '@/lib/form-errors'

const EMPTY_INVITATION: InvitationValues = { email: '' }

export function InviteDialog() {
  const user = useSignedInMember()
  const [open, setOpen] = useState(false)
  const createInvitation = useCreateInvitation()
  const form = useForm<InvitationValues>({
    resolver: zodResolver(invitationSchema),
    defaultValues: EMPTY_INVITATION,
  })

  const onOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      form.reset(EMPTY_INVITATION)
    }
  }

  const onSubmit = form.handleSubmit(({ email }) =>
    createInvitation.mutate(email, {
      onSuccess: (invitation) => {
        toast.success(`Invitation sent to ${invitation.email}.`)
        onOpenChange(false)
      },
      onError: (error) => applyApiErrors(error, form),
    }),
  )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <MailPlusIcon aria-hidden />
          Invite
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Invite someone</DialogTitle>
            <DialogDescription>
              They&apos;ll get an email with a link to join {user.organization.name} as a member.
            </DialogDescription>
          </DialogHeader>
          <FormAlert message={form.formState.errors.root?.server?.message} />
          <TextField
            label="Email"
            type="email"
            autoComplete="off"
            error={form.formState.errors.email?.message}
            {...form.register('email')}
          />
          <DialogFooter>
            <SubmitButton isPending={createInvitation.isPending}>Send invitation</SubmitButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
