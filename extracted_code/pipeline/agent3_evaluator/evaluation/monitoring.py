"""
Monitoring Planner
==================
VA26 §6 — Determines monitoring intervals and creates a monitoring plan
based on risk class + economic class.

Monitoring intervals:
  Class 1 + A → 12 months
  Class 1 + B → 6 months
  Class 1 + C → 3 months
  Class 2 + A → 12 months
  Class 2 + B → 6 months
  Class 2 + C → 3 months
  Class 3 + A → 24 months
  Class 3 + B → 12 months
  Class 3 + C → 6 months
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agent3_evaluator.rules.va26 import RiskClass, get_monitoring_interval


@dataclass
class MonitoringPlan:
    """Monitoring plan for a supplier."""
    supplier_id: str
    risk_class: RiskClass
    economic_class: str        # "A", "B", or "C"
    monitoring_interval_months: int
    next_review_date: str | None
    plan_items: list[str]
    va26_ref: str = "VA26 §6"
    status: Literal["active", "pending"] = "active"


def get_monitoring_plan(risk_class: RiskClass, economic_class: str) -> list[str]:
    """
    Return monitoring plan items per VA26 §6 based on risk + economic class.
    """
    base = [
        "Review and update supplier qualification file",
        "Verify QAA is current and signed",
    ]

    if economic_class == "C":
        base.append("Conduct intermediate quality review (economically poor supplier)")

    if risk_class in (RiskClass.CLASS_1, RiskClass.CLASS_2):
        base.append("Confirm ISO 13485 certificate is still valid")
        base.append("Review nonconformances and corrective actions since last review")
        base.append("Verify purchase history shows acceptable quality/delivery")
        if economic_class in ("B", "C"):
            base.append("Request updated quality performance data")

    if risk_class == RiskClass.CLASS_3:
        base.append("Confirm continued eligibility for Class 3 status")
        if economic_class == "C":
            base.append("Consider reclassification or supplier replacement")

    return base


def create_monitoring_plan(
    supplier_id: str,
    risk_class: RiskClass,
    economic_class: str,   # "A", "B", or "C"
    eval_date: str | None = None,
) -> MonitoringPlan:
    """
    Create monitoring plan per VA26 §6.

    Args:
        risk_class: 1, 2, or 3
        economic_class: "A", "B", or "C"
        eval_date: Evaluation date (YYYY-MM-DD). If None, uses today.

    Returns:
        MonitoringPlan with interval and plan items.
    """
    import datetime
    today = datetime.date.today()

    if eval_date:
        try:
            parts = eval_date.split("-")
            if len(parts) == 3:
                today = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception:
            pass

    interval = get_monitoring_interval(risk_class, economic_class)
    next_review = today + datetime.timedelta(days=interval * 30)

    plan_items = get_monitoring_plan(risk_class, economic_class)

    return MonitoringPlan(
        supplier_id=supplier_id,
        risk_class=risk_class,
        economic_class=economic_class,
        monitoring_interval_months=interval,
        next_review_date=next_review.isoformat(),
        plan_items=plan_items,
    )


def format_monitoring_plan(plan: MonitoringPlan) -> str:
    """Format monitoring plan as human-readable text."""
    lines = []
    lines.append(f"\n  ── VA26 §6 Monitoring Plan ─────────────────────────────")
    lines.append(f"  Supplier: {plan.supplier_id}")
    lines.append(f"  Risk Class: {plan.risk_class.value} | Economic: {plan.economic_class}")
    lines.append(f"  Monitoring Interval: every {plan.monitoring_interval_months} months")
    lines.append(f"  Next Review: {plan.next_review_date or 'not set'}")
    lines.append(f"  {'─' * 56}")
    lines.append(f"  Plan Items:")
    for item in plan.plan_items:
        lines.append(f"    • {item}")
    return "\n".join(lines)
