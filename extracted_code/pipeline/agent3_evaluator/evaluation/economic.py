"""
Economic Evaluator
==================
VA26 §2.2.2 — 6-criterion weighted scoring → A/B/C classification.

Scoring is DETERMINISTIC where data exists.
Missing data → score = 3 (neutral), flagged as "estimated".

This module does NOT make approval decisions — it only computes the
economic score and classification. The decision engine uses this output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from agent3_evaluator.rules.va26 import ECONOMIC_CRITERIA, ECONOMIC_WEIGHT_SUM, classify_economic


@dataclass
class CriterionScore:
    """Score for one economic criterion."""
    criterion_name: str
    va26_ref: str
    score: int           # 1 (best) to 6 (worst)
    data_source: str      # where the data came from
    evidence: str         # human-readable evidence summary
    is_estimated: bool   # True if score is estimated (data unavailable)
    is_confirmed: bool    # True if based on actual records

    @property
    def grade_label(self) -> str:
        labels = {1: "Excellent", 2: "Good", 3: "Satisfactory",
                   4: "Below average", 5: "Poor", 6: "Very poor"}
        return labels.get(self.score, "Unknown")


@dataclass
class EconomicEvaluationResult:
    """
    Result of VA26 §2.2.2 economic evaluation.
    """
    # Per-criterion scores
    criterion_scores: list[CriterionScore] = field(default_factory=list)

    # Aggregate
    weighted_score: float = 0.0   # Σ(score × weight) / Σ(weights)
    economic_class: str = ""       # "A", "B", or "C"

    # Metadata
    data_sources: dict = field(default_factory=dict)  # what data was used per criterion
    confirmed_count: int = 0       # how many scores are confirmed vs. estimated
    partial: bool = False          # True if any score is estimated

    # Interpretation
    va26_ref: str = "VA26 §2.2.2"
    recommendation: str = ""


def evaluate_economic(
    # From Agent 2
    certifications: list[dict],        # profile_facts category=cert
    nonconformances: list[dict],     # profile_facts category=nc
    purchases: list[dict],          # purchase_history
    audit_facts: list[dict],        # profile_facts category=audit
    profile: dict | None,            # company_profile
    # Human-reported (from intake)
    delivery_issues_reported: bool | None = None,
    cooperation_issues_reported: bool | None = None,
    price_issues_reported: bool | None = None,
) -> EconomicEvaluationResult:
    """
    Compute economic evaluation per VA26 §2.2.2.

    Args:
        certifications: cert facts from Agent 2
        nonconformances: nc facts from Agent 2
        purchases: purchase history from Agent 2
        audit_facts: audit facts from Agent 2
        profile: company_profile from Agent 2
        delivery_issues_reported: human-reported delivery problems
        cooperation_issues_reported: human-reported cooperation problems
        price_issues_reported: human-reported price problems

    Returns:
        EconomicEvaluationResult with per-criterion scores and A/B/C classification.
    """
    result = EconomicEvaluationResult()

    # ── Criterion 1: Overall Quality (weight=2) ─────────────
    # Best: active ISO 13485 + zero NCs
    # Worst: no certs + >3 open NCs
    cert_values = [str(c.get("value", "")) for c in certifications]
    has_iso13485 = any("13485" in v.upper() for v in cert_values)
    has_iso9001 = any("9001" in v.upper() and "13485" not in v.upper() for v in cert_values)
    nc_count = len(nonconformances)

    if has_iso13485 and nc_count == 0:
        q1_score = 1
        q1_evidence = "Active ISO 13485 certificate, zero nonconformances"
        q1_confirmed = True
    elif has_iso13485 and nc_count <= 2:
        q1_score = 2
        q1_evidence = f"Active ISO 13485, {nc_count} nonconformance(s)"
        q1_confirmed = True
    elif has_iso13485:
        q1_score = 3
        q1_evidence = f"Active ISO 13485, {nc_count} nonconformances"
        q1_confirmed = True
    elif has_iso9001 and nc_count == 0:
        q1_score = 2
        q1_evidence = "ISO 9001 (not ISO 13485), zero NCs"
        q1_confirmed = True
    elif nc_count > 3:
        q1_score = 5
        q1_evidence = f"No ISO 13485, {nc_count} open nonconformances"
        q1_confirmed = True
    elif nc_count > 0:
        q1_score = 3
        q1_evidence = f"No ISO 13485, {nc_count} nonconformances"
        q1_confirmed = True
    else:
        q1_score = 4
        q1_evidence = "No ISO 13485, no nonconformances recorded"
        q1_confirmed = True

    result.criterion_scores.append(CriterionScore(
        criterion_name="Overall quality of product/service",
        va26_ref="§2.2.2 #1",
        score=q1_score,
        data_source="Agent 2 profile_facts (cert + nc)",
        evidence=q1_evidence,
        is_estimated=False,
        is_confirmed=q1_confirmed,
    ))

    # ── Criterion 2: Frequency of Complaints (weight=2) ────────
    # Based on NCs relative to purchase volume
    total_purchases = len(purchases)
    nc_from_purchases = sum(1 for p in purchases if p.get("quality_issue", 0))

    if total_purchases == 0:
        # No purchase history → estimate from NC count only
        if nc_count == 0:
            q2_score = 1
            q2_evidence = "Zero complaints, no purchase history"
        else:
            q2_score = 3
            q2_evidence = f"{nc_count} NC(s), no purchase history to normalize"
        q2_estimated = True
    else:
        complaint_rate = nc_from_purchases / total_purchases
        if complaint_rate > 0.30:
            q2_score = 6
        elif complaint_rate > 0.20:
            q2_score = 5
        elif complaint_rate > 0.10:
            q2_score = 4
        elif complaint_rate > 0.05:
            q2_score = 3
        elif complaint_rate > 0:
            q2_score = 2
        else:
            q2_score = 1
        q2_evidence = f"{nc_from_purchases} quality issues / {total_purchases} deliveries ({complaint_rate:.0%})"
        q2_estimated = False

    result.criterion_scores.append(CriterionScore(
        criterion_name="Frequency of complaints",
        va26_ref="§2.2.2 #2",
        score=q2_score,
        data_source="Agent 2 purchase_history (quality_issue flag)",
        evidence=q2_evidence,
        is_estimated=q2_estimated,
        is_confirmed=not q2_estimated,
    ))

    # ── Criterion 3: Delivery Reliability (weight=1) ─────────
    # Based on delivery_status in purchase_history
    if total_purchases == 0:
        q3_score = 3  # neutral — no data
        q3_evidence = "No purchase history — delivery reliability unknown"
        q3_estimated = True
        q3_confirmed = False
    else:
        late_count = sum(
            1 for p in purchases
            if str(p.get("delivery_status", "")).lower() in ("late", "delayed", "failed", "missed")
        )
        late_rate = late_count / total_purchases
        if late_rate > 0.30:
            q3_score = 6
        elif late_rate > 0.20:
            q3_score = 5
        elif late_rate > 0.10:
            q3_score = 4
        elif late_rate > 0.05:
            q3_score = 3
        elif late_rate > 0:
            q3_score = 2
        else:
            q3_score = 1
        q3_evidence = f"{late_count} late/missed of {total_purchases} deliveries ({late_rate:.0%})"
        q3_estimated = False
        q3_confirmed = True

    result.criterion_scores.append(CriterionScore(
        criterion_name="Delivery reliability",
        va26_ref="§2.2.2 #3",
        score=q3_score,
        data_source="Agent 2 purchase_history (delivery_status)",
        evidence=q3_evidence,
        is_estimated=q3_estimated,
        is_confirmed=q3_confirmed,
    ))

    # ── Criterion 4: Offer Creation Speed (weight=1) ──────────
    # Agent 2 doesn't store offer timing — this is estimated
    # In a full implementation: track RFQ → quote turnaround in purchase_history
    q4_score = 3
    q4_evidence = "Offer creation speed not tracked in Agent 2 — estimated as neutral"
    if delivery_issues_reported:
        q4_score = 4
        q4_evidence = "Reported: slow offer response times"
    result.criterion_scores.append(CriterionScore(
        criterion_name="Offer creation speed",
        va26_ref="§2.2.2 #4",
        score=q4_score,
        data_source="Not captured in Agent 2" + (" (human-reported)" if delivery_issues_reported else " — estimated"),
        evidence=q4_evidence,
        is_estimated=True,
        is_confirmed=False,
    ))

    # ── Criterion 5: Prices (weight=1) ────────────────────────
    # Agent 2 doesn't store pricing benchmarks — estimated
    if total_purchases > 0:
        amounts = [p.get("amount") for p in purchases if p.get("amount")]
        if len(amounts) >= 2:
            avg = sum(amounts) / len(amounts)
            variance = max(amounts) / min(amounts) if min(amounts) > 0 else 1.0
            # High variance = inconsistent pricing
            if variance > 2.0:
                q5_score = 4
                q5_evidence = f"Price variance: {variance:.1f}x — high inconsistency"
            elif variance > 1.3:
                q5_score = 3
                q5_evidence = f"Price variance: {variance:.1f}x — moderate"
            else:
                q5_score = 2
                q5_evidence = f"Stable pricing, variance: {variance:.1f}x"
            q5_estimated = False
        else:
            q5_score = 3
            q5_evidence = f"Limited purchase history ({len(amounts)} records) — estimated"
            q5_estimated = True
    else:
        q5_score = 3
        q5_evidence = "No purchase history — price assessment not available"
        q5_estimated = True

    if price_issues_reported:
        q5_score = min(q5_score + 1, 6)
        q5_evidence += " (adjusted: price issues reported)"

    result.criterion_scores.append(CriterionScore(
        criterion_name="Prices",
        va26_ref="§2.2.2 #5",
        score=q5_score,
        data_source="Agent 2 purchase_history (amount)" + (" (human-reported)" if price_issues_reported else ""),
        evidence=q5_evidence,
        is_estimated=q5_estimated,
        is_confirmed=not q5_estimated,
    ))

    # ── Criterion 6: Cooperation (weight=1) ───────────────────
    # Based on audit findings and NC open status
    if audit_facts:
        # Count unresolved audit findings (would need status field)
        finding_count = len(audit_facts)
        if finding_count == 0:
            q6_score = 1
            q6_evidence = f"{finding_count} audit findings"
        else:
            q6_score = 3
            q6_evidence = f"{finding_count} audit finding(s) on record"
        q6_estimated = False
    elif nonconformances:
        open_ncs = [n for n in nonconformances if not n.get("valid_until")]
        if len(open_ncs) > 3:
            q6_score = 5
            q6_evidence = f"{len(open_ncs)} open nonconformances affecting cooperation"
            q6_estimated = False
        elif len(open_ncs) > 0:
            q6_score = 3
            q6_evidence = f"{len(open_ncs)} open nonconformance(s)"
            q6_estimated = False
        else:
            q6_score = 2
            q6_evidence = "No audit findings, nonconformances resolved"
            q6_estimated = False
    else:
        q6_score = 3
        q6_evidence = "Cooperation assessment not available — estimated"
        q6_estimated = True

    if cooperation_issues_reported:
        q6_score = min(q6_score + 1, 6)
        q6_evidence += " (adjusted: cooperation issues reported)"

    result.criterion_scores.append(CriterionScore(
        criterion_name="Cooperation",
        va26_ref="§2.2.2 #6",
        score=q6_score,
        data_source=(
            "Agent 2 profile_facts (audit) + nc facts"
            + (" (human-reported)" if cooperation_issues_reported else "")
        ),
        evidence=q6_evidence,
        is_estimated=q6_estimated,
        is_confirmed=not q6_estimated,
    ))

    # ── Compute weighted average ──────────────────────────────
    total_weighted = 0.0
    for criterion, score in zip(ECONOMIC_CRITERIA, [
        q1_score, q2_score, q3_score, q4_score, q5_score, q6_score
    ]):
        total_weighted += criterion.weight * score

    result.weighted_score = round(total_weighted / ECONOMIC_WEIGHT_SUM, 2)
    result.economic_class = classify_economic(result.weighted_score).letter

    # ── Metadata ───────────────────────────────────────────────
    result.confirmed_count = sum(1 for c in result.criterion_scores if c.is_confirmed)
    result.partial = any(c.is_estimated for c in result.criterion_scores)

    # ── Recommendation ─────────────────────────────────────────
    class_label = {
        "A": "A-Supplier (1.0–3.0) — Continue cooperation, consider strategic partnership",
        "B": "B-Supplier (3.1–5.0) — Monitor, address specific weaknesses",
        "C": "C-Supplier (5.1–6.0) — Require corrective action plan, consider alternatives",
    }.get(result.economic_class, "")

    result.recommendation = class_label

    return result


def format_economic_result(result: EconomicEvaluationResult) -> str:
    """Format economic evaluation as a human-readable table."""
    lines = []
    lines.append("\n  ── VA26 §2.2.2 Economic Evaluation ─────────────────────────")
    lines.append(f"  Weighted Score: {result.weighted_score:.2f}")
    lines.append(f"  Classification: {result.economic_class}-Supplier")
    lines.append(f"  Data: {result.confirmed_count}/{len(ECONOMIC_CRITERIA)} criteria confirmed"
                 + (" (PARTIAL — estimated)" if result.partial else ""))
    lines.append(f"  {'─' * 60}")
    lines.append(f"  {'Criterion':<38} {'Score':>5}  {'Evidence'}")
    lines.append(f"  {'─' * 60}")

    for cs in result.criterion_scores:
        icon = "✓" if cs.score <= 3 else "~" if cs.score <= 4 else "✗"
        est = " [EST]" if cs.is_estimated else ""
        lines.append(
            f"  {icon} {cs.criterion_name:<36} {cs.score}/6{est}"
        )
        lines.append(f"     {cs.evidence}")

    lines.append(f"  {'─' * 60}")
    lines.append(f"  → {result.recommendation}")
    return "\n".join(lines)
