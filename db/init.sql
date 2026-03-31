-- Orryy Tools database schema
-- SQLite 3.x
-- Run: sqlite3 db/orryy.db < db/init.sql

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Jobs table: tracks async processing jobs (stems, mashups, trackid)
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'complete', 'failed')),
    progress REAL CHECK (progress IS NULL OR (progress >= 0 AND progress <= 1)),
    result TEXT,           -- JSON blob with job output data
    error TEXT,            -- Error message if failed
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs (created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs (job_type);

-- Usage table: tracks feature usage for billing/rate limiting
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    feature TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_usage_user_feature_period ON usage (user_id, feature, period_start);
CREATE INDEX IF NOT EXISTS idx_usage_user ON usage (user_id);

-- Users table: maps Stripe customers to internal user data
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT UNIQUE NOT NULL,           -- internal user ID or email
    email TEXT,
    stripe_customer_id TEXT UNIQUE,
    plan TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'pro')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_stripe ON users (stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_users_plan ON users (plan);
