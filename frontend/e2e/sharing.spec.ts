import { expect, type Page, test } from '@playwright/test'

import {
  logIn,
  logInElsewhere,
  openDocument,
  openProject,
  SHARING_ALEX,
  SHARING_BLAIR,
  SHARING_CASEY,
  SHARING_OWNER,
} from './fixtures'

type Level = 'Viewer' | 'Editor' | 'Owner'
const LEVEL_VALUES: Record<Level, string> = { Viewer: 'VIEWER', Editor: 'EDITOR', Owner: 'OWNER' }

async function openShareDialog(page: Page) {
  await page.getByRole('button', { name: 'Share' }).click()
  return page.getByRole('dialog', { name: /^Share/ })
}

/** Adds someone from the share dialog's people search. */
async function shareWith(page: Page, email: string, level: Level) {
  const dialog = await openShareDialog(page)
  await dialog.getByLabel('Add as').selectOption(LEVEL_VALUES[level])
  await dialog.getByLabel('Search people by name or email').fill(email)
  await dialog.getByRole('button', { name: `Add ${email}` }).click()
  await expect(page.getByText(`${email} now has ${level} access.`)).toBeVisible()
  await expect(
    dialog.getByRole('list', { name: 'People with access' }).getByText(email),
  ).toBeVisible()
  return dialog
}

async function requestEditAccess(page: Page, title: string) {
  await openDocument(page, title)
  await page.getByRole('button', { name: 'Request edit access' }).click()
  await expect(page.getByText(/^Request sent/)).toBeVisible()
  await expect(page.getByText(/Waiting for an owner to answer/)).toBeVisible()
}

async function openIncomingRequest(page: Page, title: string) {
  await page
    .getByRole('navigation', { name: 'Main' })
    .getByRole('link', { name: 'Requests' })
    .click()
  await expect(page.getByRole('heading', { level: 1, name: 'Access requests' })).toBeVisible()
  return page.getByRole('row', { name: new RegExp(title) })
}

test.describe('sharing', () => {
  test("an Owner shares a project, which doesn't share its documents", async ({
    page,
    browser,
  }) => {
    await logIn(page, SHARING_OWNER)
    await openProject(page, 'Atlas')

    const dialog = await shareWith(page, SHARING_ALEX.email, 'Viewer')
    await expect(dialog.getByText(/Sharing it doesn't share its documents/)).toBeVisible()

    const alex = await logInElsewhere(browser, SHARING_ALEX)
    await openProject(alex, 'Atlas')
    await expect(alex.getByText('Viewer', { exact: true })).toBeVisible()
    await expect(alex.getByRole('button', { name: 'Edit' })).toHaveCount(0)
    await expect(alex.getByRole('button', { name: 'Share' })).toHaveCount(0)
    await alex.context().close()
  })

  test('an Owner shares a document, changes the level, then removes access', async ({
    page,
    browser,
  }) => {
    await logIn(page, SHARING_OWNER)
    await openDocument(page, 'Plan')
    const dialog = await shareWith(page, SHARING_ALEX.email, 'Editor')

    const alex = await logInElsewhere(browser, SHARING_ALEX)
    await openDocument(alex, 'Plan')
    await expect(alex.getByLabel('Content')).toBeEditable()

    await dialog
      .getByLabel(`Access level for ${SHARING_ALEX.email}`)
      .selectOption(LEVEL_VALUES.Viewer)
    await expect(page.getByText(`${SHARING_ALEX.email} now has Viewer access.`)).toBeVisible()
    await alex.reload()
    await expect(alex.getByText('Shared, re-levelled, then revoked.')).toBeVisible()
    await expect(alex.getByLabel('Content')).toHaveCount(0)

    await dialog.getByRole('button', { name: `Remove ${SHARING_ALEX.email}` }).click()
    const confirm = page.getByRole('alertdialog', { name: `Remove ${SHARING_ALEX.email}?` })
    await expect(
      confirm.getByText("They'll no longer be able to open this document."),
    ).toBeVisible()
    await confirm.getByRole('button', { name: 'Remove' }).click()
    await expect(page.getByText(`Removed ${SHARING_ALEX.email}.`)).toBeVisible()
    await alex.reload()
    await expect(alex.getByRole('heading', { name: 'Not found' })).toBeVisible()
    await alex.context().close()
  })

  test("the last Owner can't lower or remove their own access", async ({ page }) => {
    await logIn(page, SHARING_OWNER)
    await openDocument(page, 'Solo')
    const dialog = await openShareDialog(page)
    const ownLevel = dialog.getByLabel(`Access level for ${SHARING_OWNER.email}`)

    await ownLevel.selectOption(LEVEL_VALUES.Editor)
    await page.getByRole('button', { name: 'Change my access' }).click()
    await expect(page.getByText("Cannot downgrade the document's last Owner.")).toBeVisible()
    await expect(ownLevel).toHaveValue(LEVEL_VALUES.Owner)

    await dialog.getByRole('button', { name: `Remove ${SHARING_OWNER.email}` }).click()
    await page.getByRole('button', { name: 'Remove' }).click()
    await expect(page.getByText(/Cannot revoke the document's last Owner/)).toBeVisible()
    await expect(ownLevel).toHaveValue(LEVEL_VALUES.Owner)
  })
})

test.describe('requesting edit access', () => {
  test('a Viewer asks, an Owner approves, and the Viewer can edit', async ({ page, browser }) => {
    await logIn(page, SHARING_BLAIR)
    await requestEditAccess(page, 'Policy')

    const owner = await logInElsewhere(browser, SHARING_OWNER)
    const request = await openIncomingRequest(owner, 'Policy')
    await expect(request.getByText(SHARING_BLAIR.email)).toBeVisible()
    await request.getByRole('button', { name: 'Approve' }).click()
    await expect(owner.getByText(`${SHARING_BLAIR.email} can now edit "Policy".`)).toBeVisible()
    await expect(request).toHaveCount(0)
    await owner.context().close()

    await page.reload()
    await expect(page.getByLabel('Content')).toBeEditable()
    await page.goto('/requests?tab=sent')
    const sent = page.getByRole('row', { name: /Policy/ })
    await expect(sent.getByText('Approved')).toBeVisible()
    await expect(sent.getByText(SHARING_OWNER.email)).toBeVisible()
  })

  test('a Viewer asks, an Owner denies, and the Viewer may ask again', async ({
    page,
    browser,
  }) => {
    await logIn(page, SHARING_CASEY)
    await requestEditAccess(page, 'Notice')

    const owner = await logInElsewhere(browser, SHARING_OWNER)
    const request = await openIncomingRequest(owner, 'Notice')
    await request.getByRole('button', { name: 'Deny' }).click()
    await expect(
      owner.getByText(`Denied ${SHARING_CASEY.email}'s request for "Notice".`),
    ).toBeVisible()
    await owner.context().close()

    await page.reload()
    await expect(page.getByText(/^Your last request was denied on/)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Request edit access' })).toBeVisible()
    await page.goto('/requests?tab=sent')
    await expect(page.getByRole('row', { name: /Notice/ }).getByText('Denied')).toBeVisible()
  })
})
