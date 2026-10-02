import { expect, test } from '@playwright/test'

import {
  fillLoginForm,
  LAPSED_MEMBER,
  logIn,
  PAID_ADMIN,
  stubStripeEndpoint,
  UNPAID_ADMIN,
} from './fixtures'

test.describe('a lapsed organization', () => {
  test('its admin adds a billing email, then subscribes through Stripe Checkout', async ({
    page,
    baseURL,
  }) => {
    // Stripe would send the admin back here after paying.
    const checkout = await stubStripeEndpoint(page, '/subscriptions/checkout/', {
      checkout_url: `${baseURL}/billing/success/`,
    })
    await page.goto('/login')
    await fillLoginForm(page, UNPAID_ADMIN)
    await expect(page.getByRole('heading', { name: 'Subscribe to continue' })).toBeVisible()

    const plans = page.getByRole('list', { name: 'Plans' })
    await expect(plans.getByRole('heading', { name: 'Monthly' })).toBeVisible()
    await expect(plans.getByText('per year')).toBeVisible()
    const subscribe = page.getByRole('button', { name: 'Subscribe to the yearly plan' })
    await expect(subscribe).toBeDisabled()

    await page.getByLabel('Billing email').fill(`billing-${Date.now()}@unpaid.e2e.test`)
    await page.getByRole('button', { name: 'Save billing email' }).click()
    await expect(page.getByText('Billing email saved.')).toBeVisible()
    await subscribe.click()

    await expect(page.getByRole('heading', { name: 'Confirming your payment' })).toBeVisible()
    expect(checkout).toEqual([{ price_id: expect.stringMatching(/^price_/) }])
  })

  test('backing out of checkout leads back to the plans', async ({ page }) => {
    await page.goto('/login')
    await fillLoginForm(page, UNPAID_ADMIN)
    await expect(page.getByRole('heading', { name: 'Subscribe to continue' })).toBeVisible()

    await page.goto('/billing/cancel/')
    await expect(page.getByRole('heading', { name: 'Checkout cancelled' })).toBeVisible()
    await page.getByRole('link', { name: 'Back to billing' }).click()

    await expect(page.getByRole('heading', { name: 'Subscribe to continue' })).toBeVisible()
  })

  test('its members are told to ask their admin', async ({ page }) => {
    await page.goto('/login')
    await fillLoginForm(page, LAPSED_MEMBER)

    await expect(page.getByRole('heading', { name: 'Subscription inactive' })).toBeVisible()
    await expect(page.getByText(/Ask your organization admin/)).toBeVisible()
    await expect(page.getByRole('list', { name: 'Plans' })).toHaveCount(0)
  })
})

test("a subscribed organization's admin sees the plan and opens the billing portal", async ({
  page,
  baseURL,
}) => {
  // The portal sends the admin back to the Billing page when they're done.
  const portal = await stubStripeEndpoint(page, '/subscriptions/portal/', {
    portal_url: `${baseURL}/billing/`,
  })
  await logIn(page, PAID_ADMIN)
  await page
    .getByRole('navigation', { name: 'Main' })
    .getByRole('link', { name: 'Billing' })
    .click()

  await expect(page.getByRole('heading', { level: 1, name: 'Billing' })).toBeVisible()
  await expect(page.getByText('Monthly plan')).toBeVisible()
  await expect(page.getByText(/^Renews on /)).toBeVisible()
  await expect(page.getByLabel('Billing email')).toHaveValue('billing@paid.e2e.test')
  await expect(page.getByRole('list', { name: 'Plans' })).toHaveCount(0)

  await page.getByRole('button', { name: 'Manage billing' }).click()
  await expect.poll(() => portal.length).toBe(1)
  await expect(page.getByRole('heading', { level: 1, name: 'Billing' })).toBeVisible()
})
