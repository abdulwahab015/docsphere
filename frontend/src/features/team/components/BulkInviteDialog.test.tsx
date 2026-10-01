import { screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'

import type { InvitationBulkResult } from '@/api/types'
import { buildCurrentUser } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const BULK_PATH = '/users/invitations/bulk/'
const admin = buildCurrentUser({ org_role: 'ADMIN' })
const SPREADSHEET = new File(['spreadsheet bytes'], 'team.xlsx', {
  type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
})

function serveBulkInvite(result: InvitationBulkResult) {
  const upload = spyResolver(() => HttpResponse.json(result, { status: 201 }))
  server.use(http.post(apiUrl(BULK_PATH), upload))
  return upload
}

async function uploadSpreadsheet(user: UserEvent) {
  await user.click(await screen.findByRole('button', { name: 'Upload a list' }))
  const dialog = within(await screen.findByRole('dialog', { name: 'Invite from a spreadsheet' }))
  const send = dialog.getByRole('button', { name: 'Send invitations' })
  expect(send).toBeDisabled()
  await user.upload(dialog.getByLabelText('Spreadsheet'), SPREADSHEET)
  await user.click(send)
  return dialog
}

describe('BulkInviteDialog', () => {
  beforeEach(() => {
    server.use(http.get(apiUrl('/users/'), () => HttpResponse.json({ count: 0, results: [] })))
  })

  it('uploads the spreadsheet, then lists the rows that were skipped and why', async () => {
    const upload = serveBulkInvite({
      created: 2,
      skipped: [
        { email: 'not-an-email', reason: 'invalid email' },
        { email: 'grace@example.com', reason: 'user already exists' },
      ],
    })
    const { user } = renderRoute('/people', { signedInAs: admin })

    const dialog = await uploadSpreadsheet(user)

    expect(await dialog.findByText('Sent 2 invitations.')).toBeInTheDocument()
    expect(dialog.getByText('2 rows were skipped:')).toBeInTheDocument()
    const skipped = within(dialog.getByRole('table', { name: 'Skipped rows' }))
    expect(skipped.getByRole('row', { name: /not-an-email invalid email/ })).toBeInTheDocument()
    expect(
      skipped.getByRole('row', { name: /grace@example.com user already exists/ }),
    ).toBeInTheDocument()
    // jsdom's XHR drops the file name on the way out; a browser keeps it (see e2e).
    const sent = (await upload.mock.calls[0][0].request.formData()).get('file')
    expect(sent).toMatchObject({ size: SPREADSHEET.size, type: SPREADSHEET.type })
  })

  it('reports a single invitation without a skipped list, and starts over on request', async () => {
    serveBulkInvite({ created: 1, skipped: [] })
    const { user } = renderRoute('/people', { signedInAs: admin })

    const dialog = await uploadSpreadsheet(user)
    expect(await dialog.findByText('Sent 1 invitation.')).toBeInTheDocument()
    expect(dialog.queryByRole('table')).not.toBeInTheDocument()
    await user.click(dialog.getByRole('button', { name: 'Upload another' }))

    expect(dialog.getByRole('button', { name: 'Send invitations' })).toBeDisabled()
  })

  it('names the one skipped row in the singular, and closes when done', async () => {
    serveBulkInvite({
      created: 0,
      skipped: [{ email: 'dup@example.com', reason: 'duplicate in file' }],
    })
    const { user } = renderRoute('/people', { signedInAs: admin })

    const dialog = await uploadSpreadsheet(user)
    expect(await dialog.findByText('1 row was skipped:')).toBeInTheDocument()
    await user.click(dialog.getByRole('button', { name: 'Done' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it("shows the API's reason when the file is refused", async () => {
    server.use(
      http.post(apiUrl(BULK_PATH), () =>
        HttpResponse.json({ detail: 'file must be a valid .xlsx workbook.' }, { status: 400 }),
      ),
    )
    const { user } = renderRoute('/people', { signedInAs: admin })

    const dialog = await uploadSpreadsheet(user)

    expect(await dialog.findByText('file must be a valid .xlsx workbook.')).toBeInTheDocument()
  })
})
