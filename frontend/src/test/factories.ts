import type {
  AccessRequest,
  CurrentUser,
  Document,
  Grant,
  Invitation,
  Organization,
  OrganizationSummary,
  Price,
  Project,
  SoleOwnership,
  TokenPair,
  UserDetail,
} from '@/api/types'

export function buildOrganizationSummary(
  overrides: Partial<OrganizationSummary> = {},
): OrganizationSummary {
  return {
    id: 1,
    name: 'Acme',
    has_active_subscription: true,
    payment_failed: false,
    ...overrides,
  }
}

export function buildCurrentUser(overrides: Partial<CurrentUser> = {}): CurrentUser {
  return {
    id: 1,
    email: 'ada@example.com',
    org_role: 'MEMBER',
    organization: buildOrganizationSummary(),
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
    revision: 1,
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

export function buildUserDetail(overrides: Partial<UserDetail> = {}): UserDetail {
  return {
    id: 2,
    email: 'grace@example.com',
    org_role: 'MEMBER',
    created: '2026-08-01T09:00:00Z',
    ...overrides,
  }
}

/** Owns nothing alone, by default - no warning when deactivating. */
export function buildSoleOwnership(overrides: Partial<SoleOwnership> = {}): SoleOwnership {
  return { projects: 0, documents: 0, ...overrides }
}

export function buildInvitation(overrides: Partial<Invitation> = {}): Invitation {
  return {
    id: 41,
    email: 'newcomer@example.com',
    organization: 1,
    invited_by: 1,
    invited_by_email: 'ada@example.com',
    status: 'PENDING',
    created: '2026-09-25T09:00:00Z',
    sent_at: '2026-09-25T09:00:00Z',
    accepted_at: null,
    ...overrides,
  }
}

export function buildOrganization(overrides: Partial<Organization> = {}): Organization {
  return {
    id: 1,
    name: 'Acme',
    billing_email: 'billing@acme.test',
    active_subscription: {
      id: 'sub_1',
      status: 'active',
      interval: 'year',
      current_period_end: '2027-03-01T12:00:00Z',
      cancel_at_period_end: false,
    },
    created: '2026-01-01T00:00:00Z',
    modified: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

export function buildPrice(overrides: Partial<Price> = {}): Price {
  return {
    id: 'price_monthly',
    nickname: 'Monthly',
    product_name: 'DocSphere',
    unit_amount: 1500,
    currency: 'usd',
    interval: 'month',
    ...overrides,
  }
}
