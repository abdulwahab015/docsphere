import { type Action, can } from '@/lib/access'

const EVERY_ACTION: Action[] = ['READ', 'WRITE', 'DELETE', 'RESHARE']

function allowedActions(level: Parameters<typeof can>[0]) {
  return EVERY_ACTION.filter((action) => can(level, action))
}

describe('can', () => {
  it('follows Owner > Editor > Viewer', () => {
    expect(allowedActions('OWNER')).toEqual(['READ', 'WRITE', 'DELETE', 'RESHARE'])
    expect(allowedActions('EDITOR')).toEqual(['READ', 'WRITE'])
    expect(allowedActions('VIEWER')).toEqual(['READ'])
  })

  it('allows nothing without an access level', () => {
    expect(allowedActions(null)).toEqual([])
  })
})
