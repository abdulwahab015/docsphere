import type { ComponentProps } from 'react'

import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'

interface SubmitButtonProps extends ComponentProps<typeof Button> {
  isPending: boolean
}

export function SubmitButton({ isPending, disabled, children, ...buttonProps }: SubmitButtonProps) {
  return (
    <Button type="submit" disabled={isPending || disabled} {...buttonProps}>
      {isPending && <Spinner aria-hidden />}
      {children}
    </Button>
  )
}
