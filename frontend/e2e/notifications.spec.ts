import { expect, type Page, test } from '@playwright/test'

import { logIn, logInElsewhere, NOTIFY_MEMBER, NOTIFY_OWNER, openDocument } from './fixtures'

/** The poll interval, and a little more. */
const NEXT_POLL = '00:31'

function bell(page: Page, unread?: number) {
  const name = unread ? `Notifications, ${unread} unread` : 'Notifications'
  return page.getByRole('button', { name, exact: true })
}

test.describe('notifications', () => {
  test("a request lights up the Owner's bell, and the answer the requester's", async ({
    page,
    browser,
  }) => {
    // The Owner's tab keeps polling while they wait.
    await page.clock.install()
    await logIn(page, NOTIFY_OWNER)
    await expect(bell(page)).toBeVisible()

    const member = await logInElsewhere(browser, NOTIFY_MEMBER)
    await openDocument(member, 'Bulletin')
    await member.getByRole('button', { name: 'Request edit access' }).click()
    await expect(member.getByText(/^Request sent/)).toBeVisible()

    await page.clock.fastForward(NEXT_POLL)
    await bell(page, 1).click()
    await page
      .getByRole('menuitem', { name: 'Unread: Max Member asked to edit "Bulletin"' })
      .click()
    await expect(page).toHaveURL(/\/requests$/)
    await expect(bell(page)).toBeVisible()

    const request = page.getByRole('row', { name: /Bulletin/ })
    await request.getByRole('button', { name: 'Approve' }).click()
    await expect(page.getByText(/can now edit "Bulletin"/)).toBeVisible()

    await member.reload()
    await bell(member, 1).click()
    await member
      .getByRole('menuitem', {
        name: 'Unread: Olive Owner approved your request to edit "Bulletin"',
      })
      .click()
    await expect(member.getByRole('heading', { level: 1, name: 'Bulletin' })).toBeVisible()
    await expect(member.getByLabel('Content')).toBeEditable()
    await expect(bell(member)).toBeVisible()
    await member.context().close()
  })
})
