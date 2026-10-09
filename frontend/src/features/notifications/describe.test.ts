import type { Notification } from '@/api/types'
import { describeNotification, notificationLink } from '@/features/notifications/describe'
import { buildNotification } from '@/test/factories'

describe('describeNotification', () => {
  it.each<[string, Partial<Notification>]>([
    ['Grace Hopper shared "Q3 plan" with you as Editor', {}],
    [
      'Grace Hopper changed your access to "Launch" to Viewer',
      {
        verb: 'ACCESS_CHANGED',
        resource_kind: 'PROJECT',
        resource_name: 'Launch',
        details: { access_level: 'VIEWER' },
      },
    ],
    ['Grace Hopper asked to edit "Q3 plan"', { verb: 'ACCESS_REQUESTED', details: {} }],
    [
      'Grace Hopper approved your request to edit "Q3 plan"',
      { verb: 'ACCESS_REQUEST_APPROVED', details: {} },
    ],
    [
      'Grace Hopper denied your request to edit "Q3 plan"',
      { verb: 'ACCESS_REQUEST_DENIED', details: {} },
    ],
  ])('says "%s"', (sentence, overrides) => {
    expect(describeNotification(buildNotification(overrides))).toBe(sentence)
  })

  it("doesn't name what the recipient can no longer open", () => {
    const notification = buildNotification({
      resource_kind: 'PROJECT',
      resource_id: null,
      resource_name: null,
    })

    expect(describeNotification(notification)).toBe(
      'Grace Hopper shared a project you can no longer open with you as Editor',
    )
  })

  it('still reads without the person or the level', () => {
    const notification = buildNotification({ actor_email: null, actor_name: null, details: {} })

    expect(describeNotification(notification)).toBe(
      'A removed account shared "Q3 plan" with you as a new level',
    )
  })
})

describe('notificationLink', () => {
  it('goes to the project or document, a request to the Requests page', () => {
    expect(notificationLink(buildNotification())).toBe('/documents/11')
    expect(notificationLink(buildNotification({ resource_kind: 'PROJECT', resource_id: 4 }))).toBe(
      '/projects/4',
    )
    expect(notificationLink(buildNotification({ verb: 'ACCESS_REQUESTED' }))).toBe('/requests')
  })

  it("goes nowhere once the recipient can't open it", () => {
    expect(notificationLink(buildNotification({ resource_id: null }))).toBeNull()
  })
})
