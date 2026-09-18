from django.urls import path

from subscriptions.api.v1.views import CheckoutSessionCreateAPIView

urlpatterns = [
    path(
        "checkout/",
        CheckoutSessionCreateAPIView.as_view(),
        name="subscriptions_checkout",
    ),
]
