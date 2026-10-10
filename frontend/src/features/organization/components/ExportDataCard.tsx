import { DownloadIcon } from 'lucide-react'
import { toast } from 'sonner'

import { HTTP_STATUS } from '@/api/constants'
import { actionErrorMessage, getErrorStatus } from '@/api/errors'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useRequestExport } from '@/features/organization/hooks'

const DAILY_LIMIT_MESSAGE =
  'Your organization has asked for as many exports as it can today. Try again tomorrow.'

/** Asking for a copy of the organization's data, built in the background
 * and emailed to the admin as a link. One is built at a time (the API says
 * so if one is on its way), and only a few a day. */
export function ExportDataCard() {
  const requestExport = useRequestExport()

  const startExport = () =>
    requestExport.mutate(undefined, {
      onSuccess: () =>
        toast.success("We're preparing your export. We'll email you a link when it's ready."),
      onError: (error) =>
        toast.error(
          getErrorStatus(error) === HTTP_STATUS.tooManyRequests
            ? DAILY_LIMIT_MESSAGE
            : actionErrorMessage(error, "Couldn't start the export. Try again."),
        ),
    })

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Export data</h2>
        </CardTitle>
        <CardDescription>
          A .zip of the members and of the projects and documents you can open, with their text,
          sharing and attached files. Private ones you can&apos;t open are counted but not included.
          The emailed link works for 7 days.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button variant="outline" disabled={requestExport.isPending} onClick={startExport}>
          <DownloadIcon aria-hidden />
          Email me an export
        </Button>
      </CardContent>
    </Card>
  )
}
