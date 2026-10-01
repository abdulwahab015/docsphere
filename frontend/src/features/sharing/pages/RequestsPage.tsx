import { useSearchParams } from 'react-router'

import { PageHeader } from '@/components/PageHeader'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { IncomingRequests } from '@/features/sharing/components/IncomingRequests'
import { SentRequests } from '@/features/sharing/components/SentRequests'
import { useListParams } from '@/hooks/use-list-params'

const TAB_PARAM = 'tab'
const SENT_TAB = 'sent'
const INCOMING_TAB = 'incoming'

/** Requests for Editor access: ones waiting for the signed-in user to answer,
 * and ones they sent. The open tab is kept in the URL (`?tab=sent`). */
export function RequestsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { page, setPage } = useListParams()
  const tab = searchParams.get(TAB_PARAM) === SENT_TAB ? SENT_TAB : INCOMING_TAB

  // Each tab starts on its own first page.
  const changeTab = (nextTab: string) =>
    setSearchParams(nextTab === SENT_TAB ? { [TAB_PARAM]: SENT_TAB } : {})

  return (
    <>
      <PageHeader
        title="Access requests"
        description="Requests to edit documents: ones for you to answer, and ones you've sent."
      />
      <Tabs value={tab} onValueChange={changeTab}>
        <TabsList>
          <TabsTrigger value={INCOMING_TAB}>Incoming</TabsTrigger>
          <TabsTrigger value={SENT_TAB}>Sent</TabsTrigger>
        </TabsList>
        <TabsContent value={INCOMING_TAB} className="flex flex-col gap-4">
          <IncomingRequests page={page} onPageChange={setPage} />
        </TabsContent>
        <TabsContent value={SENT_TAB} className="flex flex-col gap-4">
          <SentRequests page={page} onPageChange={setPage} />
        </TabsContent>
      </Tabs>
    </>
  )
}
