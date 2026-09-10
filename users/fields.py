from django.db.models import EmailField as _EmailField


class EmailField(_EmailField):
    """Email field that normalizes to lowercase.

    Django's ``BaseUserManager.normalize_email`` only lowercases the domain,
    so ``Alice@Example.com`` and ``alice@example.com`` would otherwise be two
    distinct rows (and one of them unable to log in). Normalizing in
    ``get_prep_value`` covers both writes and lookup values, which makes the
    ``authenticate()`` email lookup case-insensitive for free.
    """

    def to_python(self, value):
        value = super().to_python(value)
        return value.lower() if isinstance(value, str) else value

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return value.lower() if isinstance(value, str) else value
