import type { CurrentUser, Project, TokenPair } from '@/api/types'

export function buildCurrentUser(overrides: Partial<CurrentUser> = {}): CurrentUser {
  return {
    id: 1,
    email: 'ada@example.com',
    org_role: 'MEMBER',
    organization: { id: 1, name: 'Acme', has_active_subscription: true },
    ...overrides,
  }
}

export function buildTokenPair(overrides: Partial<TokenPair> = {}): TokenPair {
  return { access: 'new-access-token', refresh: 'new-refresh-token', ...overrides }
}

export function buildProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 7,
    name: 'Roadmap',
    description: 'Where we are headed.',
    visibility: 'PRIVATE',
    access_level: 'OWNER',
    created_by: 1,
    created_by_email: 'ada@example.com',
    organization: 1,
    created: '2026-09-01T09:00:00Z',
    modified: '2026-09-15T09:00:00Z',
    ...overrides,
  }
}
