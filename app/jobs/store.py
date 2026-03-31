"""SQLite-backed job tracking store."""

import logging
import sqlite3
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional, Any

logger = logging.getLogger(__name__)

DB_PATH = "db/orryy.db"


def _get_conn() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create the jobs table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            progress REAL,
            result TEXT,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs (created_at)
    """)
    conn.commit()


class JobStore:
    """SQLite-backed persistent job store.

    Replaces the in-memory dict for job tracking, providing persistence
    across restarts and concurrent access safety via WAL mode.
    """

    def __init__(self):
        self._initialized = False

    def _init_db(self) -> None:
        if not self._initialized:
            import os
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            conn = _get_conn()
            try:
                _ensure_tables(conn)
                self._initialized = True
            finally:
                conn.close()

    async def create_job(self, job_id: str, job_type: str = "") -> dict:
        """Create a new job record.

        Args:
            job_id: Unique job identifier.
            job_type: Type of job (e.g. "stems", "mashup", "trackid").

        Returns:
            Dict with the created job record.
        """
        self._init_db()
        now = datetime.now(timezone.utc).isoformat()

        def _insert():
            conn = _get_conn()
            try:
                conn.execute(
                    "INSERT INTO jobs (job_id, job_type, status, created_at, updated_at) VALUES (?, ?, 'pending', ?, ?)",
                    (job_id, job_type, now, now),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_insert)
        logger.info(f"Job created: {job_id} (type={job_type})")

        return {
            "job_id": job_id,
            "job_type": job_type,
            "status": "pending",
            "progress": None,
            "result": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }

    async def get_job(self, job_id: str) -> Optional[dict]:
        """Get a job record by ID.

        Args:
            job_id: The job identifier.

        Returns:
            Dict with job data, or None if not found.
        """
        self._init_db()

        def _query():
            conn = _get_conn()
            try:
                row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
                if not row:
                    return None
                data = dict(row)
                if data.get("result"):
                    data["result"] = json.loads(data["result"])
                return data
            finally:
                conn.close()

        return await asyncio.to_thread(_query)

    async def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        result: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update a job record.

        Args:
            job_id: The job identifier.
            status: New status (pending, processing, complete, failed).
            progress: Progress value (0.0 to 1.0).
            result: Result data dict (stored as JSON).
            error: Error message string.
        """
        self._init_db()
        now = datetime.now(timezone.utc).isoformat()

        def _update():
            conn = _get_conn()
            try:
                updates = ["updated_at = ?"]
                params = [now]

                if status is not None:
                    updates.append("status = ?")
                    params.append(status)
                if progress is not None:
                    updates.append("progress = ?")
                    params.append(progress)
                if result is not None:
                    updates.append("result = ?")
                    params.append(json.dumps(result))
                if error is not None:
                    updates.append("error = ?")
                    params.append(error)

                params.append(job_id)
                sql = f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?"
                conn.execute(sql, params)
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_update)

    async def list_jobs(
        self,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List jobs with optional filtering.

        Args:
            status: Filter by status.
            job_type: Filter by job type.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of job dicts.
        """
        self._init_db()

        def _query():
            conn = _get_conn()
            try:
                conditions = []
                params = []

                if status:
                    conditions.append("status = ?")
                    params.append(status)
                if job_type:
                    conditions.append("job_type = ?")
                    params.append(job_type)

                where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                sql = f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                rows = conn.execute(sql, params).fetchall()
                results = []
                for row in rows:
                    data = dict(row)
                    if data.get("result"):
                        data["result"] = json.loads(data["result"])
                    results.append(data)
                return results
            finally:
                conn.close()

        return await asyncio.to_thread(_query)

    async def purge_old_jobs(self, max_age_seconds: int = 604800) -> int:
        """Delete jobs older than max_age_seconds that are complete or failed.

        Args:
            max_age_seconds: Maximum age in seconds (default 7 days).

        Returns:
            Number of deleted job records.
        """
        self._init_db()

        def _purge():
            conn = _get_conn()
            try:
                cursor = conn.execute(
                    "DELETE FROM jobs WHERE status IN ('complete', 'failed') "
                    "AND created_at < datetime('now', ?)",
                    (f"-{max_age_seconds} seconds",),
                )
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()

        return await asyncio.to_thread(_purge)


job_store = JobStore()
