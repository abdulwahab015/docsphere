import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useSignedInMember } from '@/features/auth/hooks'
import { ORG_ROLE_LABELS } from '@/lib/access'

export function ProfileCard() {
  const user = useSignedInMember()

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Profile</h2>
        </CardTitle>
        <CardDescription>
          You sign in with this email address. Roles are given by your organization's admins.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
          <dt className="text-muted-foreground">Email</dt>
          <dd className="break-all">{user.email}</dd>
          <dt className="text-muted-foreground">Role</dt>
          <dd>{ORG_ROLE_LABELS[user.org_role]}</dd>
          <dt className="text-muted-foreground">Organization</dt>
          <dd>{user.organization.name}</dd>
        </dl>
      </CardContent>
    </Card>
  )
}
