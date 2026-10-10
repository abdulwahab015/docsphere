import { externalRedirect } from '@/lib/external-redirect'

describe('externalRedirect', () => {
  it('sends the browser to the address', () => {
    // jsdom can't load another page, but it does follow a same-page #fragment.
    const address = `${window.location.href.split('#')[0]}#stripe`

    externalRedirect.to(address)

    expect(window.location.href).toBe(address)
  })
})
