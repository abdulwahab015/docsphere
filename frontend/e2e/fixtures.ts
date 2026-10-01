import { readFileSync } from 'node:fs'

import { expect, type Page } from '@playwright/test'

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
