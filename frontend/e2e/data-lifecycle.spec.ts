import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'

import {
  CLOSING_ADMIN,
  CLOSING_MEMBER,
  emailedLink,
  EXPORT_ADMIN,
  fillLoginForm,
  LEAVING_ADMIN,
  LEAVING_MEMBER,
  logIn,
  logInElsewhere,
  openAccountSettings,
} from './fixtures'

test.describe('leaving', () => {
  test('a member deletes their account and can no longer sign in', async ({ page, browser }) => {
    await logIn(page, LEAVING_MEMBER)
    await openAccountSettings(page)
    await page.getByRole('button', { name: 'Delete my account' }).click()
    const dialog = page.getByRole('form', { name: 'Delete your account' })
    await dialog.getByLabel('Current password').fill(LEAVING_MEMBER.password)
    await dialog.getByRole('button', { name: 'Delete my account' }).click()

    await expect(page.getByText('Your account has been deleted.')).toBeVisible()
    await expect(page).toHaveURL(/\/login$/)
    await fillLoginForm(page, LEAVING_MEMBER)
    await expect(page.getByText(/No active account/)).toBeVisible()

    // Their admin finds it in the activity, under no name but "Deleted user".
    const admin = await logInElsewhere(browser, LEAVING_ADMIN)
    await admin.goto('/activity')
    await expect(admin.getByRole('list', { name: 'Activity' })).toContainText(
      'Deleted their accountDeleted user ·',
    )
    await admin.context().close()
  })

  test('a lapsed organization deletes itself; its member leaves, its admin restores it', async ({
    page,
    browser,
  }) => {
    await page.goto('/login')
    await fillLoginForm(page, CLOSING_ADMIN)
    await expect(page.getByRole('heading', { name: 'Subscribe to continue' })).toBeVisible()
    await page.getByRole('button', { name: 'Delete organization' }).click()
    const dialog = page.getByRole('form', { name: 'Delete Closing E2E' })
    await dialog.getByLabel('Type "Closing E2E" to confirm').fill('Closing E2E')
    await dialog.getByRole('button', { name: 'Delete organization' }).click()
    await expect(page.getByRole('heading', { name: 'Organization deleted' })).toBeVisible()
    await expect(page.getByText(/will be removed for good on/)).toBeVisible()

    const member = await (await browser.newContext()).newPage()
    await member.goto('/login')
    await fillLoginForm(member, CLOSING_MEMBER)
    await expect(member.getByText(/Ask an admin if this is a mistake/)).toBeVisible()
    await expect(member.getByRole('button', { name: 'Restore organization' })).toHaveCount(0)
    // Leaving now frees their address, rather than at the purge.
    await member.getByRole('button', { name: 'Delete my account' }).click()
    const leave = member.getByRole('form', { name: 'Delete your account' })
    await leave.getByLabel('Current password').fill(CLOSING_MEMBER.password)
    await leave.getByRole('button', { name: 'Delete my account' }).click()
    await expect(member.getByText('Your account has been deleted.')).toBeVisible()
    await expect(member).toHaveURL(/\/login$/)
    await member.context().close()

    await page.getByRole('button', { name: 'Restore organization' }).click()
    await expect(page.getByText('Restored Closing E2E.')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Subscribe to continue' })).toBeVisible()
  })
})

test('an admin exports the organization and downloads it from the emailed link', async ({
  page,
}) => {
  await logIn(page, EXPORT_ADMIN)
  await page.goto('/settings/organization')
  await page.getByRole('button', { name: 'Email me an export' }).click()
  await expect(page.getByText(/We'll email you a link when it's ready/)).toBeVisible()

  await page.goto(await emailedLink(EXPORT_ADMIN.email, '/settings/organization/export'))
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Download export' }).click(),
  ])

  expect(download.suggestedFilename()).toBe('docsphere-export.zip')
  // A zip lists its files' names uncompressed: the data, and the public
  // document's attached file.
  const archive = readFileSync(await download.path()).toString('latin1')
  expect(archive.startsWith('PK')).toBe(true)
  for (const name of ['organization.json', 'members.json', 'documents.json', 'policies.pdf']) {
    expect(archive).toContain(name)
  }
})
