"""Orryy Tools API - AI-powered audio tools for DJs."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.models import HealthResponse
from app.routers import analyze, stems, compatibility, trackid, billing, jobs
from app.routers import mashup, tunebot, health, webhooks
from app.cron.mixfeed import run_mixfeed_pipeline
from app.cron.tunebot_daily import run_tunebot_daily
from app.cron.cleanup import run_cleanup
from app.jobs.store import job_store

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# APScheduler instance
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info("Orryy Tools API starting up...")
    logger.info(f"CORS origins: {settings.cors_origins_list}")

    # Initialise the SQLite job store
    job_store._init_db()

    # Register cron jobs
    scheduler.add_job(
        run_mixfeed_pipeline,
        CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="mixfeed_weekly",
        name="Weekly MixFeed Pipeline",
        replace_existing=True,
    )
    scheduler.add_job(
        run_tunebot_daily,
        CronTrigger(hour=8, minute=0),
        id="tunebot_daily",
        name="Daily TuneBot Checks",
        replace_existing=True,
    )
    scheduler.add_job(
        run_cleanup,
        CronTrigger(hour=3, minute=0),
        id="cleanup_daily",
        name="Daily Cleanup",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"APScheduler started with {len(scheduler.get_jobs())} jobs")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Orryy Tools API shutting down...")


app = FastAPI(
    title="Orryy Tools API",
    description="AI-powered audio tools for DJs - stem separation, key/BPM analysis, track ID, mashups, and more.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, tags=["Health"])
app.include_router(analyze.router, prefix="/api", tags=["Analysis"])
app.include_router(stems.router, prefix="/api", tags=["Stems"])
app.include_router(compatibility.router, prefix="/api", tags=["Compatibility"])
app.include_router(mashup.router, prefix="/api", tags=["Mashup"])
app.include_router(trackid.router, prefix="/api", tags=["Track ID"])
app.include_router(jobs.router, prefix="/api", tags=["Jobs"])
app.include_router(tunebot.router, prefix="/api", tags=["TuneBot"])
app.include_router(billing.router, tags=["Billing"])
app.include_router(webhooks.router, tags=["Webhooks"])
