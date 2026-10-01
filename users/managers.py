from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.utils import timezone

from users.choices import InvitationStatus


class InvitationQuerySet(models.QuerySet):
    def for_organization(self, organization):
        return self.filter(organization=organization)

    def pending(self):
        """Invitations whose link still works: neither accepted nor revoked,
        and sent within ``INVITATION_EXPIRY``. The complement of
        ``Invitation.is_expired`` among stored ``PENDING`` rows."""
        return self.filter(
            status=InvitationStatus.PENDING,
            sent_at__gte=timezone.now() - settings.INVITATION_EXPIRY,
        )


InvitationManager = models.Manager.from_queryset(InvitationQuerySet)


class UserManager(BaseUserManager):
    """Email-based manager — AbstractUser's default UserManager hardcodes a
    required `username` positional arg, which no longer exists on this model."""

    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)
