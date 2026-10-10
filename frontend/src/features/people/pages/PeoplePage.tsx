import { PageHeader } from '@/components/PageHeader'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useSignedInMember } from '@/features/auth/hooks'
import { MemberList } from '@/features/people/components/MemberList'
import { BulkInviteDialog } from '@/features/team/components/BulkInviteDialog'
import { DeactivatedMemberList } from '@/features/team/components/DeactivatedMemberList'
import { InvitationList } from '@/features/team/components/InvitationList'
import { InviteDialog } from '@/features/team/components/InviteDialog'
import { useTabParam } from '@/hooks/use-tab-param'

const ADMIN_TABS = ['members', 'invitations', 'deactivated'] as const

/** Everyone in the organization. Admins also manage the team here: roles,
 * invitations, and deactivated people, each on its own tab (`?tab=`). */
export function PeoplePage() {
  const user = useSignedInMember()
  const isAdmin = user.org_role === 'ADMIN'

  return (
    <>
      <PageHeader
        title="People"
        description={`Everyone in ${user.organization.name}. Share projects and documents with them.`}
        actions={
          isAdmin && (
            <>
              <BulkInviteDialog />
              <InviteDialog />
            </>
          )
        }
      />
      {isAdmin ? <TeamTabs /> : <MemberList />}
    </>
  )
}

function TeamTabs() {
  const [tab, setTab] = useTabParam(ADMIN_TABS)

  return (
    <Tabs value={tab} onValueChange={setTab}>
      <TabsList>
        <TabsTrigger value="members">Members</TabsTrigger>
        <TabsTrigger value="invitations">Invitations</TabsTrigger>
        <TabsTrigger value="deactivated">Deactivated</TabsTrigger>
      </TabsList>
      <TabsContent value="members" className="flex flex-col gap-4">
        <MemberList />
      </TabsContent>
      <TabsContent value="invitations" className="flex flex-col gap-4">
        <InvitationList />
      </TabsContent>
      <TabsContent value="deactivated" className="flex flex-col gap-4">
        <DeactivatedMemberList />
      </TabsContent>
    </Tabs>
  )
}
