import { formatMoney } from '@/lib/format'

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
