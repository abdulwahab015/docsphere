import { createHmac } from 'node:crypto'
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { type Browser, expect, type Page } from '@playwright/test'

interface SeedFile {
  password: string
  organizations: {
    name: string
    users: { email: string; role: 'ADMIN' | 'MEMBER'; two_factor_secret?: string }[]
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
  /** The key in their authenticator app, when they sign in with two-factor. */
  twoFactorSecret?: string
}

function seededAccount(email: string): Account {
  for (const organization of seed.organizations) {
    const user = organization.users.find((candidate) => candidate.email === email)
    if (user) {
      return {
        email,
        password: seed.password,
        organization: organization.name,
        twoFactorSecret: user.two_factor_secret,
      }
    }
  }
  throw new Error(`e2e/seed.json has no user "${email}".`)
}

export const ACME_ADMIN = seededAccount('admin@acme.e2e.test')
export const ACME_MEMBER = seededAccount('member@acme.e2e.test')
export const SETTINGS_ADMIN = seededAccount('admin@settings.e2e.test')
export const LAPSED_ADMIN = seededAccount('admin@lapsed.e2e.test')
export const LAPSED_MEMBER = seededAccount('member@lapsed.e2e.test')
export const UNPAID_ADMIN = seededAccount('admin@unpaid.e2e.test')
export const PAID_ADMIN = seededAccount('admin@paid.e2e.test')
export const OVERDUE_ADMIN = seededAccount('admin@overdue.e2e.test')
export const OVERDUE_MEMBER = seededAccount('member@overdue.e2e.test')
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
export const ACCOUNT_MEMBER = seededAccount('member@account.e2e.test')
export const ACCOUNT_MOVER = seededAccount('mover@account.e2e.test')
export const NAMES_ADMIN = seededAccount('admin@names.e2e.test')
export const NAMES_MEMBER = seededAccount('member@names.e2e.test')
export const ACTIVITY_ADMIN = seededAccount('admin@activity.e2e.test')
export const NOTIFY_OWNER = seededAccount('owner@notify.e2e.test')
export const NOTIFY_MEMBER = seededAccount('member@notify.e2e.test')
export const LEAVING_ADMIN = seededAccount('admin@leaving.e2e.test')
export const LEAVING_MEMBER = seededAccount('member@leaving.e2e.test')
export const CLOSING_ADMIN = seededAccount('admin@closing.e2e.test')
export const CLOSING_MEMBER = seededAccount('member@closing.e2e.test')
export const EXPORT_ADMIN = seededAccount('admin@export.e2e.test')
export const DELETED_ADMIN = seededAccount('admin@deleted.e2e.test')
// Signed up, but hasn't followed the verification link yet.
export const VERIFY_ADMIN = seededAccount('admin@verify.e2e.test')
// Two-factor sign-in: on for the admin and two members, off for `setup`.
export const TWO_FACTOR_ADMIN = seededAccount('admin@twofactor.e2e.test')
export const TWO_FACTOR_PHONE = seededAccount('phone@twofactor.e2e.test')
export const TWO_FACTOR_SETUP = seededAccount('setup@twofactor.e2e.test')
export const TWO_FACTOR_CODES = seededAccount('codes@twofactor.e2e.test')
// An organization whose admin starts requiring two-factor sign-in...
export const REQUIRED_ADMIN = seededAccount('admin@required.e2e.test')
export const REQUIRED_MEMBER = seededAccount('member@required.e2e.test')
// ...and one that already does, with a member who hasn't set it up.
export const HELD_ADMIN = seededAccount('admin@held.e2e.test')
export const HELD_MEMBER = seededAccount('member@held.e2e.test')

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

const BASE32_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
const TOTP_STEP_SECONDS = 30
const TOTP_DIGITS = 6

function base32Bytes(text: string) {
  const bits = [...text]
    .map((character) => BASE32_ALPHABET.indexOf(character).toString(2).padStart(5, '0'))
    .join('')
  return Buffer.from((bits.match(/.{8}/g) ?? []).map((byte) => parseInt(byte, 2)))
}

/**
 * The code an authenticator app holding `secret` shows (RFC 6238: SHA-1, 30
 * second steps, 6 digits) - or the one it will show `stepsAhead` steps from
 * now, which the API also accepts. Each code works only once, so a retried
 * test passes its retry count to get one not used yet.
 */
export function appCode(secret: string, stepsAhead = 0) {
  const step = Math.floor(Date.now() / 1000 / TOTP_STEP_SECONDS) + stepsAhead
  const counter = Buffer.alloc(8)
  counter.writeBigUInt64BE(BigInt(step))
  const digest = createHmac('sha1', base32Bytes(secret)).update(counter).digest()
  const offset = digest[digest.length - 1] & 0xf
  const code = (digest.readUInt32BE(offset) & 0x7fffffff) % 10 ** TOTP_DIGITS
  return code.toString().padStart(TOTP_DIGITS, '0')
}

function twoFactorSecretOf(account: Account) {
  if (!account.twoFactorSecret) {
    throw new Error(`${account.email} doesn't sign in with two-factor in e2e/seed.json.`)
  }
  return account.twoFactorSecret
}

/** Signs in an account with two-factor sign-in on: password, then a code
 * from its app (`stepsAhead` as in `appCode`). */
export async function logInWithCode(page: Page, account: Account, stepsAhead = 0) {
  await page.goto('/login')
  await fillLoginForm(page, account)
  await page.getByLabel('Code from your app').fill(appCode(twoFactorSecretOf(account), stepsAhead))
  await page.getByRole('button', { name: 'Verify' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible()
}

/** A second browser session, with its own cookies, signed in as `account` -
 * for flows where two people take turns. Close it with `page.context().close()`. */
export async function logInElsewhere(browser: Browser, account: Account) {
  const page = await (await browser.newContext()).newPage()
  await logIn(page, account)
  return page
}

export async function openAccountSettings(page: Page) {
  await page.getByRole('button', { name: 'Account menu' }).click()
  await page.getByRole('menuitem', { name: 'Account settings' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Account' })).toBeVisible()
  // The menu is still closing: a click on its button now would be lost.
  await expect(page.getByRole('menu')).toHaveCount(0)
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

/** The latest email sent to `recipient`, once one has arrived. */
export async function latestEmailTo(recipient: string) {
  let message = ''
  await expect
    .poll(() => {
      message = emailsTo(recipient).at(-1) ?? ''
      return message
    })
    .not.toBe('')
  return message
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

/**
 * Answers one of the API's Stripe-backed endpoints (checkout, billing portal)
 * from the browser instead: the e2e API has no Stripe account to call. Only
 * these endpoints are stubbed - everything around them is the real API. Returns
 * the JSON bodies the app sent, for the test to check.
 */
export async function stubStripeEndpoint(page: Page, path: string, response: object) {
  const sentBodies: unknown[] = []
  await page.route(`**/api/v1${path}`, async (route) => {
    const corsHeaders = {
      'Access-Control-Allow-Origin': new URL(page.url()).origin,
      'Access-Control-Allow-Credentials': 'true',
      'Access-Control-Allow-Headers': 'authorization, content-type',
    }
    if (route.request().method() === 'OPTIONS') {
      await route.fulfill({ status: 204, headers: corsHeaders })
      return
    }
    sentBodies.push(route.request().postDataJSON())
    await route.fulfill({ json: response, headers: corsHeaders })
  })
  return sentBodies
}
