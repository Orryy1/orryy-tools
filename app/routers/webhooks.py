"""Webhook router - Stripe webhooks extracted for clean routing."""

import logging
from fastapi import APIRouter, HTTPException, Request

from app.services.stripe_service import handle_webhook_event

logger = logging.getLogger(__name__)
router = APIRouter()


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
