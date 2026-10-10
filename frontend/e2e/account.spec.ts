import { expect, type Page, test } from '@playwright/test'

import {
  ACCOUNT_MEMBER,
  ACCOUNT_MOVER,
  ACME_MEMBER,
  emailedLink,
  fillLoginForm,
  latestEmailTo,
  logIn,
  logInElsewhere,
  logOut,
  openAccountSettings,
} from './fixtures'

const NEW_PASSWORD = 'Changed-E2e-Pass-789!'

// The email form asks for the current password too.
function passwordForm(page: Page) {
  return page.getByRole('form', { name: 'Password' })
}

async function changePassword(page: Page, current: string, next: string) {
  const form = passwordForm(page)
  await form.getByLabel('Current password').fill(current)
  await form.getByLabel('New password', { exact: true }).fill(next)
  await form.getByLabel('Confirm new password').fill(next)
  await form.getByRole('button', { name: 'Change password' }).click()
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

  await expect(passwordForm(page).getByLabel('Current password')).toHaveAccessibleDescription(
    'Current password is incorrect.',
  )
  await logOut(page)
  await logIn(page, ACME_MEMBER)
})

test('changing the email takes effect from the link sent to the new address', async ({ page }) => {
  // Fresh each run, so a retry doesn't find the address already taken.
  const newEmail = `moved-${Date.now()}@account.e2e.test`
  await logIn(page, ACCOUNT_MOVER)
  await openAccountSettings(page)

  const emailForm = page.getByRole('form', { name: 'Change email' })
  await emailForm.getByLabel('New email').fill(newEmail)
  await emailForm.getByLabel('Current password').fill(ACCOUNT_MOVER.password)
  await emailForm.getByRole('button', { name: 'Send confirmation link' }).click()
  await expect(page.getByText(`Check ${newEmail} for a link to confirm the change.`)).toBeVisible()

  await page.goto(await emailedLink(newEmail, '/confirm-email'))
  await page.getByRole('button', { name: 'Confirm new email' }).click()
  await expect(page.getByRole('heading', { name: 'Email changed' })).toBeVisible()
  expect(await latestEmailTo(ACCOUNT_MOVER.email)).toContain(
    `changed from ${ACCOUNT_MOVER.email} to ${newEmail}`,
  )

  await page.getByRole('link', { name: 'Log in' }).click()
  await fillLoginForm(page, ACCOUNT_MOVER)
  await expect(page.getByRole('alert')).toContainText(
    'No active account found with the given credentials',
  )
  await fillLoginForm(page, { ...ACCOUNT_MOVER, email: newEmail })
  await expect(page.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible()
})
