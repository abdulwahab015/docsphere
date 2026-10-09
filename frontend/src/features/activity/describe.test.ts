import type { AuditEvent } from '@/api/types'
import { actorName, describeEvent } from '@/features/activity/describe'
import { buildAuditEvent } from '@/test/factories'

const PROJECT = { resource_kind: 'PROJECT', resource_name: 'Launch' } as const
const NO_RESOURCE = { resource_kind: null, resource_name: null } as const

describe('describeEvent', () => {
  it.each<[string, Partial<AuditEvent>]>([
    [
      'Gave Grace Hopper Editor access to the document "Q3 plan"',
      { verb: 'ACCESS_GRANTED', details: { access_level: 'EDITOR' } },
    ],
    [
      'Changed Grace Hopper\'s access to the project "Launch" from Viewer to Owner',
      {
        verb: 'ACCESS_CHANGED',
        ...PROJECT,
        details: { access_level: 'OWNER', previous_access_level: 'VIEWER' },
      },
    ],
    [
      'Removed Grace Hopper\'s Editor access to the document "Q3 plan"',
      { verb: 'ACCESS_REVOKED', details: { previous_access_level: 'EDITOR' } },
    ],
    [
      'Made the project "Launch" public',
      { verb: 'VISIBILITY_CHANGED', ...PROJECT, details: { visibility: 'PUBLIC' } },
    ],
    [
      'Approved Grace Hopper\'s request to edit the document "Q3 plan"',
      { verb: 'ACCESS_REQUEST_APPROVED', details: {} },
    ],
    [
      'Denied Grace Hopper\'s request to edit the document "Q3 plan"',
      { verb: 'ACCESS_REQUEST_DENIED', details: {} },
    ],
    [
      "Changed Grace Hopper's role from Member to Admin",
      {
        verb: 'ROLE_CHANGED',
        ...NO_RESOURCE,
        details: { role: 'ADMIN', previous_role: 'MEMBER' },
      },
    ],
    ['Deactivated Grace Hopper', { verb: 'MEMBER_DEACTIVATED', ...NO_RESOURCE, details: {} }],
    ['Reactivated Grace Hopper', { verb: 'MEMBER_REACTIVATED', ...NO_RESOURCE, details: {} }],
    [
      'Invited new@example.com',
      { verb: 'INVITATION_SENT', ...NO_RESOURCE, details: { email: 'new@example.com' } },
    ],
    [
      'Resent the invitation to new@example.com',
      { verb: 'INVITATION_RESENT', ...NO_RESOURCE, details: { email: 'new@example.com' } },
    ],
    [
      'Revoked the invitation to new@example.com',
      { verb: 'INVITATION_REVOKED', ...NO_RESOURCE, details: { email: 'new@example.com' } },
    ],
    [
      'Joined from an invitation',
      { verb: 'INVITATION_ACCEPTED', ...NO_RESOURCE, details: { email: 'ada@example.com' } },
    ],
    ['Deleted their account', { verb: 'ACCOUNT_DELETED', ...NO_RESOURCE, details: {} }],
    [
      "Asked for an export of the organization's data",
      { verb: 'EXPORT_REQUESTED', ...NO_RESOURCE, details: {} },
    ],
    [
      "Downloaded an export of the organization's data",
      { verb: 'EXPORT_DOWNLOADED', ...NO_RESOURCE, details: {} },
    ],
    ['Turned on two-factor sign-in', { verb: 'TWO_FACTOR_ENABLED', ...NO_RESOURCE, details: {} }],
    ['Turned off two-factor sign-in', { verb: 'TWO_FACTOR_DISABLED', ...NO_RESOURCE, details: {} }],
    [
      "Reset Grace Hopper's two-factor sign-in",
      { verb: 'TWO_FACTOR_RESET', ...NO_RESOURCE, details: {} },
    ],
    ['Moved the project "Launch" to the trash', { verb: 'DELETED', ...PROJECT, details: {} }],
    ['Restored the document "Q3 plan" from the trash', { verb: 'RESTORED', details: {} }],
    [
      'Attached "minutes.pdf" to the document "Q3 plan"',
      { verb: 'ATTACHMENT_ADDED', details: { file_name: 'minutes.pdf', size: 10 } },
    ],
    [
      'Deleted "minutes.pdf" from the document "Q3 plan"',
      { verb: 'ATTACHMENT_DELETED', details: { file_name: 'minutes.pdf' } },
    ],
  ])('says "%s"', (sentence, overrides) => {
    expect(describeEvent(buildAuditEvent(overrides))).toBe(sentence)
  })

  it("doesn't name a private resource the admin can't open, or what's in it", () => {
    const event = buildAuditEvent({
      verb: 'ATTACHMENT_ADDED',
      resource_name: null,
      details: { size: 10 },
    })

    expect(describeEvent(event)).toBe('Attached a file to a private document')
  })

  it('still reads when a person or a detail is missing', () => {
    const event = buildAuditEvent({
      verb: 'ACCESS_GRANTED',
      target_user_email: null,
      target_user_name: null,
      details: {},
    })

    expect(describeEvent(event)).toBe(
      'Gave a removed account unknown access to the document "Q3 plan"',
    )
  })
})

describe('actorName', () => {
  it('names the person, or a removed account', () => {
    expect(actorName(buildAuditEvent())).toBe('Ada Lovelace')
    expect(actorName(buildAuditEvent({ actor_email: null, actor_name: null }))).toBe(
      'A removed account',
    )
  })
})
