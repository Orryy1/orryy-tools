"""Free tier limit tracking via SQLite."""

import logging
import sqlite3
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.billing.plans import get_plan, check_feature_gate

logger = logging.getLogger(__name__)

DB_PATH = "db/orryy.db"


def _get_conn() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode for concurrent reads."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_usage_table(conn: sqlite3.Connection) -> None:
    """Create the usage table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            feature TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_usage_user_feature_period
        ON usage (user_id, feature, period_start)
    """)
    conn.commit()


class UsageTracker:
    """Tracks feature usage per user against plan limits in SQLite."""

    def __init__(self):
        self._initialized = False

    def _init_db(self) -> None:
        if not self._initialized:
            conn = _get_conn()
            try:
                _ensure_usage_table(conn)
                self._initialized = True
            finally:
                conn.close()

    def _get_period_bounds(self, period: str) -> tuple[str, str]:
        """Get ISO date strings for the start and end of a period.

        Args:
            period: "day" or "month".

        Returns:
            Tuple of (period_start, period_end) as ISO date strings.
        """
        now = datetime.now(timezone.utc)
        if period == "day":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                end = start.replace(year=now.year + 1, month=1)
            else:
                end = start.replace(month=now.month + 1)
        else:
            raise ValueError(f"Unknown period: {period}")

        return start.isoformat(), end.isoformat()

    async def get_usage(self, user_id: str, feature: str, period: str = "day") -> int:
        """Get the current usage count for a user/feature/period.

        Args:
            user_id: User identifier (email or Stripe customer ID).
            feature: Feature key (e.g. "analyses_per_day").
            period: "day" or "month".

        Returns:
            Current usage count.
        """
        self._init_db()
        period_start, period_end = self._get_period_bounds(period)

        def _query():
            conn = _get_conn()
            try:
                row = conn.execute(
                    "SELECT count FROM usage WHERE user_id = ? AND feature = ? AND period_start = ?",
                    (user_id, feature, period_start),
                ).fetchone()
                return row["count"] if row else 0
            finally:
                conn.close()

        return await asyncio.to_thread(_query)

    async def increment_usage(self, user_id: str, feature: str, period: str = "day", amount: int = 1) -> int:
        """Increment usage for a user/feature/period.

        Args:
            user_id: User identifier.
            feature: Feature key.
            period: "day" or "month".
            amount: Amount to increment by.

        Returns:
            New usage count after increment.
        """
        self._init_db()
        period_start, period_end = self._get_period_bounds(period)

        def _upsert():
            conn = _get_conn()
            try:
                row = conn.execute(
                    "SELECT id, count FROM usage WHERE user_id = ? AND feature = ? AND period_start = ?",
                    (user_id, feature, period_start),
                ).fetchone()

                now_str = datetime.now(timezone.utc).isoformat()

                if row:
                    new_count = row["count"] + amount
                    conn.execute(
                        "UPDATE usage SET count = ?, updated_at = ? WHERE id = ?",
                        (new_count, now_str, row["id"]),
                    )
                else:
                    new_count = amount
                    conn.execute(
                        "INSERT INTO usage (user_id, feature, count, period_start, period_end, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (user_id, feature, new_count, period_start, period_end, now_str, now_str),
                    )

                conn.commit()
                return new_count
            finally:
                conn.close()

        return await asyncio.to_thread(_upsert)

    async def check_limit(self, user_id: str, feature: str, plan_name: str = "free") -> dict:
        """Check if a user is within their plan limits for a feature.

        Args:
            user_id: User identifier.
            feature: Feature key matching a PlanLimits field.
            plan_name: The user's plan ("free" or "pro").

        Returns:
            Dict with allowed (bool), current_usage, limit, and remaining.
        """
        period = "day" if "per_day" in feature else "month"
        current = await self.get_usage(user_id, feature, period)
        plan = get_plan(plan_name)
        limit = getattr(plan.limits, feature, 0)

        return {
            "allowed": current < limit,
            "current_usage": current,
            "limit": limit,
            "remaining": max(0, limit - current),
        }

    async def record_and_check(self, user_id: str, feature: str, plan_name: str = "free") -> dict:
        """Check limits, and if allowed, increment usage atomically.

        Args:
            user_id: User identifier.
            feature: Feature key.
            plan_name: The user's plan.

        Returns:
            Dict with allowed, current_usage, limit, remaining.

        Raises:
            PermissionError if usage limit has been reached.
        """
        check = await self.check_limit(user_id, feature, plan_name)
        if not check["allowed"]:
            raise PermissionError(
                f"Usage limit reached for {feature}: "
                f"{check['current_usage']}/{check['limit']} "
                f"(plan: {plan_name})"
            )

        period = "day" if "per_day" in feature else "month"
        new_count = await self.increment_usage(user_id, feature, period)
        plan = get_plan(plan_name)
        limit = getattr(plan.limits, feature, 0)

        return {
            "allowed": True,
            "current_usage": new_count,
            "limit": limit,
            "remaining": max(0, limit - new_count),
        }


usage_tracker = UsageTracker()
