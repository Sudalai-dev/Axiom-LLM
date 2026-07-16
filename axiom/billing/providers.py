"""Payment provider interface and implementations.

Kept deliberately small and dependency-free at import time: the Stripe provider
imports its SDK lazily and only when actually used, so the module loads fine
without the ``stripe`` package installed.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from core.config import settings

logger = logging.getLogger("AxiomBilling")


@dataclass
class CheckoutResult:
    """What the frontend needs to advance the upgrade flow."""
    provider: str
    mode: str                       # "redirect" | "manual"
    checkout_url: Optional[str] = None
    message: Optional[str] = None
    activated: bool = False         # True if the provider activated inline (dev)


@dataclass
class WebhookResult:
    """Normalized outcome of a provider webhook, if it grants/revokes access."""
    user_id: str
    paid: bool


class PaymentProvider(ABC):
    """Turns an upgrade intent into a paid entitlement."""

    name: str = "base"

    @abstractmethod
    async def create_checkout(self, user_id: str, tenant_id: str, email: Optional[str]) -> CheckoutResult:
        """Starts an upgrade for a user."""

    async def handle_webhook(self, payload: bytes, signature: Optional[str]) -> Optional[WebhookResult]:
        """Processes an async provider callback. Default: no webhook."""
        return None


class ManualPaymentProvider(PaymentProvider):
    """Admin/operator-activated upgrades — no external payment integration.

    ``create_checkout`` does not charge anything; it returns instructions and
    an admin later flips the account to paid via the admin grant endpoint. This
    is the safe default so the platform is fully functional without any billing
    account configured.
    """

    name = "manual"

    async def create_checkout(self, user_id: str, tenant_id: str, email: Optional[str]) -> CheckoutResult:
        return CheckoutResult(
            provider=self.name,
            mode="manual",
            message=(
                "Upgrade requested. An administrator will activate your paid plan. "
                "(No online payment provider is configured on this deployment.)"
            ),
            activated=False,
        )


class StripePaymentProvider(PaymentProvider):
    """Stripe Checkout + webhook scaffold.

    Intentionally a stub: the wiring (create a Checkout session, verify webhook
    signatures, map the customer back to a user) is expressed here but guarded
    so it activates only when ``OCIF_STRIPE_SECRET_KEY`` / ``OCIF_STRIPE_PRICE_ID``
    / ``OCIF_STRIPE_WEBHOOK_SECRET`` are set. Without them it fails loudly rather
    than pretending to charge anyone.
    """

    name = "stripe"

    async def create_checkout(self, user_id: str, tenant_id: str, email: Optional[str]) -> CheckoutResult:
        if not (settings.entitlement.stripe_secret_key and settings.entitlement.stripe_price_id):
            raise RuntimeError(
                "Stripe is selected (OCIF_PAYMENT_PROVIDER=stripe) but not configured. "
                "Set OCIF_STRIPE_SECRET_KEY and OCIF_STRIPE_PRICE_ID."
            )
        # --- Live wiring (enable when the stripe SDK is a declared dependency): ---
        # import stripe
        # stripe.api_key = settings.entitlement.stripe_secret_key
        # session = stripe.checkout.Session.create(
        #     mode="subscription",
        #     line_items=[{"price": settings.entitlement.stripe_price_id, "quantity": 1}],
        #     success_url=..., cancel_url=...,
        #     client_reference_id=user_id, customer_email=email,
        # )
        # return CheckoutResult(provider=self.name, mode="redirect", checkout_url=session.url)
        raise NotImplementedError(
            "StripePaymentProvider is a scaffold. Implement the Checkout session "
            "creation above and add `stripe` to requirements to go live."
        )

    async def handle_webhook(self, payload: bytes, signature: Optional[str]) -> Optional[WebhookResult]:
        if not settings.entitlement.stripe_webhook_secret:
            raise RuntimeError("OCIF_STRIPE_WEBHOOK_SECRET is not set; cannot verify webhook.")
        # --- Live wiring: ---
        # import stripe
        # event = stripe.Webhook.construct_event(
        #     payload, signature, settings.entitlement.stripe_webhook_secret
        # )
        # if event["type"] == "checkout.session.completed":
        #     uid = event["data"]["object"]["client_reference_id"]
        #     return WebhookResult(user_id=uid, paid=True)
        # return None
        raise NotImplementedError("Implement Stripe webhook verification to go live.")


def get_payment_provider() -> PaymentProvider:
    """Returns the configured payment provider (default: manual)."""
    selected = (settings.entitlement.payment_provider or "manual").lower()
    if selected == "stripe":
        return StripePaymentProvider()
    if selected != "manual":
        logger.warning(f"Unknown OCIF_PAYMENT_PROVIDER '{selected}'; falling back to manual.")
    return ManualPaymentProvider()
