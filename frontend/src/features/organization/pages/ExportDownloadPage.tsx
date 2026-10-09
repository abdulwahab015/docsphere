import { DownloadIcon, FileArchiveIcon } from 'lucide-react'
import { useSearchParams } from 'react-router'
import { toast } from 'sonner'

import { actionErrorMessage } from '@/api/errors'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { useDownloadExport } from '@/features/organization/hooks'

/** Where the emailed export link lands: the download goes through the API,
 * signed in, with the link's token naming the export. */
export function ExportDownloadPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const download = useDownloadExport()

  const startDownload = (exportToken: string) =>
    download.mutate(exportToken, {
      onError: (error) =>
        toast.error(actionErrorMessage(error, "Couldn't download the export. Try again.")),
    })

  return (
    <>
      <PageHeader
        title="Download export"
        description="Your organization's data, as you asked for it. The link works for 7 days."
      />
      {token ? (
        <Button
          className="self-start"
          disabled={download.isPending}
          onClick={() => startDownload(token)}
        >
          <DownloadIcon aria-hidden />
          Download export
        </Button>
      ) : (
        <EmptyState
          icon={FileArchiveIcon}
          title="This link is incomplete"
          description="Open the link from the email again, or ask for a new export on the Organization page."
        />
      )}
    </>
  )
}
