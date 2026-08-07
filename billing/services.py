def get_active_subscription(organization):
    """Return the organization's current active dj-stripe Subscription, or None.

    Access gating must go through this at request time rather than a stored
    flag on User — subscription status changes independently of any user
    record (renewal, cancellation, expiry all happen on Stripe's side).
    """
    if organization.djstripe_customer_id is None:
        return None
    return organization.djstripe_customer.subscriptions.filter(status="active").first()
