import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DeleteAccountDialog } from '@/features/account/components/DeleteAccountDialog'

export function DeleteAccountCard() {
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
        <DeleteAccountDialog />
      </CardContent>
    </Card>
  )
}
