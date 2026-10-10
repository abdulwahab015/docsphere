import { CircleAlertIcon } from 'lucide-react'

import { Alert, AlertDescription } from '@/components/ui/alert'

export function FormAlert({ message }: { message: string | undefined }) {
  if (!message) {
    return null
  }

  return (
    <Alert variant="destructive">
      <CircleAlertIcon />
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}
