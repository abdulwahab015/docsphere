import { expect, test } from '@playwright/test'

import {
  DOCS_ADMIN,
  DOCS_READER,
  DOCS_STRANGER,
  DOCS_WRITER,
  logIn,
  logOut,
  openDocument,
  openProject,
  uniqueName,
} from './fixtures'

test.describe('documents inside a project', () => {
  test("project access doesn't include the project's documents", async ({ page }) => {
    await logIn(page, DOCS_WRITER)

    await openProject(page, 'Research')

    await expect(page.getByRole('link', { name: 'Findings', exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Draft notes', exact: true })).toHaveCount(0)
    await expect(
      page.getByText(/access to this project doesn't include the documents/),
    ).toBeVisible()
  })

  test('a project editor adds a document and writes it', async ({ page }) => {
    const title = uniqueName('Plan')
    const content = `Written at ${Date.now()}.`
    await logIn(page, DOCS_WRITER)
    await openProject(page, 'Research')

    await page.getByRole('button', { name: 'New document' }).click()
    const dialog = page.getByRole('dialog', { name: 'New document' })
    await dialog.getByLabel('Title').fill(title)
    await dialog.getByRole('button', { name: 'Create document' }).click()
    await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
    await expect(page.getByText('Owner', { exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Research' })).toBeVisible()

    await page.getByLabel('Content').fill(content)
    await page.getByRole('button', { name: 'Save' }).click()
    await expect(page.getByText('Document saved.')).toBeVisible()

    await page.reload()
    await expect(page.getByLabel('Content')).toHaveValue(content)
  })

  test("a project viewer can't add documents", async ({ page }) => {
    await logIn(page, DOCS_READER)

    await openProject(page, 'Research')

    await expect(page.getByRole('link', { name: 'Findings', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'New document' })).toHaveCount(0)
  })
})

test.describe('access levels on a document', () => {
  test('an editor edits, but cannot delete or change visibility', async ({ page }) => {
    const addition = ` Checked at ${Date.now()}.`
    await logIn(page, DOCS_WRITER)
    await openDocument(page, 'Findings')

    await page.getByLabel('Content').press('End')
    await page.getByLabel('Content').pressSequentially(addition)
    await page.getByLabel('Content').press('ControlOrMeta+s')

    await expect(page.getByText('Document saved.')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /Make (public|private)/ })).toHaveCount(0)
  })

  test('a viewer reads without editing controls', async ({ page }) => {
    await logIn(page, DOCS_READER)

    await openDocument(page, 'Findings')

    await expect(page.getByText(/Early results look promising/)).toBeVisible()
    await expect(page.getByLabel('Content')).toHaveCount(0)
    await expect(page.getByText('Viewer', { exact: true })).toBeVisible()
  })

  test('names the project only to readers who can open it', async ({ page }) => {
    await logIn(page, DOCS_STRANGER)

    await openDocument(page, 'Shared brief')

    await expect(page.getByText("A project you can't open")).toBeVisible()
    await expect(page.getByRole('link', { name: 'Research' })).toHaveCount(0)
  })
})

test('private documents stay hidden; public ones are open to every member', async ({ page }) => {
  await logIn(page, DOCS_ADMIN)
  await openDocument(page, 'Draft notes')
  const draftUrl = page.url()
  await logOut(page)

  await logIn(page, DOCS_STRANGER)
  await page.goto('/documents')
  await expect(page.getByRole('link', { name: 'Team guide', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Findings', exact: true })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Draft notes', exact: true })).toHaveCount(0)

  await page.goto(draftUrl)
  await expect(page.getByRole('heading', { name: 'Not found' })).toBeVisible()
})

test('a personal document: create, publish, delete and restore', async ({ page }) => {
  const title = uniqueName('Journal')
  await logIn(page, DOCS_STRANGER)
  await page.goto('/documents')

  await page.getByRole('button', { name: 'New document' }).click()
  const dialog = page.getByRole('dialog', { name: 'New document' })
  await dialog.getByLabel('Title').fill(title)
  await dialog.getByRole('button', { name: 'Create document' }).click()
  await expect(page.getByText('None (personal document)')).toBeVisible()

  await page.getByRole('button', { name: 'Make public' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Make public' }).click()
  await expect(page.getByText('Document is now public.')).toBeVisible()

  await page.getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Delete document' }).click()
  await expect(page.getByText(`Moved "${title}" to your trash.`)).toBeVisible()

  await page.getByRole('link', { name: 'Trash' }).click()
  await page.getByRole('button', { name: `Restore ${title}` }).click()
  await expect(page.getByText(`Restored "${title}".`)).toBeVisible()
  await openDocument(page, title)
})

test("a member's trash holds the documents they own", async ({ page }) => {
  await logIn(page, DOCS_WRITER)
  await page.goto('/documents')

  await page.getByRole('link', { name: 'Trash' }).click()

  await expect(page.getByRole('cell', { name: 'Old memo', exact: true })).toBeVisible()
})

test('asks before leaving a document with unsaved changes', async ({ page }) => {
  await logIn(page, DOCS_WRITER)
  await openDocument(page, 'Findings')
  const documentUrl = page.url()
  await page.getByLabel('Content').pressSequentially(' unsaved')
  const projectsLink = page.getByRole('navigation', { name: 'Main' }).getByRole('link', {
    name: 'Projects',
  })

  await projectsLink.click()
  const confirm = page.getByRole('alertdialog', { name: 'Discard unsaved changes?' })
  await confirm.getByRole('button', { name: 'Cancel' }).click()
  await expect(page).toHaveURL(documentUrl)

  await projectsLink.click()
  await confirm.getByRole('button', { name: 'Discard changes' }).click()
  await expect(page).toHaveURL(/\/projects$/)
})
