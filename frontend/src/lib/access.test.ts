import { type Action, can, canRequestEditAccess } from '@/lib/access'

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

describe('canRequestEditAccess', () => {
  it('lets only a Viewer ask for Editor access', () => {
    expect(canRequestEditAccess('VIEWER')).toBe(true)
    expect(canRequestEditAccess('EDITOR')).toBe(false)
    expect(canRequestEditAccess('OWNER')).toBe(false)
    expect(canRequestEditAccess(null)).toBe(false)
  })
})
