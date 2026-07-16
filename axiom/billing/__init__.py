"""Billing subsystem — pluggable payment providers for the paid plan.

A ``PaymentProvider`` turns "the user wants to upgrade" into "the user is
marked paid". Two implementations ship:

  - :class:`ManualPaymentProvider` (default) — no external dependency; an
    operator/admin activates the account (``POST /api/v1/billing/admin/grant``).
    Suitable for dev, pilots, and invoice-based sales.
  - :class:`StripePaymentProvider` — a documented scaffold (Checkout session +
    webhook) that activates automatically once ``OCIF_STRIPE_*`` env is set.
    Ships as a stub so no live Stripe account/keys are required to run AXIOM.

Selected by ``OCIF_PAYMENT_PROVIDER`` (``manual`` | ``stripe``).
"""

from billing.providers import (
    ManualPaymentProvider,
    PaymentProvider,
    StripePaymentProvider,
    get_payment_provider,
)

__all__ = [
    "PaymentProvider",
    "ManualPaymentProvider",
    "StripePaymentProvider",
    "get_payment_provider",
]
