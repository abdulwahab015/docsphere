import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'

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
import { useDeleteAccount } from '@/features/account/hooks'
import { deleteAccountSchema } from '@/features/account/schemas'
import { useSignedInMember } from '@/features/auth/hooks'
import { applyApiErrors } from '@/lib/form-errors'

const EMPTY_VALUES = { current_password: '' }

/** Deleting your own account, confirmed with your password in a dialog. The
 * API refuses the organization's only admin and the only Owner of anything,
 * and the dialog shows why. */
export function DeleteAccountCard() {
  const user = useSignedInMember()
  const [open, setOpen] = useState(false)
  const deleteAccount = useDeleteAccount()
  const form = useForm({ resolver: zodResolver(deleteAccountSchema), defaultValues: EMPTY_VALUES })
  const { errors } = form.formState

  const changeOpen = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      form.reset(EMPTY_VALUES)
    }
  }

  const onSubmit = form.handleSubmit((values) =>
    deleteAccount.mutate(values, {
      onSuccess: () => toast.success('Your account has been deleted.'),
      onError: (error) => applyApiErrors(error, form),
    }),
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Delete account</h2>
        </CardTitle>
        <CardDescription>
          You'll be signed out and won't be able to sign in again. What you wrote stays, shown as by
          a deleted user; your name and email address are removed.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Dialog open={open} onOpenChange={changeOpen}>
          <DialogTrigger asChild>
            <Button variant="destructive">Delete my account</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete your account?</DialogTitle>
              <DialogDescription>
                This can't be undone. Enter your password to confirm.
              </DialogDescription>
            </DialogHeader>
            <form
              onSubmit={onSubmit}
              noValidate
              aria-label="Delete your account"
              className="flex flex-col gap-4"
            >
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
                isPending={deleteAccount.isPending}
                variant="destructive"
                className="self-start"
              >
                Delete my account
              </SubmitButton>
            </form>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  )
}
