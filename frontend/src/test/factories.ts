import type { AccessRequest, CurrentUser, Document, Grant, Project, TokenPair } from '@/api/types'

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

export function buildDocument(overrides: Partial<Document> = {}): Document {
  return {
    id: 11,
    title: 'Findings',
    content: 'First draft.',
    visibility: 'PRIVATE',
    access_level: 'OWNER',
    created_by: 1,
    created_by_email: 'ada@example.com',
    organization: 1,
    project: null,
    created: '2026-09-01T09:00:00Z',
    modified: '2026-09-15T09:00:00Z',
    ...overrides,
  }
}

export function buildGrant(overrides: Partial<Grant> = {}): Grant {
  return {
    id: 21,
    project: 7,
    user: 1,
    user_email: 'ada@example.com',
    access_level: 'OWNER',
    ...overrides,
  }
}

export function buildAccessRequest(overrides: Partial<AccessRequest> = {}): AccessRequest {
  return {
    id: 31,
    document: 11,
    document_title: 'Findings',
    requested_by: 2,
    requested_by_email: 'grace@example.com',
    reviewed_by: null,
    reviewed_by_email: null,
    status: 'PENDING',
    created: '2026-09-20T09:00:00Z',
    modified: '2026-09-20T09:00:00Z',
    ...overrides,
  }
}
