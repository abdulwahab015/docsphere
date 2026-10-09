import { AxeBuilder } from '@axe-core/playwright'
import { expect, type Page, test } from '@playwright/test'

import {
  DOCS_ADMIN,
  DOCS_READER,
  fillLoginForm,
  LAPSED_ADMIN,
  LAPSED_MEMBER,
  logIn,
  openDocument,
  openProject,
  OVERDUE_ADMIN,
  VERIFY_ADMIN,
} from './fixtures'

// WCAG 2.1 A and AA, plus axe's best practices (landmarks, one main, ...).
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice']
const DESKTOP = { width: 1280, height: 800 }
const PHONE = { width: 375, height: 812 }

/**
 * Checks the page as it stands, at each width: no axe violations, and nothing
 * wider than the screen (a phone must never scroll sideways). A dialog or menu
 * is checked once its opening animation has finished, so contrast is measured
 * on the final colours.
 */
async function expectAccessible(
  page: Page,
  { viewports = [DESKTOP, PHONE], skipRules = [] as string[] } = {},
) {
  for (const viewport of viewports) {
    await page.setViewportSize(viewport)
    await page.waitForLoadState('networkidle')
    await page.waitForFunction(() =>
      document.getAnimations().every((animation) => animation.playState !== 'running'),
    )

    const { violations } = await new AxeBuilder({ page })
      .withTags(AXE_TAGS)
      .disableRules(skipRules)
      .analyze()
    const found = violations.map(
      (violation) =>
        `${violation.id} (${violation.impact}): ${violation.nodes
          .map((node) => node.target.join(' '))
          .join(', ')}`,
    )
    expect(found, `axe violations at ${viewport.width}px`).toEqual([])

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    )
    expect(overflow, `sideways scroll at ${viewport.width}px`).toBe(0)
  }
  await page.setViewportSize(DESKTOP)
}

async function visit(page: Page, path: string) {
  await page.goto(path)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
}

test('the signed-out pages', async ({ page }) => {
  for (const path of [
    '/login',
    '/signup',
    '/forgot-password',
    '/reset-password',
    '/accept-invite?token=unchecked-until-submitted',
    '/verify-email',
    '/confirm-email?token=unchecked-until-submitted',
  ]) {
    await visit(page, path)
    await expectAccessible(page)
  }
})

// A test per page: each check takes a few seconds, so together they'd outrun
// one test's time limit, and a failure names the page.
test.describe("the app's pages", () => {
  for (const path of [
    '/projects',
    '/projects/trash',
    '/documents',
    '/documents/trash',
    '/requests',
    '/requests?tab=sent',
    '/people',
    '/people?tab=invitations',
    '/people?tab=deactivated',
    '/settings/organization',
    '/settings/account',
    '/billing',
    '/no-such-page',
  ]) {
    test(path, async ({ page }) => {
      await logIn(page, DOCS_ADMIN)
      await visit(page, path)
      await expectAccessible(page)
    })
  }
})

test('document search results, showing where each matched', async ({ page }) => {
  await logIn(page, DOCS_ADMIN)
  await visit(page, '/documents?search=aboard')
  await expect(page.locator('mark').filter({ hasText: 'aboard' })).toBeVisible()
  await expectAccessible(page)
})

test('project and document pages, and their dialogs', async ({ page }) => {
  await logIn(page, DOCS_ADMIN)
  await openProject(page, 'Research')
  await expectAccessible(page)

  await openDocument(page, 'Findings')
  await expectAccessible(page)
  // Findings has a seeded attachment, so its row and buttons are checked too.
  await expect(page.getByRole('list', { name: 'Attachments' })).toContainText('results.pdf')
  await page.getByRole('button', { name: 'Share' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expectAccessible(page)
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'History' }).click()
  const history = page.getByRole('dialog', { name: 'Version history' })
  await expect(history.getByRole('list', { name: 'Versions' })).toBeVisible()
  await expectAccessible(page)
  await history.getByRole('button', { name: /^Version 1/ }).click()
  await expect(page.getByRole('article', { name: 'Version 1' })).toBeVisible()
  await expectAccessible(page)
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'Delete', exact: true }).click()
  await expect(page.getByRole('alertdialog')).toBeVisible()
  await expectAccessible(page)
})

test('a read-only document, and the menus and dialogs of the shell', async ({ page }) => {
  await logIn(page, DOCS_READER)
  await openDocument(page, 'Findings')
  await expectAccessible(page)

  // The account menu sits in the sidebar, which is a drawer on a phone. Like
  // every popup it renders at the end of the page, outside the landmarks -
  // reached by focus, which moves into it - so "region" doesn't apply to it.
  await page.getByRole('button', { name: 'Account menu' }).click()
  await expect(page.getByRole('menu')).toBeVisible()
  await expectAccessible(page, { viewports: [DESKTOP], skipRules: ['region'] })
  await page.keyboard.press('Escape')

  await page.setViewportSize(PHONE)
  await page.getByRole('button', { name: 'Toggle navigation' }).click()
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible()
  await expectAccessible(page, { viewports: [PHONE] })
})

test('the dialogs an admin opens from People', async ({ page }) => {
  await logIn(page, DOCS_ADMIN)
  await visit(page, '/people')
  await page.getByRole('button', { name: 'Invite', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expectAccessible(page)
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'Upload a list' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expectAccessible(page)
})

test('the warning an admin sees after a failed payment', async ({ page }) => {
  await logIn(page, OVERDUE_ADMIN)
  await visit(page, '/billing')
  await expect(page.getByText('Your last payment failed')).toBeVisible()
  await expectAccessible(page)
})

test("a lapsed organization's screens", async ({ page, browser }) => {
  await page.goto('/login')
  await fillLoginForm(page, LAPSED_ADMIN)
  await expect(page.getByRole('heading', { name: 'Subscribe to continue' })).toBeVisible()
  await expectAccessible(page)

  const memberPage = await (await browser.newContext()).newPage()
  await memberPage.goto('/login')
  await fillLoginForm(memberPage, LAPSED_MEMBER)
  await expect(memberPage.getByRole('heading', { name: 'Subscription inactive' })).toBeVisible()
  await expectAccessible(memberPage)
  await memberPage.context().close()
})

test('the screen a new signup sees until they verify their email', async ({ page }) => {
  await page.goto('/login')
  await fillLoginForm(page, VERIFY_ADMIN)
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible()
  await expectAccessible(page)
})
