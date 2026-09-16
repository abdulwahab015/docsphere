from django.conf import settings

from subscriptions.choices import Plan

PLAN_PRICE_IDS = {
    Plan.MONTHLY: settings.STRIPE_PRICE_ID_MONTHLY,
    Plan.YEARLY: settings.STRIPE_PRICE_ID_YEARLY,
}
