import { useState } from 'react'

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
import { RecoveryCodesList } from '@/features/two-factor/components/RecoveryCodesList'
import { useMakeNewRecoveryCodes } from '@/features/two-factor/hooks'

/** A new set of recovery codes, confirmed with the password and shown once;
 * the old set stops working. */
export function NewRecoveryCodesDialog() {
  const [open, setOpen] = useState(false)
  const makeCodes = useMakeNewRecoveryCodes()

  const changeOpen = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      // Opening it again asks for the password again.
      makeCodes.reset()
    }
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">New recovery codes</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New recovery codes</DialogTitle>
          <DialogDescription>
            {makeCodes.data
              ? "Save these somewhere safe: they won't be shown again. Your old codes no longer work."
              : 'Your old recovery codes will stop working. Enter your password to make new ones.'}
          </DialogDescription>
        </DialogHeader>
        {makeCodes.data ? (
          <div className="flex flex-col gap-4">
            <RecoveryCodesList codes={makeCodes.data.recovery_codes} />
            <Button className="self-start" onClick={() => changeOpen(false)}>
              I&apos;ve saved them
            </Button>
          </div>
        ) : (
          <CurrentPasswordForm
            label="Make new recovery codes"
            submitLabel="Make new codes"
            isPending={makeCodes.isPending}
            onSubmit={(values, reportError) => makeCodes.mutate(values, { onError: reportError })}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
