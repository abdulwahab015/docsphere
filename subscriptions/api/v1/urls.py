from django.urls import path

from subscriptions.api.v1.views import CheckoutSessionCreateAPIView, PriceListAPIView

urlpatterns = [
    path("prices/", PriceListAPIView.as_view(), name="subscriptions_price_list"),
    path(
        "checkout/",
        CheckoutSessionCreateAPIView.as_view(),
        name="subscriptions_checkout",
    ),
]
