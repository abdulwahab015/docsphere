import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Toaster } from 'sonner'

import { RecoveryCodesList } from '@/features/two-factor/components/RecoveryCodesList'
import { fileSaver } from '@/lib/save-file'

const CODES = ['abcde-fghjk', 'mnpqr-stuvw']

function renderList() {
  const user = userEvent.setup()
  render(
    <>
      <RecoveryCodesList codes={CODES} />
      <Toaster />
    </>,
  )
  return user
}

describe('RecoveryCodesList', () => {
  it('lists the codes', () => {
    renderList()

    expect(screen.getByRole('list', { name: 'Recovery codes' })).toHaveTextContent(
      'abcde-fghjkmnpqr-stuvw',
    )
  })

  it('copies them, one per line', async () => {
    const user = renderList()

    await user.click(screen.getByRole('button', { name: 'Copy' }))

    expect(await screen.findByText('Recovery codes copied.')).toBeInTheDocument()
    expect(await navigator.clipboard.readText()).toBe('abcde-fghjk\nmnpqr-stuvw')
  })

  it('says so when they could not be copied', async () => {
    const user = renderList()
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValueOnce(new Error('denied'))

    await user.click(screen.getByRole('button', { name: 'Copy' }))

    expect(
      await screen.findByText("Couldn't copy them. Download them instead."),
    ).toBeInTheDocument()
  })

  it('downloads them as a text file', async () => {
    const save = vi.spyOn(fileSaver, 'save').mockImplementation(() => {})
    const user = renderList()

    await user.click(screen.getByRole('button', { name: 'Download' }))

    expect(save).toHaveBeenCalledOnce()
    const [file, name] = save.mock.calls[0]
    expect(name).toBe('docsphere-recovery-codes.txt')
    expect(await file.text()).toBe('abcde-fghjk\nmnpqr-stuvw\n')
  })
})
