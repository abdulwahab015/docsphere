describe('session broadcast without BroadcastChannel support', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.stubGlobal('BroadcastChannel', undefined)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('announces and subscribes as harmless no-ops', async () => {
    const { announceSessionChange, onSessionChangeElsewhere } =
      await import('@/features/auth/session-broadcast')
    const listener = vi.fn<() => void>()

    const unsubscribe = onSessionChangeElsewhere(listener)
    announceSessionChange()
    unsubscribe()

    expect(listener).not.toHaveBeenCalled()
  })
})
