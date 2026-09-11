from django.test import TestCase

from organizations.factories import (
    OrganizationFactory,
    StripeCustomerFactory,
    StripeSubscriptionFactory,
)


class OrganizationModelTests(TestCase):
    def test_str_is_the_name(self):
        org = OrganizationFactory(name="Acme Inc")

        self.assertEqual(str(org), "Acme Inc")

    def test_email_property_aliases_billing_email(self):
        org = OrganizationFactory(billing_email="billing@acme.test")

        self.assertEqual(org.email, "billing@acme.test")

    def test_active_subscription_returns_the_active_subscription(self):
        org = OrganizationFactory()
        subscription = StripeSubscriptionFactory(customer__subscriber=org)

        with self.assertNumQueries(2):
            self.assertEqual(org.active_subscription, subscription)

    def test_active_subscription_is_none_without_a_customer(self):
        org = OrganizationFactory()

        with self.assertNumQueries(1):
            self.assertIsNone(org.active_subscription)

    def test_active_subscription_is_none_when_customer_has_no_active_sub(self):
        org = OrganizationFactory()
        StripeCustomerFactory(subscriber=org)

        with self.assertNumQueries(2):
            self.assertIsNone(org.active_subscription)

    def test_active_subscription_ignores_a_canceled_subscription(self):
        org = OrganizationFactory()
        StripeSubscriptionFactory(customer__subscriber=org, status="canceled")

        with self.assertNumQueries(2):
            self.assertIsNone(org.active_subscription)
