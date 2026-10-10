from rest_framework.exceptions import APIException


class PaymentProviderUnavailable(APIException):
    """Stripe couldn't be reached, or refused a change the app had to make
    there as well, so the change was not made at all."""

    status_code = 502
    default_detail = (
        "We couldn't update our payment provider, so nothing was changed. "
        "Please try again."
    )
    default_code = "payment_provider_unavailable"
