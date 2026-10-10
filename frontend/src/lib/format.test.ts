import { formatBytes, formatMoney } from '@/lib/format'

describe('formatMoney', () => {
  it("converts from the currency's smallest unit", () => {
    expect(formatMoney(1500, 'usd')).toBe(
      new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' }).format(15),
    )
  })

  it('leaves zero-decimal currencies as they are', () => {
    expect(formatMoney(1500, 'jpy')).toBe(
      new Intl.NumberFormat(undefined, { style: 'currency', currency: 'JPY' }).format(1500),
    )
  })
})

describe('formatBytes', () => {
  it('reads like a person would say it', () => {
    expect(formatBytes(820)).toBe('820 B')
    expect(formatBytes(1536)).toBe('1.5 KB')
    expect(formatBytes(12 * 1024)).toBe('12 KB')
    expect(formatBytes(2_400_000)).toBe('2.3 MB')
    expect(formatBytes(3 * 1024 ** 3)).toBe('3.0 GB')
  })
})
