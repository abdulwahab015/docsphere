import { ZodError } from 'zod'

import { readRuntimeConfig } from '@/lib/runtime-config'

/** A page whose <head> holds the given meta tags, as nginx serves index.html. */
function pageWith(metaTags: Record<string, string>) {
  const page = document.implementation.createHTMLDocument()
  for (const [name, content] of Object.entries(metaTags)) {
    const meta = page.createElement('meta')
    meta.name = name
    meta.content = content
    page.head.append(meta)
  }
  return page
}

describe('readRuntimeConfig', () => {
  it('reads the settings the server filled in', () => {
    const page = pageWith({
      'sentry-dsn': 'https://public@errors.example.com/1',
      'sentry-environment': 'staging',
    })

    expect(readRuntimeConfig(page)).toEqual({
      sentryDsn: 'https://public@errors.example.com/1',
      sentryEnvironment: 'staging',
    })
  })

  it('leaves error reporting off when nothing filled them in', () => {
    const blank = { sentryDsn: '', sentryEnvironment: '' }

    expect(readRuntimeConfig(pageWith({ 'sentry-dsn': '', 'sentry-environment': '' }))).toEqual(
      blank,
    )
    expect(readRuntimeConfig(pageWith({}))).toEqual(blank)
  })

  it('refuses a malformed DSN, so a misconfigured server fails at startup', () => {
    expect(() => readRuntimeConfig(pageWith({ 'sentry-dsn': 'not a dsn' }))).toThrow(ZodError)
  })
})
