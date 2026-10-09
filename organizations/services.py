from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from organizations.models import Organization
from projects.models import Attachment, Document, DocumentVersion, Project
from subscriptions.services import cancel_subscription
from users.choices import InvitationStatus
from users.models import Invitation
from users.services import blacklist_outstanding_tokens

User = get_user_model()


def schedule_deletion(organization):
    """Deletes ``organization`` as far as its people can tell: everyone is
    signed out, pending invitations stop working and the subscription is
    cancelled at once. Its admins can restore it until it's purged. If Stripe
    can't cancel the subscription, nothing changes."""
    with transaction.atomic():
        organization = Organization.objects.select_for_update().get(pk=organization.pk)
        organization.deletion_requested_at = timezone.now()
        organization.save(update_fields=["deletion_requested_at"])
        Invitation.objects.for_organization(organization).pending().update(
            status=InvitationStatus.REVOKED
        )
        for user in User.objects.filter(organization=organization):
            blacklist_outstanding_tokens(user)
        # Last, so a refusal from Stripe undoes everything above.
        cancel_subscription(organization)


def cancel_deletion(organization):
    """Restores a deleted organization before it's purged. Its subscription
    stays cancelled: an admin subscribes again to carry on."""
    organization.deletion_requested_at = None
    organization.save(update_fields=["deletion_requested_at"])


def purge_organization(organization):
    """Removes ``organization`` and everything in it for good, stored files
    included (once the database part is committed). Content goes first:
    projects, documents and their history keep their authors with
    ``PROTECT``, so the people can only go after it."""
    attachments = Attachment.objects.filter(document__organization=organization)
    stored_files = [
        (attachment.file.storage, attachment.file.name) for attachment in attachments
    ]
    stored_files += [
        (export.file.storage, export.file.name)
        for export in organization.exports.exclude(file="")
    ]
    with transaction.atomic():
        attachments.delete()
        DocumentVersion.objects.filter(document__organization=organization).delete()
        Document.objects.filter(organization=organization).delete()
        Project.objects.filter(organization=organization).delete()
        organization.delete()

    def delete_stored_files():
        for storage, name in stored_files:
            storage.delete(name)

    transaction.on_commit(delete_stored_files)
