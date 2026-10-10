import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { CurrentPasswordForm } from '@/features/two-factor/components/CurrentPasswordForm'
import { useRereadTwoFactor, useTurnOffTwoFactor } from '@/features/two-factor/hooks'

/** Turning two-factor sign-in off, confirmed with the password. `disabled`
 * while the organization requires it (the API refuses anyway). Once it's off
 * and the dialog has closed, whether it's on is re-read, and the card shows
 * it. */
export function TurnOffTwoFactorDialog({ disabled }: { disabled: boolean }) {
  const [open, setOpen] = useState(false)
  const turnOff = useTurnOffTwoFactor()
  const rereadTwoFactor = useRereadTwoFactor()

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" disabled={disabled}>
          Turn off
        </Button>
      </DialogTrigger>
      <DialogContent
        onCloseAutoFocus={() => {
          if (turnOff.isSuccess) {
            rereadTwoFactor()
          }
        }}
      >
        <DialogHeader>
          <DialogTitle>Turn off two-factor sign-in?</DialogTitle>
          <DialogDescription>
            You&apos;ll log in with your password alone, and your recovery codes will stop working.
            Enter your password to confirm.
          </DialogDescription>
        </DialogHeader>
        <CurrentPasswordForm
          label="Turn off two-factor sign-in"
          submitLabel="Turn off"
          destructive
          isPending={turnOff.isPending}
          onSubmit={(values, reportError) =>
            turnOff.mutate(values, {
              onSuccess: () => {
                toast.success('Two-factor sign-in is off.')
                setOpen(false)
              },
              onError: reportError,
            })
          }
        />
      </DialogContent>
    </Dialog>
  )
}
