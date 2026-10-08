import { expect, test } from '@playwright/test'

import {
  logIn,
  logInElsewhere,
  NAMES_ADMIN,
  NAMES_MEMBER,
  openAccountSettings,
  openProject,
} from './fixtures'

test('a name set in account settings is how colleagues see and find that person', async ({
  page,
  browser,
}) => {
  await logIn(page, NAMES_MEMBER)
  await openAccountSettings(page)
  await page.getByLabel('Your name').fill('Grace Hopper')
  await page.getByRole('button', { name: 'Save name' }).click()
  await expect(page.getByText('Name saved.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Account menu' })).toContainText('Grace Hopper')

  // Their admin sees the name in People, with the address beneath it...
  const admin = await logInElsewhere(browser, NAMES_ADMIN)
  await admin.goto('/people')
  const row = admin.getByRole('row', { name: new RegExp(NAMES_MEMBER.email) })
  await expect(row.getByText('Grace Hopper')).toBeVisible()

  // ...and finds them by it when sharing.
  await openProject(admin, 'Launch')
  await admin.getByRole('button', { name: 'Share' }).click()
  const dialog = admin.getByRole('dialog', { name: /^Share/ })
  await dialog.getByLabel('Search people by name or email').fill('hopper')
  await dialog.getByRole('button', { name: 'Add Grace Hopper' }).click()
  await expect(admin.getByText('Grace Hopper now has Viewer access.')).toBeVisible()
  await expect(
    dialog.getByRole('list', { name: 'People with access' }).getByText('Grace Hopper'),
  ).toBeVisible()
  await admin.context().close()

  // The project's creator, seeded with a name, is shown by it too.
  await openProject(page, 'Launch')
  await expect(page.getByText('Ada Admin')).toBeVisible()
})
