from django.test import TestCase
from djstripe.models import Customer

from organizations.factories import OrganizationFactory


class OrganizationModelTests(TestCase):
    def test_str_is_the_name(self):
        org = OrganizationFactory(name="Acme Inc")

        self.assertEqual(str(org), "Acme Inc")

    def test_email_property_aliases_billing_email(self):
        org = OrganizationFactory(billing_email="billing@acme.test")

        self.assertEqual(org.email, "billing@acme.test")

    def test_active_subscription_is_none_without_a_customer(self):
        org = OrganizationFactory()

        self.assertIsNone(org.active_subscription)

    def test_active_subscription_is_none_when_customer_has_no_active_sub(self):
        org = OrganizationFactory()
        Customer.objects.create(id="cus_test_org", subscriber=org)

        self.assertIsNone(org.active_subscription)
