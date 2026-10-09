import { expect, type Locator, type Page, test } from '@playwright/test'

import {
  appCode,
  fillLoginForm,
  latestEmailTo,
  logIn,
  logInElsewhere,
  logInWithCode,
  logOut,
  openAccountSettings,
  REQUIRED_ADMIN,
  REQUIRED_MEMBER,
  TWO_FACTOR_ADMIN,
  TWO_FACTOR_PHONE,
  TWO_FACTOR_SETUP,
} from './fixtures'

/** Goes through setup in `area` (the account page's dialog, or the screen an
 * organization's requirement shows) as someone with an authenticator app
 * would: scan the key - here, read it - and type the code it shows. Returns
 * the recovery codes. */
async function setUpTwoFactor(area: Locator) {
  await area.getByRole('button', { name: 'Get started' }).click()
  await expect(area.getByRole('img', { name: 'QR code for your authenticator app' })).toBeVisible()
  const key = (await area.locator('code').textContent())!.replaceAll(' ', '')
  await area.getByLabel('Code from your app').fill(appCode(key))
  await area.getByRole('button', { name: 'Turn on' }).click()

  const codes = area.getByRole('list', { name: 'Recovery codes' }).getByRole('listitem')
  await expect(codes).toHaveCount(10)
  const recoveryCodes = await codes.allTextContents()
  await area.getByRole('button', { name: "I've saved them" }).click()
  return recoveryCodes
}

function memberRow(page: Page, email: string) {
  return page.getByRole('row', { name: new RegExp(email) })
}

test('a member turns on two-factor sign-in, then logs in with a recovery code', async ({
  page,
}) => {
  await logIn(page, TWO_FACTOR_SETUP)
  await openAccountSettings(page)
  await page.getByRole('button', { name: 'Turn on two-factor sign-in' }).click()
  const recoveryCodes = await setUpTwoFactor(
    page.getByRole('dialog', { name: 'Turn on two-factor sign-in' }),
  )
  await expect(page.getByText('You have 10 recovery codes left.')).toBeVisible()

  // The password alone no longer signs them in.
  await logOut(page)
  await fillLoginForm(page, TWO_FACTOR_SETUP)
  await expect(page.getByRole('heading', { name: 'Two-factor sign-in' })).toBeVisible()
  await page.getByRole('button', { name: 'Use a recovery code' }).click()
  await page.getByLabel('Recovery code').fill(recoveryCodes[0])
  await page.getByRole('button', { name: 'Verify' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible()

  await openAccountSettings(page)
  await expect(page.getByText('You have 9 recovery codes left.')).toBeVisible()

  // A used recovery code doesn't work twice.
  await logOut(page)
  await fillLoginForm(page, TWO_FACTOR_SETUP)
  await page.getByRole('button', { name: 'Use a recovery code' }).click()
  await page.getByLabel('Recovery code').fill(recoveryCodes[0])
  await page.getByRole('button', { name: 'Verify' }).click()
  await expect(page.getByText(/That code didn't work/)).toBeVisible()
})

test('an admin logs in with a code from their app and resets a member who lost their phone', async ({
  page,
  browser,
}, testInfo) => {
  // A wrong code first.
  const secret = TWO_FACTOR_ADMIN.twoFactorSecret!
  const wrongCode = String((Number(appCode(secret)) + 500_000) % 1_000_000).padStart(6, '0')
  await page.goto('/login')
  await fillLoginForm(page, TWO_FACTOR_ADMIN)
  await page.getByLabel('Code from your app').fill(wrongCode)
  await page.getByRole('button', { name: 'Verify' }).click()
  await expect(page.getByText(/That code didn't work/)).toBeVisible()
  await page.getByLabel('Code from your app').fill(appCode(secret, testInfo.retry))
  await page.getByRole('button', { name: 'Verify' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible()

  await page.goto('/people')
  await expect(memberRow(page, TWO_FACTOR_PHONE.email)).toContainText('On')
  await page.getByRole('button', { name: `Actions for ${TWO_FACTOR_PHONE.email}` }).click()
  await page.getByRole('menuitem', { name: 'Reset two-factor sign-in' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Reset' }).click()
  await expect(
    page.getByText(`Reset ${TWO_FACTOR_PHONE.email}'s two-factor sign-in.`),
  ).toBeVisible()
  await expect(memberRow(page, TWO_FACTOR_PHONE.email)).toContainText('Off')

  // They're told, and sign in with their password alone.
  expect(await latestEmailTo(TWO_FACTOR_PHONE.email)).toContain(
    `turned off two-factor sign-in for your DocSphere account (${TWO_FACTOR_PHONE.email})`,
  )
  const member = await logInElsewhere(browser, TWO_FACTOR_PHONE)
  await member.context().close()

  await page.goto('/activity')
  await expect(page.getByText(`Reset ${TWO_FACTOR_PHONE.email}'s two-factor sign-in`)).toBeVisible()
})

test('an admin requires two-factor sign-in, and a member without it sets it up before anything else', async ({
  page,
  browser,
}, testInfo) => {
  const member = await logInElsewhere(browser, REQUIRED_MEMBER)

  await logInWithCode(page, REQUIRED_ADMIN, testInfo.retry)
  await page.goto('/settings/organization')
  await page.getByRole('button', { name: 'Require two-factor sign-in' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Require it' }).click()
  await expect(page.getByText('Two-factor sign-in is now required.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Stop requiring it' })).toBeVisible()

  // The member's next request is refused, and the app asks them to set it up.
  await member.getByRole('link', { name: 'Documents' }).click()
  const screen = member.getByRole('main')
  await expect(screen.getByRole('heading', { name: 'Set up two-factor sign-in' })).toBeVisible()
  await expect(
    screen.getByText(
      `${REQUIRED_MEMBER.organization} requires a code from an authenticator app each time you log in.`,
    ),
  ).toBeVisible()
  await setUpTwoFactor(screen)
  await expect(member.getByRole('heading', { level: 1, name: 'Documents' })).toBeVisible()
  await member.context().close()
})
