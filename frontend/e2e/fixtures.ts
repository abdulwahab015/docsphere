import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { type Browser, expect, type Page } from '@playwright/test'

interface SeedFile {
  password: string
  organizations: {
    name: string
    users: { email: string; role: 'ADMIN' | 'MEMBER' }[]
    extra_members?: number
    projects?: { name: string }[]
    documents?: { title: string }[]
  }[]
}

// The same file the backend's `seed_e2e` command loads, so the accounts used
// here always exist in the test database.
const seed: SeedFile = JSON.parse(readFileSync(new URL('./seed.json', import.meta.url), 'utf-8'))

export interface Account {
  email: string
  password: string
  organization: string
}

function seededAccount(email: string): Account {
  const organization = seed.organizations.find((candidate) =>
    candidate.users.some((user) => user.email === email),
  )
  if (!organization) {
    throw new Error(`e2e/seed.json has no user "${email}".`)
  }
  return { email, password: seed.password, organization: organization.name }
}

export const ACME_ADMIN = seededAccount('admin@acme.e2e.test')
export const ACME_MEMBER = seededAccount('member@acme.e2e.test')
export const SETTINGS_ADMIN = seededAccount('admin@settings.e2e.test')
export const LAPSED_ADMIN = seededAccount('admin@lapsed.e2e.test')
export const PROJECTS_ADMIN = seededAccount('admin@projects.e2e.test')
export const PROJECTS_EDITOR = seededAccount('editor@projects.e2e.test')
export const PROJECTS_VIEWER = seededAccount('viewer@projects.e2e.test')
export const PROJECTS_OUTSIDER = seededAccount('outsider@projects.e2e.test')
export const DOCS_ADMIN = seededAccount('admin@docs.e2e.test')
export const DOCS_WRITER = seededAccount('writer@docs.e2e.test')
export const DOCS_READER = seededAccount('reader@docs.e2e.test')
export const DOCS_STRANGER = seededAccount('stranger@docs.e2e.test')
export const SHARING_OWNER = seededAccount('owner@sharing.e2e.test')
export const SHARING_ALEX = seededAccount('alex@sharing.e2e.test')
export const SHARING_BLAIR = seededAccount('blair@sharing.e2e.test')
export const SHARING_CASEY = seededAccount('casey@sharing.e2e.test')
export const TEAM_ADMIN = seededAccount('admin@team.e2e.test')
export const TEAM_PROMOTE = seededAccount('promote@team.e2e.test')
export const TEAM_LEAVER = seededAccount('leaver@team.e2e.test')
export const TEAM_FORGETFUL = seededAccount('forgetful@team.e2e.test')

export function memberCount(organizationName: string) {
  const organization = seed.organizations.find((candidate) => candidate.name === organizationName)
  return (organization?.users.length ?? 0) + (organization?.extra_members ?? 0)
}

export async function fillLoginForm(page: Page, account: Account) {
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password', { exact: true }).fill(account.password)
  await page.getByRole('button', { name: 'Log in' }).click()
}

/** Signs in through the real login page and waits for the app to open. */
export async function logIn(page: Page, account: Account) {
  await page.goto('/login')
  await fillLoginForm(page, account)
  await expect(page.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible()
}

/** A second browser session, with its own cookies, signed in as `account` -
 * for flows where two people take turns. Close it with `page.context().close()`. */
export async function logInElsewhere(browser: Browser, account: Account) {
  const page = await (await browser.newContext()).newPage()
  await logIn(page, account)
  return page
}

export async function logOut(page: Page) {
  await page.getByRole('button', { name: 'Account menu' }).click()
  await page.getByRole('menuitem', { name: 'Log out' }).click()
  await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible()
}

/** A name no seeded project or earlier run uses, for tests that create one. */
export function uniqueName(prefix: string) {
  return `${prefix} ${Date.now()}`
}

export async function openProject(page: Page, name: string) {
  await page.goto('/projects')
  await page.getByRole('link', { name, exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
}

export async function openDocument(page: Page, title: string) {
  await page.goto('/documents')
  await page.getByRole('link', { name: title, exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
}

/** Creates a project through the New project dialog (admins only). */
export async function createProject(page: Page, name: string, visibility: 'Private' | 'Public') {
  await page.goto('/projects')
  await page.getByRole('button', { name: 'New project' }).click()
  const dialog = page.getByRole('dialog', { name: 'New project' })
  await dialog.getByLabel('Name').fill(name)
  await dialog.getByLabel('Description (optional)').fill('Created by an end-to-end test.')
  await dialog.getByRole('radio', { name: visibility }).check()
  await dialog.getByRole('button', { name: 'Create project' }).click()
}

/** Creates a document through the open page's New document dialog. */
export async function createDocument(page: Page, title: string) {
  await page.getByRole('button', { name: 'New document' }).click()
  const dialog = page.getByRole('dialog', { name: 'New document' })
  await dialog.getByLabel('Title').fill(title)
  await dialog.getByRole('button', { name: 'Create document' }).click()
  await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
}

// Where the e2e API writes every email it sends, one file each (`make e2e-api`
// uses Django's file-based email backend).
const MAILBOX = fileURLToPath(new URL('../node_modules/.tmp/e2e-mail/', import.meta.url))
const MESSAGE_SEPARATOR = '-'.repeat(79)

function emailsTo(recipient: string) {
  if (!existsSync(MAILBOX)) {
    return []
  }
  const files = readdirSync(MAILBOX)
    .map((name) => join(MAILBOX, name))
    .sort((first, second) => statSync(first).mtimeMs - statSync(second).mtimeMs)
  return files
    .flatMap((file) => readFileSync(file, 'utf-8').split(MESSAGE_SEPARATOR))
    .filter((message) => message.includes(`To: ${recipient}`))
    .map(decodeQuotedPrintable)
}

/** Undoes the quoted-printable encoding Django gives a long plain-text body,
 * as a mail client would: joins soft-wrapped lines (`=` at a line end) and
 * turns `=3D`-style escapes back into characters. Links are ASCII, so
 * single-byte decoding is enough. */
function decodeQuotedPrintable(message: string) {
  if (!message.includes('Content-Transfer-Encoding: quoted-printable')) {
    return message
  }
  return message
    .replace(/=\r?\n/g, '')
    .replace(/=([0-9A-F]{2})/g, (_escape, hex: string) => String.fromCharCode(parseInt(hex, 16)))
}

function escapeRegExp(text: string) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** The link to `path` (e.g. `/accept-invite`) in the latest email sent to
 * `recipient`, as the person would click it. */
export async function emailedLink(recipient: string, path: string) {
  const linkPattern = new RegExp(`https?://\\S+${escapeRegExp(path)}\\?\\S+`)
  let link = ''
  await expect
    .poll(() => {
      link = emailsTo(recipient).at(-1)?.match(linkPattern)?.[0] ?? ''
      return link
    })
    .not.toBe('')
  return link
}
