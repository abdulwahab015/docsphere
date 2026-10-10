import { expect, test } from '@playwright/test'

import { ACME_ADMIN, ACME_MEMBER, logIn, memberCount, SETTINGS_ADMIN } from './fixtures'

const ACME_MEMBERS = memberCount('Acme E2E')
const PAGE_SIZE = 20

test.describe('people directory', () => {
  test('pages through and searches the real roster', async ({ page }) => {
    await logIn(page, ACME_MEMBER)
    await page
      .getByRole('navigation', { name: 'Main' })
      .getByRole('link', { name: 'People' })
      .click()

    await expect(page.getByText(`Showing 1–${PAGE_SIZE} of ${ACME_MEMBERS}`)).toBeVisible()
    await page.getByRole('button', { name: 'Next' }).click()
    await expect(
      page.getByText(`Showing ${PAGE_SIZE + 1}–${ACME_MEMBERS} of ${ACME_MEMBERS}`),
    ).toBeVisible()
    await expect(page).toHaveURL(/\?page=2$/)

    await page.getByRole('searchbox', { name: 'Search people' }).fill('admin@acme')
    await expect(page.getByText('Showing 1–1 of 1')).toBeVisible()
    await expect(page.getByRole('cell', { name: ACME_ADMIN.email })).toBeVisible()
    await expect(page).toHaveURL(/\?search=admin%40acme$/)
  })
})

test.describe('organization settings', () => {
  test('lets an admin rename the organization', async ({ page }) => {
    const newName = `Settings E2E ${Date.now()}`
    await logIn(page, SETTINGS_ADMIN)
    await page
      .getByRole('navigation', { name: 'Main' })
      .getByRole('link', { name: 'Organization' })
      .click()

    await page.getByLabel('Organization name').fill(newName)
    await page.getByRole('button', { name: 'Save changes' }).click()

    await expect(page.getByText('Organization details saved.')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Account menu' })).toContainText(newName)
    await page.reload()
    await expect(page.getByLabel('Organization name')).toHaveValue(newName)
  })

  test('is hidden from members, and refused if opened directly', async ({ page }) => {
    await logIn(page, ACME_MEMBER)

    await expect(
      page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Organization' }),
    ).toHaveCount(0)
    await page.goto('/settings/organization')
    await expect(page.getByRole('heading', { name: "You don't have access" })).toBeVisible()
  })
})

test('shows a not-found page for unknown addresses', async ({ page }) => {
  await logIn(page, ACME_MEMBER)

  await page.goto('/no-such-page')

  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
})

test.describe('on a phone-sized screen', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('opens the navigation from the menu button', async ({ page }) => {
    await logIn(page, ACME_MEMBER)
    const navigation = page.getByRole('navigation', { name: 'Main' })
    await expect(navigation).toBeHidden()

    await page.getByRole('button', { name: 'Toggle navigation' }).click()
    await navigation.getByRole('link', { name: 'People' }).click()

    await expect(page.getByRole('heading', { level: 1, name: 'People' })).toBeVisible()
  })

  test("keeps a table to its essential columns, and shows the rest when there's room", async ({
    page,
  }) => {
    await logIn(page, ACME_ADMIN)
    await page.goto('/people')
    const table = page.getByRole('table')
    await expect(table.getByRole('columnheader', { name: 'Person' })).toBeVisible()
    await expect(table.getByRole('columnheader', { name: 'Role' })).toBeVisible()
    await expect(table.getByRole('columnheader', { name: 'Joined' })).toBeHidden()

    await page.setViewportSize({ width: 1280, height: 800 })
    await expect(table.getByRole('columnheader', { name: 'Joined' })).toBeVisible()
  })
})
