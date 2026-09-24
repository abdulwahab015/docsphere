from django.urls import path

from subscriptions.api.v1.views import (
    BillingPortalSessionCreateAPIView,
    CheckoutSessionCreateAPIView,
    PriceListAPIView,
)

urlpatterns = [
    path("prices/", PriceListAPIView.as_view(), name="subscriptions_price_list"),
    path(
        "portal/",
        BillingPortalSessionCreateAPIView.as_view(),
        name="subscriptions_portal",
    ),
    path(
        "checkout/",
        CheckoutSessionCreateAPIView.as_view(),
        name="subscriptions_checkout",
    ),
]
