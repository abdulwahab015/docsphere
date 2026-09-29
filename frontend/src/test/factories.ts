import type { CurrentUser, TokenPair } from '@/api/types'

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
