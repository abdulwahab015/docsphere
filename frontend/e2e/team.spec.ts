import { type Browser, expect, type Page, test } from '@playwright/test'

import {
  emailedLink,
  fillLoginForm,
  logIn,
  logInElsewhere,
  TEAM_ADMIN,
  TEAM_FORGETFUL,
  TEAM_LEAVER,
  TEAM_PROMOTE,
} from './fixtures'

const INVALID_INVITATION = 'This invitation link is invalid or has expired.'
const NEW_PASSWORD = 'Fresh-E2e-Pass-456!'

/** An address no seeded account or earlier run has used. */
function freshAddress(name: string) {
  return `${name}-${Date.now()}@team.e2e.test`
}

async function openTab(page: Page, tab: 'Members' | 'Invitations' | 'Deactivated') {
  await page.goto('/people')
  await page.getByRole('tab', { name: tab }).click()
}

async function invite(page: Page, email: string) {
  await page.goto('/people')
  await page.getByRole('button', { name: 'Invite' }).click()
  const dialog = page.getByRole('dialog', { name: 'Invite someone' })
  await dialog.getByLabel('Email').fill(email)
  await dialog.getByRole('button', { name: 'Send invitation' }).click()
  await expect(page.getByText(`Invitation sent to ${email}.`)).toBeVisible()
}

/** Opens an emailed invitation link in a browser nobody is signed in to. */
async function openInvitation(browser: Browser, link: string) {
  const page = await (await browser.newContext()).newPage()
  await page.goto(link)
  await page.getByLabel('Password', { exact: true }).fill(NEW_PASSWORD)
  await page.getByLabel('Confirm password').fill(NEW_PASSWORD)
  await page.getByRole('button', { name: 'Create account' }).click()
  return page
}

async function chooseMemberAction(page: Page, email: string, action: string) {
  await page.getByRole('button', { name: `Actions for ${email}` }).click()
  await page.getByRole('menuitem', { name: action }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: action }).click()
}

test.describe('invitations', () => {
  test('an admin invites someone, who joins from the emailed link', async ({ page, browser }) => {
    const email = freshAddress('invitee')
    await logIn(page, TEAM_ADMIN)
    await invite(page, email)
    await openTab(page, 'Invitations')
    await expect(
      page.getByRole('row', { name: new RegExp(email) }).getByText('Pending'),
    ).toBeVisible()

    const invitee = await openInvitation(browser, await emailedLink(email, '/accept-invite'))
    await expect(invitee.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible()
    await invitee.context().close()

    await page.reload()
    await expect(
      page.getByRole('row', { name: new RegExp(email) }).getByText('Accepted'),
    ).toBeVisible()
    await page.getByRole('tab', { name: 'Members' }).click()
    await expect(
      page.getByRole('row', { name: new RegExp(email) }).getByText('Member'),
    ).toBeVisible()
  })

  test('resending replaces the link, and revoking stops the new one', async ({ page, browser }) => {
    const email = freshAddress('resend')
    await logIn(page, TEAM_ADMIN)
    await invite(page, email)
    const firstLink = await emailedLink(email, '/accept-invite')

    await openTab(page, 'Invitations')
    const row = page.getByRole('row', { name: new RegExp(email) })
    await row.getByRole('button', { name: 'Resend' }).click()
    await expect(
      page.getByText(`Sent a new invitation to ${email}.`, { exact: false }),
    ).toBeVisible()
    const secondLink = await emailedLink(email, '/accept-invite')
    expect(secondLink).not.toBe(firstLink)

    const oldLink = await openInvitation(browser, firstLink)
    await expect(oldLink.getByRole('alert')).toContainText(INVALID_INVITATION)
    await oldLink.context().close()

    await row.getByRole('button', { name: 'Revoke' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Revoke' }).click()
    await expect(row.getByText('Revoked')).toBeVisible()
    const revokedLink = await openInvitation(browser, secondLink)
    await expect(revokedLink.getByRole('alert')).toContainText(INVALID_INVITATION)
    await revokedLink.context().close()
  })

  test('an admin invites a list from a spreadsheet', async ({ page }) => {
    await logIn(page, TEAM_ADMIN)
    await page.goto('/people')
    await page.getByRole('button', { name: 'Upload a list' }).click()
    const dialog = page.getByRole('dialog', { name: 'Invite from a spreadsheet' })
    // e2e/files/invitations.xlsx: a header row, two new addresses, "not-an-email",
    // and the seeded admin's own address.
    await dialog.getByLabel('Spreadsheet').setInputFiles('e2e/files/invitations.xlsx')
    await dialog.getByRole('button', { name: 'Send invitations' }).click()

    const skipped = dialog.getByRole('table', { name: 'Skipped rows' })
    await expect(skipped.getByRole('row', { name: /not-an-email/ })).toContainText(/invalid email/i)
    await expect(skipped.getByRole('row', { name: /admin@team/ })).toContainText(
      /user already exists/i,
    )
    await dialog.getByRole('button', { name: 'Done' }).click()

    await openTab(page, 'Invitations')
    for (const email of ['bulk-one@team.e2e.test', 'bulk-two@team.e2e.test']) {
      await expect(
        page.getByRole('row', { name: new RegExp(email) }).getByText('Pending'),
      ).toBeVisible()
    }
  })
})

test.describe('members', () => {
  test('an admin makes a member an admin, and back', async ({ page, browser }) => {
    await logIn(page, TEAM_ADMIN)
    await page.goto('/people')
    await chooseMemberAction(page, TEAM_PROMOTE.email, 'Make admin')
    await expect(page.getByText(`${TEAM_PROMOTE.email} is now an admin.`)).toBeVisible()

    const promoted = await logInElsewhere(browser, TEAM_PROMOTE)
    const navigation = promoted.getByRole('navigation', { name: 'Main' })
    await expect(navigation.getByRole('link', { name: 'Organization' })).toBeVisible()

    await chooseMemberAction(page, TEAM_PROMOTE.email, 'Make member')
    await expect(page.getByText(`${TEAM_PROMOTE.email} is now a member.`)).toBeVisible()
    await promoted.reload()
    await expect(navigation.getByRole('link', { name: 'Projects' })).toBeVisible()
    await expect(navigation.getByRole('link', { name: 'Organization' })).toHaveCount(0)
    await promoted.context().close()
  })

  test('a deactivated member is signed out until reactivated', async ({ page, browser }) => {
    const leaver = await logInElsewhere(browser, TEAM_LEAVER)
    await logIn(page, TEAM_ADMIN)
    await page.goto('/people')
    await chooseMemberAction(page, TEAM_LEAVER.email, 'Deactivate')
    await expect(page.getByText(`Deactivated ${TEAM_LEAVER.email}.`)).toBeVisible()

    await leaver.reload()
    await expect(leaver.getByRole('heading', { name: 'Log in' })).toBeVisible()
    await fillLoginForm(leaver, TEAM_LEAVER)
    await expect(leaver.getByRole('alert')).toContainText('No active account found')

    await openTab(page, 'Deactivated')
    await page
      .getByRole('row', { name: new RegExp(TEAM_LEAVER.email) })
      .getByRole('button', { name: 'Reactivate' })
      .click()
    await expect(
      page.getByText(`Reactivated ${TEAM_LEAVER.email}.`, { exact: false }),
    ).toBeVisible()
    await fillLoginForm(leaver, TEAM_LEAVER)
    await expect(leaver.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible()
    await leaver.context().close()
  })
})

test('a forgotten password is reset from the emailed link', async ({ page }) => {
  await page.goto('/forgot-password')
  await page.getByLabel('Email').fill(TEAM_FORGETFUL.email)
  await page.getByRole('button', { name: 'Send reset link' }).click()
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible()

  await page.goto(await emailedLink(TEAM_FORGETFUL.email, '/reset-password'))
  await page.getByLabel('New password', { exact: true }).fill(NEW_PASSWORD)
  await page.getByLabel('Confirm new password').fill(NEW_PASSWORD)
  await page.getByRole('button', { name: 'Update password' }).click()
  await expect(page.getByRole('heading', { name: 'Password updated' })).toBeVisible()

  await page.getByRole('link', { name: 'Log in with your new password' }).click()
  await fillLoginForm(page, { ...TEAM_FORGETFUL, password: NEW_PASSWORD })
  await expect(page.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible()
})
