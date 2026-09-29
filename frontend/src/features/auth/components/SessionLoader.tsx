import type { ReactNode } from 'react'

import type { CurrentUser } from '@/api/types'
import { FullPageSpinner } from '@/components/FullPageSpinner'
import { Button } from '@/components/ui/button'
import { AuthCard } from '@/features/auth/components/AuthCard'
import { useCurrentUser } from '@/features/auth/hooks'

interface SessionLoaderProps {
  children: (user: CurrentUser | null) => ReactNode
}

/** Waits for the session to resolve, then renders `children` with the
 * signed-in user, or `null` when nobody is signed in. */
export function SessionLoader({ children }: SessionLoaderProps) {
  const session = useCurrentUser()

  // `null` is a resolved answer (signed out); only `undefined` means there is
  // no answer yet. A failed background refetch keeps the last good answer.
  if (session.data === undefined) {
    if (session.isError) {
      return (
        <AuthCard
          title="Can't load DocSphere"
          description="We couldn't reach the server. Check your connection and try again."
        >
          <Button className="w-full" onClick={() => void session.refetch()}>
            Try again
          </Button>
        </AuthCard>
      )
    }
    return <FullPageSpinner />
  }

  return children(session.data)
}
