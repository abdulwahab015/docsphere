import type { BrowserOptions, Breadcrumb, ErrorEvent } from '@sentry/react'

import type { CurrentUser } from '@/api/types'

type Sentry = typeof import('@sentry/react')

export interface ErrorTrackingConfig {
  /** Where reports go; nothing is reported without one. */
  dsn: string
  environment?: string
  release?: string
  /** How reports are sent - Sentry's own unless given (tests capture them). */
  transport?: BrowserOptions['transport']
}

/** A URL without its query string, which can hold what was searched for. */
function withoutQuery(url: string) {
  return url.split('?')[0]
}

/** Keeps only what may leave the browser: the page's address without its
 * query, and the user's id - never an email or the content of a document. */
export function scrubEvent(event: ErrorEvent): ErrorEvent {
  if (event.request?.url) {
    event.request = { url: withoutQuery(event.request.url) }
  }
  if (event.user) {
    event.user = event.user.id ? { id: event.user.id } : {}
  }
  return event
}

/** Breadcrumbs are what happened before the error: requests and page changes
 * keep their addresses without queries; console messages aren't kept, since
 * they can repeat anything. */
export function scrubBreadcrumb(breadcrumb: Breadcrumb): Breadcrumb | null {
  if (breadcrumb.category === 'console') {
    return null
  }
  const { data } = breadcrumb
  if (data) {
    for (const key of ['url', 'from', 'to']) {
      if (typeof data[key] === 'string') {
        data[key] = withoutQuery(data[key])
      }
    }
  }
  return breadcrumb
}

// Loaded only when there is somewhere to report to, so the SDK isn't part of
// the app's first download.
let sentry: Promise<Sentry> | undefined

/** Error reporting to a Sentry-compatible service. An object rather than bare
 * functions so tests can spy on it. */
export const errorTracking = {
  start({ dsn, environment, release, transport }: ErrorTrackingConfig) {
    if (!dsn) {
      return
    }
    sentry = import('@sentry/react').then((Sentry) => {
      Sentry.init({
        dsn,
        environment,
        release,
        // Nothing the SDK would collect on its own: reports carry only the
        // ids `identify` sets, and `scrubEvent` keeps the address without its
        // query. (Sentry 11's defaults collect user details, cookies,
        // headers, bodies and query strings.)
        dataCollection: {
          userInfo: false,
          cookies: false,
          httpHeaders: false,
          httpBodies: [],
          urlQueryParams: false,
          stackFrameVariables: false,
        },
        beforeSend: scrubEvent,
        beforeBreadcrumb: scrubBreadcrumb,
        ...(transport && { transport }),
      })
      return Sentry
    })
  },

  /** Reports an error the app caught itself (errors nothing catches are
   * reported by the SDK on its own). */
  report(error: unknown) {
    void sentry?.then((Sentry) => Sentry.captureException(error))
  },

  /** Marks later reports with who is signed in - their user and organization
   * ids, nothing else - or with nobody. */
  identify(user: CurrentUser | undefined) {
    void sentry?.then((Sentry) => {
      Sentry.setUser(user ? { id: String(user.id) } : null)
      Sentry.setTag('organization_id', user?.organization ? String(user.organization.id) : '')
    })
  },
}
