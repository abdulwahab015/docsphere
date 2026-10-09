import type {
  AccessRequest,
  Attachment,
  AuditEvent,
  CurrentUser,
  Document,
  DocumentListItem,
  DocumentVersionDetail,
  Grant,
  Invitation,
  Notification,
  Organization,
  OrganizationSummary,
  Price,
  Project,
  RosterUser,
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
    email_verified: true,
    name: '',
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
    created_by_name: '',
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
    created_by_name: '',
    organization: 1,
    project: null,
    created: '2026-09-01T09:00:00Z',
    modified: '2026-09-15T09:00:00Z',
    ...overrides,
  }
}

export function buildDocumentListItem(overrides: Partial<DocumentListItem> = {}): DocumentListItem {
  const { content: _content, ...listed } = buildDocument()
  return { ...listed, excerpt: null, ...overrides }
}

export function buildDocumentVersion(
  overrides: Partial<DocumentVersionDetail> = {},
): DocumentVersionDetail {
  return {
    revision: 1,
    title: 'Findings',
    content: 'First draft.',
    created_by: 1,
    created_by_email: 'ada@example.com',
    created_by_name: '',
    created: '2026-09-01T09:00:00Z',
    ...overrides,
  }
}

export function buildAttachment(overrides: Partial<Attachment> = {}): Attachment {
  return {
    id: 31,
    name: 'Q3 report.pdf',
    content_type: 'application/pdf',
    size: 2_400_000,
    uploaded_by: 1,
    uploaded_by_email: 'ada@example.com',
    uploaded_by_name: 'Ada Lovelace',
    created: '2026-09-02T09:00:00Z',
    ...overrides,
  }
}

export function buildAuditEvent(overrides: Partial<AuditEvent> = {}): AuditEvent {
  return {
    id: 41,
    created: '2026-09-03T10:00:00Z',
    verb: 'ACCESS_GRANTED',
    actor_email: 'ada@example.com',
    actor_name: 'Ada Lovelace',
    target_user_email: 'grace@example.com',
    target_user_name: 'Grace Hopper',
    resource_kind: 'DOCUMENT',
    resource_name: 'Q3 plan',
    details: { access_level: 'EDITOR' },
    ...overrides,
  }
}

export function buildNotification(overrides: Partial<Notification> = {}): Notification {
  return {
    id: 51,
    created: '2026-09-04T10:00:00Z',
    verb: 'ACCESS_GRANTED',
    read: false,
    actor_email: 'grace@example.com',
    actor_name: 'Grace Hopper',
    resource_kind: 'DOCUMENT',
    resource_id: 11,
    resource_name: 'Q3 plan',
    details: { access_level: 'EDITOR' },
    ...overrides,
  }
}

export function buildGrant(overrides: Partial<Grant> = {}): Grant {
  return {
    id: 21,
    project: 7,
    user: 1,
    user_email: 'ada@example.com',
    user_name: '',
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
    requested_by_name: '',
    reviewed_by: null,
    reviewed_by_email: null,
    reviewed_by_name: null,
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
    name: '',
    org_role: 'MEMBER',
    created: '2026-08-01T09:00:00Z',
    ...overrides,
  }
}

/** A roster entry as a member sees it: no role or join date. */
export function buildRosterUser(overrides: Partial<RosterUser> = {}): RosterUser {
  return { id: 2, email: 'grace@example.com', name: '', ...overrides }
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
    invited_by_name: '',
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
