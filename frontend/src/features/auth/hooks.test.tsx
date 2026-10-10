import { renderHook } from '@testing-library/react'

import { useSignedInMember, useSignedInUser } from '@/features/auth/hooks'

// Each hook only has a value inside the guard that provides it; using one
// anywhere else is a programming error and should fail loudly, not render
// with a missing user.
describe('session hooks outside their guards', () => {
  beforeEach(() => {
    // React logs the error a render throws; keep the test output clean.
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('useSignedInUser requires RequireAuth', () => {
    expect(() => renderHook(() => useSignedInUser())).toThrow(
      'useSignedInUser must be used inside RequireAuth.',
    )
  })

  it('useSignedInMember requires RequireActiveSubscription', () => {
    expect(() => renderHook(() => useSignedInMember())).toThrow(
      'useSignedInMember must be used inside RequireActiveSubscription.',
    )
  })
})
