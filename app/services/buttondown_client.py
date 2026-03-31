"""Buttondown newsletter API client."""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BUTTONDOWN_API_BASE = "https://api.buttondown.email/v1"


class ButtondownClient:
    """Wrapper for the Buttondown newsletter API."""

    def __init__(self):
        self.api_key = settings.BUTTONDOWN_API_KEY

    def _check_key(self) -> None:
        if not self.api_key:
            raise ValueError("BUTTONDOWN_API_KEY is not configured")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }

    async def send_email(
        self,
        subject: str,
        body: str,
        status: str = "draft",
    ) -> dict:
        """Create and optionally send a newsletter email.

        Args:
            subject: Email subject line.
            body: Email body in Markdown or HTML.
            status: "draft" to save as draft, "about_to_send" to send immediately.

        Returns:
            Dict with the created email data from Buttondown.
        """
        self._check_key()
        payload = {
            "subject": subject,
            "body": body,
            "status": status,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{BUTTONDOWN_API_BASE}/emails",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        logger.info(f"Buttondown email created: subject='{subject}', status={status}, id={data.get('id')}")
        return data

    async def get_subscribers(self, page: int = 1) -> dict:
        """Fetch subscriber list (paginated).

        Args:
            page: Page number (1-indexed).

        Returns:
            Dict with count and results list.
        """
        self._check_key()
        params = {"page": page}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{BUTTONDOWN_API_BASE}/subscribers",
                params=params,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_subscriber_count(self) -> int:
        """Get total subscriber count.

        Returns:
            Integer count of active subscribers.
        """
        data = await self.get_subscribers(page=1)
        return data.get("count", 0)

    async def add_subscriber(
        self,
        email: str,
        metadata: Optional[dict] = None,
        tags: Optional[list[str]] = None,
    ) -> dict:
        """Add a new subscriber.

        Args:
            email: Subscriber email address.
            metadata: Optional metadata dict.
            tags: Optional list of tag strings.

        Returns:
            Dict with subscriber data.
        """
        self._check_key()
        payload = {"email": email}
        if metadata:
            payload["metadata"] = metadata
        if tags:
            payload["tags"] = tags

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{BUTTONDOWN_API_BASE}/subscribers",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        logger.info(f"Buttondown subscriber added: {email}")
        return data

    async def get_emails(self, page: int = 1, status: str = "sent") -> dict:
        """Fetch sent emails (paginated).

        Args:
            page: Page number.
            status: Filter by status (sent, draft, scheduled).

        Returns:
            Dict with count and results list.
        """
        self._check_key()
        params = {"page": page, "status": status}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{BUTTONDOWN_API_BASE}/emails",
                params=params,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()


buttondown_client = ButtondownClient()
