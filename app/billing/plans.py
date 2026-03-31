"""Plan definitions and feature gates for Orryy Tools."""

from dataclasses import dataclass, field
from typing import Optional

from app.config import settings


@dataclass
class PlanLimits:
    """Defines the limits for a billing plan."""
    analyses_per_day: int
    stems_per_month: int
    trackids_per_month: int
    mashups_per_month: int
    tunebot_audits_per_month: int
    compatibility_checks_per_day: int
    max_file_size_mb: int
    priority_processing: bool = False


@dataclass
class Plan:
    """A billing plan with its metadata and limits."""
    name: str
    display_name: str
    stripe_price_ids: list[str] = field(default_factory=list)
    limits: PlanLimits = field(default_factory=lambda: PlanLimits(
        analyses_per_day=0,
        stems_per_month=0,
        trackids_per_month=0,
        mashups_per_month=0,
        tunebot_audits_per_month=0,
        compatibility_checks_per_day=0,
        max_file_size_mb=0,
    ))


# Plan definitions
FREE_PLAN = Plan(
    name="free",
    display_name="Free",
    stripe_price_ids=[],
    limits=PlanLimits(
        analyses_per_day=5,
        stems_per_month=2,
        trackids_per_month=5,
        mashups_per_month=1,
        tunebot_audits_per_month=1,
        compatibility_checks_per_day=10,
        max_file_size_mb=25,
        priority_processing=False,
    ),
)

PRO_PLAN = Plan(
    name="pro",
    display_name="Pro",
    stripe_price_ids=[
        settings.STRIPE_PRO_MONTHLY_PRICE_ID,
        settings.STRIPE_PRO_ANNUAL_PRICE_ID,
    ],
    limits=PlanLimits(
        analyses_per_day=100,
        stems_per_month=50,
        trackids_per_month=100,
        mashups_per_month=20,
        tunebot_audits_per_month=30,
        compatibility_checks_per_day=200,
        max_file_size_mb=100,
        priority_processing=True,
    ),
)

# All plans indexed by name
PLANS = {
    "free": FREE_PLAN,
    "pro": PRO_PLAN,
}


def get_plan(plan_name: str) -> Plan:
    """Get a plan by name. Defaults to free if not found."""
    return PLANS.get(plan_name, FREE_PLAN)


def get_plan_for_price(price_id: str) -> Plan:
    """Look up which plan a Stripe price ID belongs to."""
    for plan in PLANS.values():
        if price_id in plan.stripe_price_ids:
            return plan
    return FREE_PLAN


def check_feature_gate(plan_name: str, feature: str, current_usage: int) -> bool:
    """Check if a feature usage is within plan limits.

    Args:
        plan_name: The user's plan name ("free" or "pro").
        feature: The feature key (e.g. "analyses_per_day", "stems_per_month").
        current_usage: The user's current usage count for this feature.

    Returns:
        True if the usage is within limits, False if at/over limit.
    """
    plan = get_plan(plan_name)
    limit = getattr(plan.limits, feature, None)
    if limit is None:
        return False
    return current_usage < limit
