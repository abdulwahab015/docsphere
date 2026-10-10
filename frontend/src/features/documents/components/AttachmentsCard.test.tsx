import { fireEvent, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { Attachment, Document } from '@/api/types'
import { MAX_ATTACHMENT_BYTES } from '@/features/documents/attachments'
import { fileSaver } from '@/lib/save-file'
import { buildAttachment, buildCurrentUser, buildDocument } from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, heldResponse, server, spyResolver } from '@/test/server'

const DOCUMENT_URL = '/documents/11'
const ATTACHMENTS_PATH = '/documents/11/attachments/'
const signedInAs = buildCurrentUser()
const REPORT = buildAttachment()
const PDF = new File(['%PDF-1.7'], 'minutes.pdf', { type: 'application/pdf' })

function serveDocument(document: Document) {
  server.use(http.get(apiUrl('/documents/11/'), () => HttpResponse.json(document)))
}

function serveAttachments(attachments: Attachment[]) {
  server.use(
    http.get(apiUrl(ATTACHMENTS_PATH), () =>
      HttpResponse.json({ count: attachments.length, results: attachments }),
    ),
  )
}

async function attachmentsCard() {
  const heading = await screen.findByRole('heading', { name: 'Attachments' })
  return within(heading.closest('[data-slot="card"]') as HTMLElement)
}

describe('AttachmentsCard', () => {
  describe('reading (anyone who can open the document)', () => {
    it('lists each file with its size, who attached it and when, but no editing controls for a Viewer', async () => {
      serveDocument(buildDocument({ access_level: 'VIEWER', visibility: 'PUBLIC' }))
      serveAttachments([REPORT])
      renderRoute(DOCUMENT_URL, { signedInAs })
      const card = await attachmentsCard()

      const row = (await card.findByText('Q3 report.pdf')).closest('li')!
      expect(row).toHaveTextContent('2.3 MB · Ada Lovelace ·')
      expect(within(row).getByRole('button', { name: 'Download Q3 report.pdf' })).toBeEnabled()
      expect(card.queryByRole('button', { name: 'Delete Q3 report.pdf' })).not.toBeInTheDocument()
      expect(card.queryByLabelText('Attach a file')).not.toBeInTheDocument()
    })

    it('says when nothing is attached', async () => {
      serveDocument(buildDocument({ access_level: 'VIEWER', visibility: 'PUBLIC' }))
      renderRoute(DOCUMENT_URL, { signedInAs })

      expect(await (await attachmentsCard()).findByText('No files attached.')).toBeInTheDocument()
    })

    it('downloads a file through the API and saves it under its name', async () => {
      serveDocument(buildDocument({ access_level: 'VIEWER', visibility: 'PUBLIC' }))
      serveAttachments([REPORT])
      server.use(
        http.get(
          apiUrl(`${ATTACHMENTS_PATH}31/download/`),
          () =>
            new HttpResponse('%PDF-1.7 report', { headers: { 'Content-Type': 'application/pdf' } }),
        ),
      )
      const save = vi.spyOn(fileSaver, 'save').mockImplementation(() => {})
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const card = await attachmentsCard()

      await user.click(await card.findByRole('button', { name: 'Download Q3 report.pdf' }))

      await vi.waitFor(() => expect(save).toHaveBeenCalledOnce())
      const [file, name] = save.mock.calls[0]
      expect(name).toBe('Q3 report.pdf')
      expect(file.type).toBe('application/pdf')
      expect(await file.text()).toBe('%PDF-1.7 report')
    })

    it('says when a download fails', async () => {
      serveDocument(buildDocument({ access_level: 'VIEWER', visibility: 'PUBLIC' }))
      serveAttachments([REPORT])
      server.use(
        http.get(apiUrl(`${ATTACHMENTS_PATH}31/download/`), () =>
          HttpResponse.json({}, { status: 500 }),
        ),
      )
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const card = await attachmentsCard()

      await user.click(await card.findByRole('button', { name: 'Download Q3 report.pdf' }))

      expect(await screen.findByText("Couldn't download this file. Try again.")).toBeInTheDocument()
    })

    it('offers a retry when the list fails to load', async () => {
      serveDocument(buildDocument({ access_level: 'VIEWER', visibility: 'PUBLIC' }))
      server.use(http.get(apiUrl(ATTACHMENTS_PATH), () => HttpResponse.json({}, { status: 500 })))
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const card = await attachmentsCard()

      const retry = await card.findByRole('button', { name: 'Try again' })
      serveAttachments([REPORT])
      await user.click(retry)

      expect(await card.findByText('Q3 report.pdf')).toBeInTheDocument()
    })
  })

  describe('attaching (Editor and above)', () => {
    it('uploads the picked file, showing its progress, and lists it', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      serveAttachments([])
      const minutes = buildAttachment({ id: 32, name: 'minutes.pdf', size: 8 })
      const upload = heldResponse(() => HttpResponse.json(minutes, { status: 201 }))
      const sent = spyResolver(upload.resolver)
      server.use(http.post(apiUrl(ATTACHMENTS_PATH), sent))
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const card = await attachmentsCard()

      await user.upload(await card.findByLabelText('Attach a file'), PDF)

      expect(await card.findByRole('progressbar', { name: 'Uploading' })).toBeInTheDocument()
      expect(card.getByLabelText('Attach a file')).toBeDisabled()
      serveAttachments([minutes])
      upload.release()
      expect(await screen.findByText('Attached minutes.pdf.')).toBeInTheDocument()
      expect(await card.findByText('minutes.pdf')).toBeInTheDocument()
      expect(card.queryByRole('progressbar')).not.toBeInTheDocument()
      // The test environment's FormData doesn't keep the file's name.
      const file = (await sent.mock.calls[0][0].request.formData()).get('file')
      expect(file).toMatchObject({ size: PDF.size, type: PDF.type })
    })

    it("shows the API's reason for refusing a file under the field", async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      serveAttachments([])
      server.use(
        http.post(apiUrl(ATTACHMENTS_PATH), () =>
          HttpResponse.json(
            { file: ["This file's content doesn't match its .pdf name."] },
            { status: 400 },
          ),
        ),
      )
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const card = await attachmentsCard()

      await user.upload(await card.findByLabelText('Attach a file'), PDF)

      expect(await card.findByLabelText('Attach a file')).toHaveAccessibleDescription(
        expect.stringContaining("This file's content doesn't match its .pdf name."),
      )
    })

    it('says when the organization has run out of space', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      serveAttachments([])
      server.use(
        http.post(apiUrl(ATTACHMENTS_PATH), () =>
          HttpResponse.json(
            { detail: 'Your organization has used its 1 GB for attached files.' },
            { status: 400 },
          ),
        ),
      )
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const card = await attachmentsCard()

      await user.upload(await card.findByLabelText('Attach a file'), PDF)

      expect(
        await card.findByText('Your organization has used its 1 GB for attached files.'),
      ).toBeInTheDocument()
    })

    it('uploads nothing when the file picker is cancelled', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      serveAttachments([])
      const sent = spyResolver(() => HttpResponse.json({}, { status: 201 }))
      server.use(http.post(apiUrl(ATTACHMENTS_PATH), sent))
      renderRoute(DOCUMENT_URL, { signedInAs })
      const card = await attachmentsCard()

      fireEvent.change(await card.findByLabelText('Attach a file'), { target: { files: [] } })

      expect(card.queryByRole('progressbar')).not.toBeInTheDocument()
      expect(sent).not.toHaveBeenCalled()
    })

    it('refuses a file over the size limit without uploading it', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      serveAttachments([])
      const sent = spyResolver(() => HttpResponse.json({}, { status: 201 }))
      server.use(http.post(apiUrl(ATTACHMENTS_PATH), sent))
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const card = await attachmentsCard()
      const tooLarge = new File([new Uint8Array(MAX_ATTACHMENT_BYTES + 1)], 'scan.pdf')

      await user.upload(await card.findByLabelText('Attach a file'), tooLarge)

      expect(await card.findByText('Files can be at most 10 MB.')).toBeInTheDocument()
      expect(sent).not.toHaveBeenCalled()
    })
  })

  describe('deleting (Editor and above)', () => {
    it('deletes a file after confirming', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      serveAttachments([REPORT])
      const remove = spyResolver(() => new HttpResponse(null, { status: 204 }))
      server.use(http.delete(apiUrl(`${ATTACHMENTS_PATH}31/`), remove))
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const card = await attachmentsCard()

      await user.click(await card.findByRole('button', { name: 'Delete Q3 report.pdf' }))
      const confirm = await screen.findByRole('alertdialog', { name: 'Delete Q3 report.pdf?' })
      serveAttachments([])
      await user.click(within(confirm).getByRole('button', { name: 'Delete file' }))

      expect(await screen.findByText('Deleted Q3 report.pdf.')).toBeInTheDocument()
      expect(remove).toHaveBeenCalledOnce()
      expect(await card.findByText('No files attached.')).toBeInTheDocument()
    })

    it('says when a deletion fails', async () => {
      serveDocument(buildDocument({ access_level: 'EDITOR' }))
      serveAttachments([REPORT])
      server.use(
        http.delete(apiUrl(`${ATTACHMENTS_PATH}31/`), () => HttpResponse.json({}, { status: 500 })),
      )
      const { user } = renderRoute(DOCUMENT_URL, { signedInAs })
      const card = await attachmentsCard()

      await user.click(await card.findByRole('button', { name: 'Delete Q3 report.pdf' }))
      await user.click(await screen.findByRole('button', { name: 'Delete file' }))

      expect(await screen.findByText("Couldn't delete this file. Try again.")).toBeInTheDocument()
    })
  })
})
