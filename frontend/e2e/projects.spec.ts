import { expect, test } from '@playwright/test'

import {
  createProject,
  logIn,
  logOut,
  openProject,
  PROJECTS_ADMIN,
  PROJECTS_EDITOR,
  PROJECTS_OUTSIDER,
  PROJECTS_VIEWER,
  uniqueName,
} from './fixtures'

test.describe('as an admin', () => {
  test('creates a project and becomes its owner', async ({ page }) => {
    const name = uniqueName('Launch')
    await logIn(page, PROJECTS_ADMIN)

    await createProject(page, name, 'Public')

    await expect(page.getByText(`Created "${name}".`)).toBeVisible()
    await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
    await expect(page.getByText('Owner', { exact: true })).toBeVisible()
    await page.getByRole('link', { name: 'Projects', exact: true }).first().click()
    await page.getByRole('searchbox', { name: 'Search projects' }).fill(name)
    await expect(page.getByRole('link', { name, exact: true })).toBeVisible()
  })

  test("can't reuse a project name", async ({ page }) => {
    await logIn(page, PROJECTS_ADMIN)

    await createProject(page, 'Handbook', 'Private')

    await expect(
      page
        .getByRole('dialog')
        .getByText('A project with this name already exists in your organization.'),
    ).toBeVisible()
  })

  test('changes visibility, deletes, and restores from the trash', async ({ page }) => {
    const name = uniqueName('Lifecycle')
    await logIn(page, PROJECTS_ADMIN)
    await createProject(page, name, 'Private')
    await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()

    await page.getByRole('button', { name: 'Make public' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Make public' }).click()
    await expect(page.getByText('Project is now public.')).toBeVisible()

    await page.getByRole('button', { name: 'Delete' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Delete project' }).click()
    await expect(page.getByText(`Moved "${name}" to the trash.`)).toBeVisible()
    await expect(page).toHaveURL(/\/projects$/)

    await page.getByRole('link', { name: 'Trash' }).click()
    await page.getByRole('button', { name: `Restore ${name}` }).click()
    await expect(page.getByText(`Restored "${name}".`)).toBeVisible()
    await openProject(page, name)
    await expect(page.getByText('Public', { exact: true })).toBeVisible()
  })

  test('sees deleted projects in the trash', async ({ page }) => {
    await logIn(page, PROJECTS_ADMIN)
    await page.goto('/projects')

    await page.getByRole('link', { name: 'Trash' }).click()

    await expect(page.getByRole('cell', { name: 'Archived launch', exact: true })).toBeVisible()
  })
})

test.describe('access levels', () => {
  test('an editor can edit but not delete or change visibility', async ({ page }) => {
    const description = `Updated by the editor at ${Date.now()}.`
    await logIn(page, PROJECTS_EDITOR)
    await openProject(page, 'Roadmap')

    await page.getByRole('button', { name: 'Edit' }).click()
    const dialog = page.getByRole('dialog', { name: 'Edit project' })
    await dialog.getByLabel('Description (optional)').fill(description)
    await dialog.getByRole('button', { name: 'Save changes' }).click()

    await expect(page.getByText('Project updated.')).toBeVisible()
    await expect(page.getByText(description)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /Make (public|private)/ })).toHaveCount(0)
  })

  test('a viewer sees the project read-only', async ({ page }) => {
    await logIn(page, PROJECTS_VIEWER)

    await openProject(page, 'Roadmap')

    await expect(page.getByText('Viewer', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Edit' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(0)
  })

  test('members see public projects but never private ones they lack access to', async ({
    page,
  }) => {
    await logIn(page, PROJECTS_ADMIN)
    await openProject(page, 'Secret plans')
    const secretUrl = page.url()
    await logOut(page)

    await logIn(page, PROJECTS_OUTSIDER)
    await expect(page.getByRole('link', { name: 'Handbook', exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Secret plans', exact: true })).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Roadmap', exact: true })).toHaveCount(0)

    // Even with the link, a private project is indistinguishable from a missing one.
    await page.goto(secretUrl)
    await expect(page.getByRole('heading', { name: 'Not found' })).toBeVisible()
  })

  test("members can't create projects or open the trash", async ({ page }) => {
    await logIn(page, PROJECTS_EDITOR)

    await expect(page.getByRole('button', { name: 'New project' })).toHaveCount(0)
    await page.goto('/projects/trash')
    await expect(page.getByRole('heading', { name: "You don't have access" })).toBeVisible()
  })
})
