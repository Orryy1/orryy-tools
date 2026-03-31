"""Stripe billing router - checkout sessions, webhooks, subscription status."""

import logging
from fastapi import APIRouter, HTTPException, Request, Query

from app.models import CheckoutRequest, CheckoutResponse, SubscriptionStatus
from app.services.stripe_service import (
    create_checkout_session,
    handle_webhook_event,
    get_subscription_status,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/billing/checkout", response_model=CheckoutResponse)
async def create_checkout(request: CheckoutRequest):
    """Create a Stripe Checkout session for a subscription or one-time payment.

    Pass a price_id to select the product:
    - Pro Monthly subscription
    - Pro Annual subscription
    - Single stem separation
    - Single track ID
    """
    try:
        result = await create_checkout_session(
            price_id=request.price_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            customer_email=request.customer_email,
            customer_id=request.customer_id,
        )
        return CheckoutResponse(**result)

    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {str(e)}")


@router.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events.

    Stripe sends POST requests here for subscription lifecycle events,
    payment success/failure, etc.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        result = await handle_webhook_event(payload, sig_header)
        return {"received": True, **result}

    except ValueError as e:
        logger.error(f"Webhook validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


@router.get("/api/billing/status", response_model=SubscriptionStatus)
async def check_subscription_status(customer_id: str = Query(..., description="Stripe customer ID")):
    """Check the subscription status for a Stripe customer.

    Returns whether the subscription is active, the plan name,
    period end date, and cancellation status.
    """
    if not customer_id.startswith("cus_"):
        raise HTTPException(status_code=400, detail="Invalid customer ID format")

    try:
        result = await get_subscription_status(customer_id)
        return SubscriptionStatus(**result)

    except Exception as e:
        logger.error(f"Failed to check subscription status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check subscription status: {str(e)}",
        )
