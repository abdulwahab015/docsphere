import type { ComponentProps } from 'react'
import { toast } from 'sonner'

import { actionErrorMessage } from '@/api/errors'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { useOpenBillingPortal } from '@/features/billing/hooks'

/** Opens Stripe's billing portal, where the admin updates payment details,
 * downloads invoices or cancels. */
export function ManageBillingButton({
  children = 'Manage billing',
  ...buttonProps
}: ComponentProps<typeof Button>) {
  const portal = useOpenBillingPortal()
  // Still busy after success: the browser is on its way to Stripe.
  const isLeaving = portal.isPending || portal.isSuccess

  return (
    <Button
      variant="outline"
      {...buttonProps}
      disabled={isLeaving}
      onClick={() =>
        portal.mutate(undefined, {
          // e.g. an organization that has never subscribed has no billing account yet.
          onError: (error) =>
            toast.error(actionErrorMessage(error, "Couldn't open the billing portal.")),
        })
      }
    >
      {isLeaving && <Spinner aria-hidden />}
      {children}
    </Button>
  )
}
