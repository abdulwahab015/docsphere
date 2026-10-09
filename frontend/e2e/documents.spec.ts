import { expect, test } from '@playwright/test'

import {
  createDocument,
  createProject,
  DOCS_ADMIN,
  DOCS_READER,
  DOCS_STRANGER,
  DOCS_WRITER,
  logIn,
  logInElsewhere,
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

test("deleting a project hides its documents until it's restored", async ({ page }) => {
  const project = uniqueName('Archive')
  const kept = uniqueName('Kept doc')
  const deletedAlone = uniqueName('Deleted doc')
  const documentsSearch = page.getByRole('searchbox', { name: 'Search documents' })
  await logIn(page, DOCS_ADMIN)

  // A project with two documents, one of them then deleted on its own.
  await createProject(page, project, 'Private')
  await expect(page.getByRole('heading', { level: 1, name: project })).toBeVisible()
  await createDocument(page, kept)
  await openProject(page, project)
  await createDocument(page, deletedAlone)
  await page.getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Delete document' }).click()
  await expect(page.getByText(`Moved "${deletedAlone}" to your trash.`)).toBeVisible()

  // Deleting the project takes its remaining document with it.
  await openProject(page, project)
  await page.getByRole('button', { name: 'Delete' }).click()
  const confirm = page.getByRole('alertdialog')
  await expect(confirm.getByText(/along with every document filed under it/)).toBeVisible()
  await confirm.getByRole('button', { name: 'Delete project' }).click()
  await page.goto('/documents')
  await documentsSearch.fill(kept)
  await expect(page.getByRole('heading', { name: 'No matches' })).toBeVisible()

  // A document can't come back on its own while its project is in the trash.
  await page.goto('/documents/trash')
  await page.getByRole('button', { name: `Restore ${deletedAlone}` }).click()
  await expect(page.getByText(/restore the project first/)).toBeVisible()

  // Restoring the project brings its document back...
  await page.goto('/projects/trash')
  await page.getByRole('button', { name: `Restore ${project}` }).click()
  await expect(page.getByText(`Restored "${project}".`)).toBeVisible()
  await openDocument(page, kept)

  // ...and now the separately deleted one can be restored too.
  await page.goto('/documents/trash')
  await page.getByRole('button', { name: `Restore ${deletedAlone}` }).click()
  await expect(page.getByText(`Restored "${deletedAlone}".`)).toBeVisible()
  await openDocument(page, deletedAlone)
})

test('two people editing at once: the later save is refused, then kept on request', async ({
  page,
  browser,
}) => {
  await logIn(page, DOCS_ADMIN)
  await openDocument(page, 'Meeting notes')
  // Typing first: from then on the editor sticks to the revision it opened.
  await page.getByLabel('Content').fill("Admin's agenda.")

  const writer = await logInElsewhere(browser, DOCS_WRITER)
  await openDocument(writer, 'Meeting notes')
  await writer.getByLabel('Content').fill("Writer's agenda.")
  await writer.getByRole('button', { name: 'Save' }).click()
  await expect(writer.getByText('Document saved.')).toBeVisible()

  await page.getByRole('button', { name: 'Save' }).click()
  const conflict = page.getByRole('alert').filter({ hasText: 'Someone else saved this document' })
  await expect(conflict).toBeVisible()
  await expect(page.getByLabel('Content')).toHaveValue("Admin's agenda.")

  await conflict.getByRole('button', { name: 'Overwrite with mine' }).click()
  await expect(page.getByText('Document saved.')).toBeVisible()
  await expect(conflict).toHaveCount(0)

  await writer.reload()
  await expect(writer.getByLabel('Content')).toHaveValue("Admin's agenda.")
  await writer.context().close()
})

test('search finds documents by what they say, but only ones the reader can open', async ({
  page,
  browser,
}) => {
  await logIn(page, DOCS_READER)
  await page.goto('/documents')
  const search = page.getByRole('searchbox', { name: 'Search documents' })

  // "aboard" is only in the public team guide's text, not its title.
  await search.fill('aboard')
  const guide = page.getByRole('row').filter({ hasText: 'Team guide' })
  await expect(guide.locator('mark')).toHaveText('aboard')
  await expect(guide).toContainText('Welcome aboard.')

  // The brief says "eyes only", but it's shared with someone else.
  await search.fill('eyes only')
  await expect(page.getByRole('heading', { name: 'No matches' })).toBeVisible()

  // The person it's shared with finds it; each search word is marked.
  const stranger = await logInElsewhere(browser, DOCS_STRANGER)
  await stranger.goto('/documents?search=eyes%20only')
  await expect(
    stranger.getByRole('row').filter({ hasText: 'Shared brief' }).locator('mark'),
  ).toHaveText(['eyes', 'only'])
  await stranger.context().close()
})
