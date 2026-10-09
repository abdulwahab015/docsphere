import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { fileSaver } from '@/lib/save-file'
import { buildCurrentUser } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, server, spyResolver } from '@/test/server'

const DOWNLOAD_PATH = '/organizations/exports/download/'
const admin = buildCurrentUser({ org_role: 'ADMIN' })

describe('ExportDownloadPage', () => {
  it('downloads the export the link names', async () => {
    const save = vi.spyOn(fileSaver, 'save').mockImplementation(() => {})
    const download = spyResolver(
      () => new HttpResponse(new Uint8Array([0x50, 0x4b]), { status: 200 }),
    )
    server.use(http.get(apiUrl(DOWNLOAD_PATH), download))
    const { user } = renderRoute('/settings/organization/export?token=abc', { signedInAs: admin })

    await user.click(screen.getByRole('button', { name: 'Download export' }))

    await vi.waitFor(() => expect(save).toHaveBeenCalledTimes(1))
    const [file, name] = save.mock.calls[0]
    expect(name).toBe('docsphere-export.zip')
    expect(file.size).toBe(2)
    expect(new URL(download.mock.calls[0][0].request.url).searchParams.get('token')).toBe('abc')
  })

  it("shows why an expired link didn't work", async () => {
    server.use(
      http.get(apiUrl(DOWNLOAD_PATH), () =>
        HttpResponse.json(
          { detail: 'This download link is invalid or has expired.' },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute('/settings/organization/export?token=old', { signedInAs: admin })

    await user.click(screen.getByRole('button', { name: 'Download export' }))

    expect(
      await screen.findByText('This download link is invalid or has expired.'),
    ).toBeInTheDocument()
  })

  it('falls back to a general message when the error has no reason', async () => {
    server.use(
      http.get(apiUrl(DOWNLOAD_PATH), () => new HttpResponse('Bad gateway', { status: 502 })),
    )
    const { user } = renderRoute('/settings/organization/export?token=abc', { signedInAs: admin })

    await user.click(screen.getByRole('button', { name: 'Download export' }))

    expect(await screen.findByText("Couldn't download the export. Try again.")).toBeInTheDocument()
  })

  it('says when the link has no token', () => {
    renderRoute('/settings/organization/export', { signedInAs: admin })

    expect(screen.getByRole('heading', { name: 'This link is incomplete' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Download export' })).not.toBeInTheDocument()
  })
})
