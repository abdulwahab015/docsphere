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


class RecoveryCodeQuerySet(models.QuerySet):
    def unused(self):
        return self.filter(used_at__isnull=True)


class UserQuerySet(models.QuerySet):
    def unverified_past_expiry(self):
        """Accounts that signed up without verifying their address within
        ``EMAIL_LINK_EXPIRY``. They no longer hold the address: whoever owns
        it may sign up or accept an invitation with it, which removes them."""
        return self.filter(
            email_verified_at__isnull=True,
            created__lt=timezone.now() - settings.EMAIL_LINK_EXPIRY,
        )

    def holding_email(self):
        """Accounts that hold their address, so nobody else may sign up with
        it, be invited with it or move their account to it: all of them but
        those that never verified it in time."""
        return self.exclude(
            email_verified_at__isnull=True,
            created__lt=timezone.now() - settings.EMAIL_LINK_EXPIRY,
        )

    def release_email(self, email):
        """Frees ``email`` from an account that never verified it in time,
        for the person now signing up, accepting an invitation or moving
        their account to it."""
        self.unverified_past_expiry().filter(email=email).delete_with_organizations()

    def delete_with_organizations(self):
        """Deletes these unverified accounts together with the organization
        each one signed up, which deletes the account too. Nothing else can
        be in it: until its admin verifies, an organization can't invite
        anyone, create anything or subscribe. An organization that somehow
        has a verified member is left alone."""
        organization_model = self.model._meta.get_field("organization").related_model
        organization_model.objects.filter(
            pk__in=self.values("organization_id")
        ).exclude(users__email_verified_at__isnull=False).delete()


class UserManager(BaseUserManager.from_queryset(UserQuerySet)):
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
        # Created from the command line by whoever runs the platform.
        extra_fields.setdefault("email_verified_at", timezone.now())
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)
