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
import { TwoFactorSetup } from '@/features/two-factor/components/TwoFactorSetup'
import { useRereadTwoFactor } from '@/features/two-factor/hooks'

/** Setting up two-factor sign-in from the account page. Once the dialog has
 * closed - done or not - whether it's on is re-read, and the card shows it. */
export function TurnOnTwoFactorDialog() {
  const [open, setOpen] = useState(false)
  const rereadTwoFactor = useRereadTwoFactor()

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Turn on two-factor sign-in</Button>
      </DialogTrigger>
      <DialogContent onCloseAutoFocus={rereadTwoFactor}>
        <DialogHeader>
          <DialogTitle>Turn on two-factor sign-in</DialogTitle>
          <DialogDescription>
            A code from an authenticator app each time you log in, as well as your password.
          </DialogDescription>
        </DialogHeader>
        <TwoFactorSetup onDone={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  )
}
