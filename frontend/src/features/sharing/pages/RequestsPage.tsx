import { PageHeader } from '@/components/PageHeader'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { IncomingRequests } from '@/features/sharing/components/IncomingRequests'
import { SentRequests } from '@/features/sharing/components/SentRequests'
import { useListParams } from '@/hooks/use-list-params'
import { useTabParam } from '@/hooks/use-tab-param'

const TABS = ['incoming', 'sent'] as const

/** Requests for Editor access: ones waiting for the signed-in user to answer,
 * and ones they sent. The open tab is kept in the URL (`?tab=sent`). */
export function RequestsPage() {
  const [tab, setTab] = useTabParam(TABS)
  const { page, setPage } = useListParams()

  return (
    <>
      <PageHeader
        title="Access requests"
        description="Requests to edit documents: ones for you to answer, and ones you've sent."
      />
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="incoming">Incoming</TabsTrigger>
          <TabsTrigger value="sent">Sent</TabsTrigger>
        </TabsList>
        <TabsContent value="incoming" className="flex flex-col gap-4">
          <IncomingRequests page={page} onPageChange={setPage} />
        </TabsContent>
        <TabsContent value="sent" className="flex flex-col gap-4">
          <SentRequests page={page} onPageChange={setPage} />
        </TabsContent>
      </Tabs>
    </>
  )
}
