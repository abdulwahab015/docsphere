import { toast } from 'sonner'

import { actionErrorMessage } from '@/api/errors'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { useMyLatestAccessRequest, useRequestEditAccess } from '@/features/sharing/hooks'
import { formatDate } from '@/lib/format'

/** Lets a Viewer ask the document's owners for Editor access, and shows
 * where their latest request stands. */
export function RequestEditAccessCard({ documentId }: { documentId: number }) {
  const latestRequest = useMyLatestAccessRequest(documentId)
  const requestAccess = useRequestEditAccess(documentId)

  const sendRequest = () =>
    requestAccess.mutate(undefined, {
      onSuccess: () => toast.success("Request sent. You'll get an email when an owner answers."),
      onError: (error) => toast.error(actionErrorMessage(error, "Couldn't send your request.")),
    })

  const request = latestRequest.data
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Editing</h2>
        </CardTitle>
        <CardDescription>
          You can view this document. To edit it, ask its owners for Editor access.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col items-start gap-3 text-sm">
        {latestRequest.isPending ? (
          <Skeleton className="h-8 w-40" aria-label="Loading your request" />
        ) : request?.status === 'PENDING' ? (
          <p>You asked on {formatDate(request.created)}. Waiting for an owner to answer.</p>
        ) : (
          <>
            {request?.status === 'DENIED' && (
              <p className="text-muted-foreground">
                Your last request was denied on {formatDate(request.modified)}.
              </p>
            )}
            <Button disabled={requestAccess.isPending} onClick={sendRequest}>
              {requestAccess.isPending && <Spinner aria-hidden />}
              Request edit access
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  )
}
