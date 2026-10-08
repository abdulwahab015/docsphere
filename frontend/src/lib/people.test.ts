import { creatorName, displayName } from '@/lib/people'

describe('displayName', () => {
  it("shows a person's name", () => {
    expect(displayName({ name: 'Grace Hopper', email: 'grace@example.com' })).toBe('Grace Hopper')
  })

  it("falls back to their email address while they haven't given a name", () => {
    expect(displayName({ name: '', email: 'grace@example.com' })).toBe('grace@example.com')
  })
})

describe('creatorName', () => {
  it('names whoever created a project or document, or gives their email address', () => {
    expect(
      creatorName({ created_by_name: 'Ada Lovelace', created_by_email: 'ada@example.com' }),
    ).toBe('Ada Lovelace')
    expect(creatorName({ created_by_name: '', created_by_email: 'ada@example.com' })).toBe(
      'ada@example.com',
    )
  })
})
