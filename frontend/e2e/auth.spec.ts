import { expect, test } from '@playwright/test'

import { ACME_MEMBER, fillLoginForm, LAPSED_ADMIN, logIn, logOut } from './fixtures'

test.describe('signing in and out', () => {
  test('keeps the session across a reload, and ends it on logout', async ({ page }) => {
    await logIn(page, ACME_MEMBER)

    // A fresh page load has no access token in memory: the session comes back
    // from the HttpOnly refresh cookie.
    await page.reload()
    await expect(page.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Account menu' })).toContainText(
      ACME_MEMBER.email,
    )

    await logOut(page)
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible()
  })

  test("shows the server's message for a wrong password", async ({ page }) => {
    await page.goto('/login')
    await fillLoginForm(page, { ...ACME_MEMBER, password: 'Wrong-Pass-123!' })

    await expect(page.getByRole('alert')).toContainText(
      'No active account found with the given credentials',
    )
  })

  test('returns to the requested page after logging in', async ({ page }) => {
    await page.goto('/people?search=member')
    await expect(page).toHaveURL(/\/login$/)

    await fillLoginForm(page, ACME_MEMBER)

    await expect(page).toHaveURL(/\/people\?search=member$/)
    await expect(page.getByRole('heading', { level: 1, name: 'People' })).toBeVisible()
  })

  test("offers the plans to a lapsed organization's admin", async ({ page }) => {
    await page.goto('/login')
    await fillLoginForm(page, LAPSED_ADMIN)

    await expect(page.getByRole('heading', { name: 'Subscribe to continue' })).toBeVisible()
    await expect(page.getByRole('list', { name: 'Plans' })).toBeVisible()
  })

  test('creates a new organization and signs its admin in', async ({ page }) => {
    const email = `founder-${Date.now()}@signup.e2e.test`

    await page.goto('/signup')
    await page.getByLabel('Organization name').fill(`Signup ${Date.now()}`)
    await page.getByLabel('Your email').fill(email)
    await page.getByLabel('Password', { exact: true }).fill('Founder-Pass-123!')
    await page.getByLabel('Confirm password').fill('Founder-Pass-123!')
    await page.getByRole('button', { name: 'Create organization' }).click()

    // A brand-new organization has no subscription yet: its admin picks a plan.
    await expect(page.getByRole('heading', { name: 'Subscribe to continue' })).toBeVisible()
  })
})

test('logging out in one tab signs the other tabs out too', async ({ context }) => {
  const firstTab = await context.newPage()
  await logIn(firstTab, ACME_MEMBER)
  const secondTab = await context.newPage()
  await secondTab.goto('/people')
  await expect(secondTab.getByRole('heading', { level: 1, name: 'People' })).toBeVisible()

  await logOut(firstTab)

  await expect(secondTab.getByRole('heading', { name: 'Log in' })).toBeVisible()
})
