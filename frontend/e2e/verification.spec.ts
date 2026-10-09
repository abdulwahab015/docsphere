import { expect, test } from '@playwright/test'

import { emailedLink } from './fixtures'

test("a new organization's admin verifies their email before anything else", async ({
  context,
}) => {
  const email = `founder-${Date.now()}@signup.e2e.test`
  const page = await context.newPage()

  await page.goto('/signup')
  await page.getByLabel('Organization name').fill(`Signup ${Date.now()}`)
  await page.getByLabel('Your email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill('Founder-Pass-123!')
  await page.getByLabel('Confirm password').fill('Founder-Pass-123!')
  await page.getByRole('button', { name: 'Create organization' }).click()

  // Signed in, but nothing more until the address is proven theirs.
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible()
  await expect(page.getByText(email)).toBeVisible()
  await page.getByRole('button', { name: 'Send a new link' }).click()
  await expect(page.getByText(`A new link is on its way to ${email}.`)).toBeVisible()

  // The link opens in another tab, as from a mail client.
  const linkTab = await context.newPage()
  await linkTab.goto(await emailedLink(email, '/verify-email'))
  await expect(linkTab.getByRole('heading', { name: 'Email verified' })).toBeVisible()

  // The tab that was waiting lets them in without a reload. A brand-new
  // organization has no subscription yet: its admin picks a plan.
  await expect(page.getByRole('heading', { name: 'Subscribe to continue' })).toBeVisible()
  await linkTab.getByRole('link', { name: 'Continue to DocSphere' }).click()
  await expect(linkTab.getByRole('heading', { name: 'Subscribe to continue' })).toBeVisible()
})

test('a verification link that has been tampered with is refused', async ({ page }) => {
  await page.goto('/verify-email?token=not-a-real-token')

  await expect(page.getByRole('heading', { name: "Couldn't verify your email" })).toBeVisible()
  await expect(page.getByText('This link is invalid or has expired.')).toBeVisible()
})
