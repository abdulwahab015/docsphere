import { cleanup, screen } from '@testing-library/react'

import { errorTracking } from '@/lib/error-tracking'
import { buildCurrentUser } from '@/test/factories'
import { renderRoute } from '@/test/render'

describe('ErrorTrackingIdentity', () => {
  it('marks error reports with the signed-in user, and with nobody once they leave', async () => {
    const identify = vi.spyOn(errorTracking, 'identify').mockImplementation(() => {})
    const user = buildCurrentUser()
    renderRoute('/settings/account', { signedInAs: user })

    expect(await screen.findByRole('heading', { level: 1, name: 'Account' })).toBeInTheDocument()
    expect(identify).toHaveBeenLastCalledWith(user)

    cleanup()
    expect(identify).toHaveBeenLastCalledWith(undefined)
    identify.mockRestore()
  })
})
