import { useEffect } from 'react'
import { useBlocker } from 'react-router'

import { ConfirmDialog } from '@/components/ConfirmDialog'

/** While `when` is true, asks before leaving the page: in-app navigation gets
 * a confirm dialog, and closing or reloading the tab gets the browser's own
 * prompt. */
export function UnsavedChangesGuard({ when }: { when: boolean }) {
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      when && currentLocation.pathname !== nextLocation.pathname,
  )

  useEffect(() => {
    if (!when) {
      return undefined
    }
    const warnBeforeUnload = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warnBeforeUnload)
    return () => window.removeEventListener('beforeunload', warnBeforeUnload)
  }, [when])

  return (
    <ConfirmDialog
      open={blocker.state === 'blocked'}
      onOpenChange={(open) => {
        if (!open) {
          blocker.reset?.()
        }
      }}
      title="Discard unsaved changes?"
      description="You've made changes that haven't been saved. Leaving this page discards them."
      confirmLabel="Discard changes"
      onConfirm={() => blocker.proceed?.()}
      isPending={false}
      destructive
    />
  )
}
