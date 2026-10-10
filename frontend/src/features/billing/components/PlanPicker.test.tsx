import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import type { Price } from '@/api/types'
import { externalRedirect } from '@/lib/external-redirect'
import { formatMoney } from '@/lib/format'
import {
  buildCurrentUser,
  buildOrganization,
  buildOrganizationSummary,
  buildPrice,
} from '@/test/factories'
import { renderRoute } from '@/test/render'
import { apiUrl, heldResponse, server, spyResolver } from '@/test/server'

const PRICES_PATH = '/subscriptions/prices/'
const CHECKOUT_PATH = '/subscriptions/checkout/'
const CHECKOUT_URL = 'https://checkout.stripe.com/c/pay/test'
const MONTHLY = buildPrice()
const YEARLY = buildPrice({ id: 'price_yearly', unit_amount: 15000, interval: 'year' })
// The plans are what a lapsed organization's admin sees in place of the app.
const lapsedAdmin = buildCurrentUser({
  org_role: 'ADMIN',
  organization: buildOrganizationSummary({ has_active_subscription: false }),
})

function serveBilling({
  prices = [MONTHLY, YEARLY],
  billingEmail = 'billing@acme.test',
}: { prices?: Price[]; billingEmail?: string | null } = {}) {
  server.use(
    http.get(apiUrl('/organizations/profile/'), () =>
      HttpResponse.json(
        buildOrganization({ active_subscription: null, billing_email: billingEmail }),
      ),
    ),
    http.get(apiUrl(PRICES_PATH), () =>
      HttpResponse.json({ count: prices.length, results: prices }),
    ),
  )
}

function planCard(title: string) {
  return within(screen.getByRole('heading', { name: title }).closest('li')!)
}

describe('PlanPicker', () => {
  let redirect: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    redirect = vi.spyOn(externalRedirect, 'to').mockImplementation(() => {})
  })

  afterEach(() => {
    redirect.mockRestore()
  })

  it('lists the plans with their prices', async () => {
    serveBilling()
    renderRoute('/', { signedInAs: lapsedAdmin })

    await screen.findByRole('list', { name: 'Plans' })
    expect(planCard('Monthly').getByText('DocSphere')).toBeInTheDocument()
    expect(planCard('Monthly').getByText(formatMoney(1500, 'usd'))).toBeInTheDocument()
    expect(planCard('Monthly').getByText('per month')).toBeInTheDocument()
    expect(planCard('Yearly').getByText(formatMoney(15000, 'usd'))).toBeInTheDocument()
    expect(planCard('Yearly').getByText('per year')).toBeInTheDocument()
  })

  it('names a plan by its product when the interval is unknown, and shows no amount when there is none', async () => {
    serveBilling({
      prices: [buildPrice({ product_name: 'Enterprise', interval: null, unit_amount: null })],
    })
    renderRoute('/', { signedInAs: lapsedAdmin })

    const card = within((await screen.findByRole('list', { name: 'Plans' })).querySelector('li')!)
    expect(card.getByRole('heading', { name: 'Enterprise' })).toBeInTheDocument()
    expect(card.queryByText(/per /)).not.toBeInTheDocument()
  })

  it('describes an interval it has no wording for in plain terms', async () => {
    serveBilling({ prices: [buildPrice({ interval: 'fortnight' })] })
    renderRoute('/', { signedInAs: lapsedAdmin })

    expect(await screen.findByText('per fortnight')).toBeInTheDocument()
  })

  it('starts Stripe Checkout for the chosen plan, holding the others while it leaves', async () => {
    serveBilling()
    const checkout = heldResponse(() => HttpResponse.json({ checkout_url: CHECKOUT_URL }))
    const spy = spyResolver(checkout.resolver)
    server.use(http.post(apiUrl(CHECKOUT_PATH), spy))
    const { user } = renderRoute('/', { signedInAs: lapsedAdmin })

    const subscribe = await screen.findByRole('button', {
      name: 'Subscribe to the yearly plan',
    })
    await user.click(subscribe)
    expect(subscribe).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Subscribe to the monthly plan' })).toBeDisabled()
    checkout.release()

    await vi.waitFor(() => expect(redirect).toHaveBeenCalledWith(CHECKOUT_URL))
    expect(await spy.mock.calls[0][0].request.json()).toEqual({ price_id: 'price_yearly' })
    expect(subscribe).toBeDisabled()
  })

  it('asks for a billing email before anything can be bought', async () => {
    serveBilling({ billingEmail: null })
    renderRoute('/', { signedInAs: lapsedAdmin })

    expect(await screen.findByText(/Add a billing email below before subscribing/)).toBeVisible()
    expect(
      await screen.findByRole('button', { name: 'Subscribe to the monthly plan' }),
    ).toBeDisabled()
    expect(screen.getByLabelText('Billing email')).toHaveValue('')
  })

  it("reports the API's reason when checkout is refused", async () => {
    serveBilling()
    server.use(
      http.post(apiUrl(CHECKOUT_PATH), () =>
        HttpResponse.json(
          {
            non_field_errors: [
              'Your organization already has an active subscription. Manage it from the billing portal.',
            ],
          },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderRoute('/', { signedInAs: lapsedAdmin })

    await user.click(await screen.findByRole('button', { name: 'Subscribe to the monthly plan' }))

    expect(
      await screen.findByText(/Your organization already has an active subscription/),
    ).toBeInTheDocument()
    expect(redirect).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Subscribe to the monthly plan' })).toBeEnabled()
  })

  it('lets a returning organization open the billing portal', async () => {
    serveBilling()
    server.use(
      http.post(apiUrl('/subscriptions/portal/'), () =>
        HttpResponse.json({ portal_url: 'https://billing.stripe.com/session/test' }),
      ),
    )
    const { user } = renderRoute('/', { signedInAs: lapsedAdmin })

    await user.click(
      await screen.findByRole('button', {
        name: 'Update your payment details in the billing portal.',
      }),
    )

    await vi.waitFor(() =>
      expect(redirect).toHaveBeenCalledWith('https://billing.stripe.com/session/test'),
    )
  })

  it('says when no plans are on offer', async () => {
    serveBilling({ prices: [] })
    renderRoute('/', { signedInAs: lapsedAdmin })

    expect(await screen.findByText('No plans available')).toBeInTheDocument()
  })

  it('offers a retry when the plans fail to load', async () => {
    serveBilling()
    server.use(http.get(apiUrl(PRICES_PATH), () => HttpResponse.json({}, { status: 500 })))
    const { user } = renderRoute('/', { signedInAs: lapsedAdmin })

    const retry = await screen.findByRole('button', { name: 'Try again' })
    serveBilling()
    await user.click(retry)

    expect(await screen.findByRole('list', { name: 'Plans' })).toBeInTheDocument()
  })
})
