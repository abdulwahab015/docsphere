import { expect, type Page, test } from '@playwright/test'

import { ACTIVITY_ADMIN, logIn, openDocument } from './fixtures'

async function openActivity(page: Page) {
  await page
    .getByRole('navigation', { name: 'Main' })
    .getByRole('link', { name: 'Activity' })
    .click()
  await expect(page.getByRole('heading', { level: 1, name: 'Activity' })).toBeVisible()
}

test.describe('activity', () => {
  test('an admin shares a document and finds it in Activity, beside a private one left unnamed', async ({
    page,
  }) => {
    await logIn(page, ACTIVITY_ADMIN)

    await openDocument(page, 'Charter')
    await page.getByRole('button', { name: 'Share' }).click()
    const dialog = page.getByRole('dialog', { name: /^Share/ })
    await dialog.getByLabel('Add as').selectOption('EDITOR')
    await dialog.getByLabel('Search people by name or email').fill('member@activity')
    await dialog.getByRole('button', { name: 'Add Morgan Member' }).click()
    await expect(page.getByText('Morgan Member now has Editor access.')).toBeVisible()
    await page.keyboard.press('Escape')

    await openActivity(page)
    const entries = page.getByRole('list', { name: 'Activity' }).getByRole('listitem')
    // Newest first: the share just made, then the member's seeded one.
    await expect(entries.nth(0)).toContainText(
      'Gave Morgan Member Editor access to the document "Charter"Avery Admin ·',
    )
    await expect(entries.nth(1)).toContainText(
      'Gave Casey Colleague Viewer access to a private documentMorgan Member ·',
    )
    await expect(page.getByRole('list', { name: 'Activity' })).not.toContainText('Diary')

    await page.getByLabel('Search activity').fill('casey')
    await expect(entries).toHaveCount(1)
    await expect(entries.nth(0)).toContainText('a private document')

    await page.getByLabel('Kind').selectOption('Membership')
    await expect(page.getByRole('heading', { name: 'No matching activity' })).toBeVisible()
    await expect(page).toHaveURL(/\?search=casey&kind=MEMBERSHIP$/)
  })
})
