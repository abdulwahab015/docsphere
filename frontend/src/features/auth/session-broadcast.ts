const CHANNEL_NAME = 'docsphere-session'
const SESSION_CHANGED = 'session-changed'

// One instance both sends and listens: a BroadcastChannel never delivers a
// message back to the instance that posted it, so a tab doesn't react to its
// own announcements.
const channel = typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel(CHANNEL_NAME)

/** Tells this app's other open tabs that the user deliberately signed in or
 * out here, so they stop acting on a session that is no longer current. */
export function announceSessionChange() {
  channel?.postMessage(SESSION_CHANGED)
}

/** Calls `listener` when another tab announces a session change; returns the
 * unsubscribe function. */
export function onSessionChangeElsewhere(listener: () => void) {
  if (!channel) {
    return () => {}
  }
  const handleMessage = (event: MessageEvent) => {
    if (event.data === SESSION_CHANGED) {
      listener()
    }
  }
  channel.addEventListener('message', handleMessage)
  return () => channel.removeEventListener('message', handleMessage)
}
