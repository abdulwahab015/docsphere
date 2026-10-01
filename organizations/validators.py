from rest_framework.exceptions import ValidationError

from organizations.models import Organization

BILLING_EMAIL_TAKEN_MESSAGE = "An organization with this billing email already exists."


def validate_unique_billing_email(billing_email, organization=None):
    """Rejects a billing email another organization already uses, reporting it
    as a field error rather than an IntegrityError.

    An empty billing email never clashes: the column is unique but nullable,
    so any number of organizations may leave it unset - and filtering on
    ``billing_email=None`` would match every one of them. ``organization`` is
    the one being updated, which may keep its own address."""
    if not billing_email:
        return billing_email

    clashes = Organization.objects.filter(billing_email=billing_email)
    if organization:
        clashes = clashes.exclude(pk=organization.pk)
    if clashes.exists():
        raise ValidationError(BILLING_EMAIL_TAKEN_MESSAGE)
    return billing_email
