import { readFileSync } from 'node:fs'

import { expect, type Page } from '@playwright/test'

interface SeedFile {
  password: string
  organizations: {
    name: string
    users: { email: string; role: 'ADMIN' | 'MEMBER' }[]
    extra_members?: number
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

function seededAccount(organizationName: string, role: 'ADMIN' | 'MEMBER'): Account {
  const organization = seed.organizations.find((candidate) => candidate.name === organizationName)
  const user = organization?.users.find((candidate) => candidate.role === role)
  if (!organization || !user) {
    throw new Error(`e2e/seed.json has no ${role} in "${organizationName}".`)
  }
  return { email: user.email, password: seed.password, organization: organization.name }
}

export const ACME_ADMIN = seededAccount('Acme E2E', 'ADMIN')
export const ACME_MEMBER = seededAccount('Acme E2E', 'MEMBER')
export const SETTINGS_ADMIN = seededAccount('Settings E2E', 'ADMIN')
export const LAPSED_ADMIN = seededAccount('Lapsed E2E', 'ADMIN')

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
  await expect(page.getByRole('heading', { level: 1, name: 'Home' })).toBeVisible()
}

export async function logOut(page: Page) {
  await page.getByRole('button', { name: 'Account menu' }).click()
  await page.getByRole('menuitem', { name: 'Log out' }).click()
  await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible()
}
