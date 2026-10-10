import { FileUpIcon } from 'lucide-react'
import { type FormEvent, useId, useState } from 'react'

import { parseApiError } from '@/api/errors'
import type { InvitationBulkResult } from '@/api/types'
import { FormAlert } from '@/components/form/FormAlert'
import { SubmitButton } from '@/components/form/SubmitButton'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useBulkInvite } from '@/features/team/hooks'

// Mirrors the backend's users/constants.py::MAX_BULK_INVITE_ROWS.
const MAX_BULK_INVITE_ROWS = 500
const XLSX_TYPES = '.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/** Invites everyone listed in an uploaded spreadsheet, then reports who was
 * invited and which rows were skipped, and why. */
export function BulkInviteDialog() {
  const fileId = useId()
  const [open, setOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const bulkInvite = useBulkInvite()

  const startOver = () => {
    setFile(null)
    bulkInvite.reset()
  }

  const onOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      startOver()
    }
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (file) {
      bulkInvite.mutate(file)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <FileUpIcon aria-hidden />
          Upload a list
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Invite from a spreadsheet</DialogTitle>
          <DialogDescription>
            An .xlsx file with one email address per row in the first column (a header row is fine),
            up to {MAX_BULK_INVITE_ROWS} rows. Everyone listed gets an invitation email.
          </DialogDescription>
        </DialogHeader>
        {bulkInvite.data ? (
          <>
            <BulkInviteSummary result={bulkInvite.data} />
            <DialogFooter>
              <Button variant="outline" onClick={startOver}>
                Upload another
              </Button>
              <Button onClick={() => onOpenChange(false)}>Done</Button>
            </DialogFooter>
          </>
        ) : (
          <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
            <FormAlert
              message={bulkInvite.isError ? parseApiError(bulkInvite.error).formMessage : undefined}
            />
            <Field>
              <FieldLabel htmlFor={fileId}>Spreadsheet</FieldLabel>
              <Input
                id={fileId}
                type="file"
                accept={XLSX_TYPES}
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </Field>
            <DialogFooter>
              <SubmitButton isPending={bulkInvite.isPending} disabled={!file}>
                Send invitations
              </SubmitButton>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}

function BulkInviteSummary({ result }: { result: InvitationBulkResult }) {
  const { created, skipped } = result
  return (
    <div className="flex flex-col gap-3 text-sm">
      <output className="block font-medium">
        {created === 1 ? 'Sent 1 invitation.' : `Sent ${created} invitations.`}
      </output>
      {skipped.length > 0 && (
        <>
          <p>
            {skipped.length === 1 ? '1 row was skipped:' : `${skipped.length} rows were skipped:`}
          </p>
          <div className="rounded-lg border">
            <Table aria-label="Skipped rows">
              <TableHeader>
                <TableRow>
                  <TableHead>Row</TableHead>
                  <TableHead>Reason</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {skipped.map((row, index) => (
                  // A file can repeat the same address, so the email alone isn't a key.
                  <TableRow key={`${index}-${row.email}`}>
                    <TableCell className="break-all">{row.email}</TableCell>
                    <TableCell className="text-muted-foreground first-letter:uppercase">
                      {row.reason}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </div>
  )
}
