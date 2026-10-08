import { expect, type Page, test } from '@playwright/test'

import {
  ACCOUNT_MEMBER,
  ACME_MEMBER,
  fillLoginForm,
  logIn,
  logInElsewhere,
  logOut,
  openAccountSettings,
} from './fixtures'

const NEW_PASSWORD = 'Changed-E2e-Pass-789!'

async function changePassword(page: Page, current: string, next: string) {
  await page.getByLabel('Current password').fill(current)
  await page.getByLabel('New password', { exact: true }).fill(next)
  await page.getByLabel('Confirm new password').fill(next)
  await page.getByRole('button', { name: 'Change password' }).click()
}

test('changing the password keeps this session, signs out the others, and replaces the old one', async ({
  page,
  browser,
}) => {
  const elsewhere = await logInElsewhere(browser, ACCOUNT_MEMBER)
  await logIn(page, ACCOUNT_MEMBER)
  await openAccountSettings(page)
  await expect(page.getByRole('definition')).toHaveText([
    ACCOUNT_MEMBER.email,
    'Member',
    ACCOUNT_MEMBER.organization,
  ])

  await changePassword(page, ACCOUNT_MEMBER.password, NEW_PASSWORD)
  await expect(
    page.getByText('Password changed. Your other devices have been signed out.'),
  ).toBeVisible()

  // A reload restores the session from the refresh cookie: the new one here,
  // a revoked one in the other browser.
  await page.reload()
  await expect(page.getByRole('heading', { level: 1, name: 'Account' })).toBeVisible()
  await elsewhere.reload()
  await expect(elsewhere.getByRole('heading', { name: 'Log in' })).toBeVisible()
  await elsewhere.context().close()

  await logOut(page)
  await fillLoginForm(page, ACCOUNT_MEMBER)
  await expect(page.getByRole('alert')).toContainText(
    'No active account found with the given credentials',
  )
  await fillLoginForm(page, { ...ACCOUNT_MEMBER, password: NEW_PASSWORD })
  await expect(page.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible()
})

test('a wrong current password is reported under that field and changes nothing', async ({
  page,
}) => {
  await logIn(page, ACME_MEMBER)
  await openAccountSettings(page)

  await changePassword(page, 'Not-My-Pass-123!', NEW_PASSWORD)

  await expect(page.getByLabel('Current password')).toHaveAccessibleDescription(
    'Current password is incorrect.',
  )
  await logOut(page)
  await logIn(page, ACME_MEMBER)
})
