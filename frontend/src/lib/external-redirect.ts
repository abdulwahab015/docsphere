/** Leaves the app for a page elsewhere - Stripe Checkout or the billing
 * portal. An object rather than a bare function so tests can spy on it, since
 * jsdom can't navigate. */
export const externalRedirect = {
  to(url: string) {
    window.location.assign(url)
  },
}
