"""Stripe billing service for checkout sessions, webhooks, and subscription status."""

import logging
from typing import Optional
from datetime import datetime, timezone

import stripe

from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


async def create_checkout_session(
    price_id: str,
    success_url: str,
    cancel_url: str,
    customer_email: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> dict:
    """Create a Stripe Checkout session.

    Args:
        price_id: The Stripe price ID for the product.
        success_url: URL to redirect on successful payment.
        cancel_url: URL to redirect on cancelled payment.
        customer_email: Email for new customers.
        customer_id: Existing Stripe customer ID.

    Returns:
        Dict with checkout_url and session_id.
    """
    # Determine if this is a subscription or one-time payment
    subscription_prices = {
        settings.STRIPE_PRO_MONTHLY_PRICE_ID,
        settings.STRIPE_PRO_ANNUAL_PRICE_ID,
    }
    mode = "subscription" if price_id in subscription_prices else "payment"

    session_params = {
        "mode": mode,
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url + "?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": cancel_url,
    }

    if customer_id:
        session_params["customer"] = customer_id
    elif customer_email:
        session_params["customer_email"] = customer_email

    # Allow promotion codes
    session_params["allow_promotion_codes"] = True

    session = stripe.checkout.Session.create(**session_params)

    logger.info(f"Created checkout session {session.id} for price {price_id} (mode: {mode})")

    return {
        "checkout_url": session.url,
        "session_id": session.id,
    }


async def handle_webhook_event(payload: bytes, sig_header: str) -> dict:
    """Process a Stripe webhook event.

    Args:
        payload: Raw request body bytes.
        sig_header: Stripe-Signature header value.

    Returns:
        Dict with event type and processing result.
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        logger.error("Stripe webhook signature verification failed")
        raise ValueError("Invalid webhook signature")

    event_type = event["type"]
    data = event["data"]["object"]
    logger.info(f"Processing Stripe webhook: {event_type}")

    if event_type == "checkout.session.completed":
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")
        payment_intent = data.get("payment_intent")
        logger.info(
            f"Checkout completed: customer={customer_id}, "
            f"subscription={subscription_id}, payment_intent={payment_intent}"
        )
        # Here you would update your database, grant access, etc.
        return {"event": event_type, "customer_id": customer_id, "processed": True}

    elif event_type == "customer.subscription.created":
        customer_id = data.get("customer")
        status = data.get("status")
        logger.info(f"Subscription created: customer={customer_id}, status={status}")
        return {"event": event_type, "customer_id": customer_id, "status": status}

    elif event_type == "customer.subscription.updated":
        customer_id = data.get("customer")
        status = data.get("status")
        cancel_at = data.get("cancel_at_period_end")
        logger.info(
            f"Subscription updated: customer={customer_id}, "
            f"status={status}, cancel_at_period_end={cancel_at}"
        )
        return {"event": event_type, "customer_id": customer_id, "status": status}

    elif event_type == "customer.subscription.deleted":
        customer_id = data.get("customer")
        logger.info(f"Subscription deleted: customer={customer_id}")
        return {"event": event_type, "customer_id": customer_id, "cancelled": True}

    elif event_type == "invoice.payment_succeeded":
        customer_id = data.get("customer")
        amount = data.get("amount_paid", 0)
        logger.info(f"Payment succeeded: customer={customer_id}, amount={amount}")
        return {"event": event_type, "customer_id": customer_id, "amount": amount}

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        logger.warning(f"Payment failed: customer={customer_id}")
        return {"event": event_type, "customer_id": customer_id, "failed": True}

    else:
        logger.info(f"Unhandled webhook event type: {event_type}")
        return {"event": event_type, "processed": False}


async def get_subscription_status(customer_id: str) -> dict:
    """Get the subscription status for a Stripe customer.

    Args:
        customer_id: Stripe customer ID.

    Returns:
        Dict with subscription status details.
    """
    subscriptions = stripe.Subscription.list(
        customer=customer_id,
        status="all",
        limit=1,
    )

    if not subscriptions.data:
        return {
            "customer_id": customer_id,
            "is_active": False,
            "plan": None,
            "current_period_end": None,
            "cancel_at_period_end": False,
        }

    sub = subscriptions.data[0]
    is_active = sub.status in ("active", "trialing")

    # Get the price ID to determine the plan name
    price_id = None
    plan_name = None
    if sub.get("items") and sub["items"].get("data"):
        price_id = sub["items"]["data"][0].get("price", {}).get("id")

    if price_id == settings.STRIPE_PRO_MONTHLY_PRICE_ID:
        plan_name = "pro_monthly"
    elif price_id == settings.STRIPE_PRO_ANNUAL_PRICE_ID:
        plan_name = "pro_annual"
    else:
        plan_name = "unknown"

    period_end = None
    if sub.get("current_period_end"):
        period_end = datetime.fromtimestamp(
            sub["current_period_end"], tz=timezone.utc
        ).isoformat()

    return {
        "customer_id": customer_id,
        "is_active": is_active,
        "plan": plan_name,
        "current_period_end": period_end,
        "cancel_at_period_end": sub.get("cancel_at_period_end", False),
    }
