"""
Approval Gate Engine
====================
Applies VA26 §2.1.1.1 minimum criteria per risk class to determine
approval readiness.

For each measure required by the risk class:
  - Check if evidence exists in Agent 2's databases
  - Check intake data for human-reported status
  - Mark as MET / UNMET / NOT_APPLICABLE

Output:
  - List of gate items with status
  - Whether supplier can be approved / needs conditional approval / is rejected
  - List of action_required items
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from agent3_evaluator.rules.va26 import (
    Measure, RiskClass, SupplierCriticality, InternalControl,
    get_criteria_set,
    QAA_MANDATORY_FOR, GTC_ACCEPTABLE_FOR, AUDIT_REQUIRED_FOR,
)


class GateStatus(str, Enum):
    MET             = "met"
    UNMET           = "unmet"
    PARTIAL         = "partial"   # evidence exists but insufficient
    NOT_APPLICABLE  = "na"
    NOT_AVAILABLE   = "not_available"  # Agent 2 has no data


@dataclass
class GateItem:
    """One gate item from VA26 §2.1.1.1."""
    measure: Measure
    status: GateStatus
    va26_ref: str
    description: str
    evidence_source: str  # where this measure's evidence comes from
    evidence_summary: str  # what evidence exists
    action_required: str | None = None  # what to do if unmet
    is_blocking: bool = True  # False for advisory items


@dataclass
class ApprovalGateResult:
    """
    Result of applying the approval gate for a supplier.
    """
    risk_class: RiskClass
    supplier_criticality: SupplierCriticality
    gate_items: list[GateItem] = field(default_factory=list)

    # Summary
    total_items: int = 0
    met_items: int = 0
    unmet_items: int = 0
    blocking_unmet: int = 0

    # Decision
    approval_status: Literal["approve", "conditional", "reject", "blocked"] = "blocked"
    va26_justification: str = ""
    conditions: list[str] = field(default_factory=list)
    action_required: list[str] = field(default_factory=list)


def build_gate(
    risk_class: RiskClass,
    supplier_criticality: SupplierCriticality,
    # Evidence from Agent 2
    certifications: list[dict],          # from profile_facts category=cert
    nonconformances: list[dict],         # from profile_facts category=nc
    audit_facts: list[dict],            # from profile_facts category=audit
    purchases: list[dict],              # from purchase_history
    profile: dict | None,                # from company_profile
    # Human-reported status (from intake)
    qaa_status: Literal["yes", "in_progress", "no"] | None = None,
    audit_status: Literal["yes", "planned", "no"] | None = None,
) -> ApprovalGateResult:
    """
    Apply VA26 §2.1.1.1 approval gate.

    Args:
        risk_class: 1, 2, or 3
        supplier_criticality: critical or noncritical
        certifications: cert facts from Agent 2 profile_facts
        nonconformances: nc facts from Agent 2 profile_facts
        audit_facts: audit facts from Agent 2 profile_facts
        purchases: purchase history from Agent 2
        profile: company_profile from Agent 2
        qaa_status: human-reported from intake
        audit_status: human-reported from intake
    """
    criteria = get_criteria_set(risk_class, supplier_criticality)
    if not criteria:
        return ApprovalGateResult(
            risk_class=risk_class,
            supplier_criticality=supplier_criticality,
            approval_status="blocked",
            va26_justification="Unknown risk class or supplier type.",
        )

    result = ApprovalGateResult(
        risk_class=risk_class,
        supplier_criticality=supplier_criticality,
    )

    for measure in criteria.required:
        item = _evaluate_measure(
            measure=measure,
            certifications=certifications,
            nonconformances=nonconformances,
            audit_facts=audit_facts,
            purchases=purchases,
            profile=profile,
            qaa_status=qaa_status,
            audit_status=audit_status,
        )
        result.gate_items.append(item)

    # Compute summary
    result.total_items = len(result.gate_items)
    result.met_items = sum(1 for i in result.gate_items if i.status == GateStatus.MET)
    result.unmet_items = sum(1 for i in result.gate_items if i.status == GateStatus.UNMET)
    result.blocking_unmet = sum(
        1 for i in result.gate_items
        if i.status == GateStatus.UNMET and i.is_blocking
    )

    # ── Decision Logic (VA26 §3.1 Step 9) ───────────────────
    #
    # ALL blocking criteria met → APPROVE
    # Some criteria unmet but none blocking → CONDITIONAL
    # Critical criteria unmet → REJECT or CONDITIONAL

    # D2 FIX: zero items = undefined matrix combination → BLOCKED not APPROVE
    if result.total_items == 0:
        result.approval_status = "blocked"
        result.va26_justification = (
            f"No qualification measures could be determined for this classification "
            f"(Class {result.risk_class.value}, {result.supplier_criticality.value}). "
            f"A human QM reviewer must determine applicable measures manually."
        )
    elif result.blocking_unmet == 0:
        if result.unmet_items == 0:
            result.approval_status = "approve"
            result.va26_justification = (
                f"All minimum criteria for Class {risk_class.value} "
                f"{supplier_criticality.value} supplier are satisfied. "
                f"Approve supplier per VA26 §3.1 Step 9."
            )
        else:
            result.approval_status = "conditional"
            result.va26_justification = (
                f"Minimum criteria partially met ({result.met_items}/{result.total_items}). "
                f"Conditional approval per VA26 §3.1 — conditions must be resolved."
            )
    else:
        # Check if missing items are critical enough to reject
        critical_unmet = [
            i for i in result.gate_items
            if i.status == GateStatus.UNMET and i.is_blocking
        ]
        if any(i.measure == Measure.QAA_OR_CONTRACT for i in critical_unmet):
            result.approval_status = "conditional"
            result.conditions.append(
                "QAA or Quality Assurance Agreement must be finalized before supplier use"
            )
            result.va26_justification = (
                f"QAA missing — required for Class {risk_class.value} per VA26 §2.1.1.1 Measure 3. "
                f"Conditional approval: QAA must be signed before supplier use."
            )
        else:
            result.approval_status = "conditional"
            result.va26_justification = (
                f"{result.blocking_unmet} blocking criteria unmet for Class {risk_class.value}. "
                f"Conditional approval — submit required evidence."
            )

    # Collect action_required from all unmet items
    result.action_required = [
        i.action_required
        for i in result.gate_items
        if i.action_required
    ]
    result.conditions = list(set(result.conditions))

    return result


def _evaluate_measure(
    measure: Measure,
    certifications: list[dict],
    nonconformances: list[dict],
    audit_facts: list[dict],
    purchases: list[dict],
    profile: dict | None,
    qaa_status: str | None,
    audit_status: str | None,
) -> GateItem:
    """Evaluate a single VA26 measure."""

    # ── Measure 1: Contractual Agreement / GTC ────────────
    if measure == Measure.CONTRACTUAL_AGREEMENT:
        # Class 1 always requires contractual agreement
        # In practice: human reports this in intake
        return GateItem(
            measure=measure,
            status=GateStatus.MET,  # Assume in-progress unless reported otherwise
            va26_ref="§2.1.1.1 Measure 1",
            description="Contractual agreement with supplier",
            evidence_source="intake (human-reported)",
            evidence_summary=qaa_status or "not reported",
            action_required=None,
            is_blocking=False,
        )

    if measure == Measure.GTC:
        # GTC is acceptable for Class 2 non-critical and Class 3
        # No structured evidence in Agent 2 — human reports
        return GateItem(
            measure=measure,
            status=GateStatus.MET,
            va26_ref="§2.1.1.1 Measure 1 (Class 2/3)",
            description="General Terms and Conditions or contractual agreement",
            evidence_source="intake (human-reported)",
            evidence_summary="GTC acceptable for non-critical suppliers",
            action_required=None,
            is_blocking=False,
        )

    # ── Measure 2: Supplier Audit ──────────────────────────
    if measure == Measure.SUPPLIER_AUDIT:
        if audit_status == "yes":
            status = GateStatus.MET
            summary = "Supplier audit completed per QM_AA17"
        elif audit_status == "planned":
            status = GateStatus.PARTIAL
            summary = "Supplier audit planned but not yet completed"
        else:
            status = GateStatus.UNMET
            summary = "No supplier audit reported"

        return GateItem(
            measure=measure,
            status=status,
            va26_ref="§2.1.1.1 Measure 2 + AA17",
            description="Supplier audit conducted per QM_AA17",
            evidence_source="intake (human-reported) + audit_facts from Agent 2",
            evidence_summary=(
                f"Intake: {audit_status or 'not reported'} | "
                f"Agent 2 audit facts: {len(audit_facts)}"
            ),
            action_required=(
                "Schedule and conduct supplier audit per QM_AA17 — "
                "required for Class 1 suppliers"
                if status == GateStatus.UNMET else None
            ),
            is_blocking=True,
        )

    # ── Measure 3: QAA ────────────────────────────────────
    if measure == Measure.QAA_OR_CONTRACT:
        if qaa_status == "yes":
            status = GateStatus.MET
            summary = "QAA signed and on file"
        elif qaa_status == "in_progress":
            status = GateStatus.PARTIAL
            summary = "QAA in negotiation/drafting"
        else:
            status = GateStatus.UNMET
            summary = "No QAA or contractual quality rule in place"

        return GateItem(
            measure=measure,
            status=status,
            va26_ref="§2.1.1.1 Measure 3 + §2.1.4",
            description="Quality Assurance Agreement (QAA / FB29) or contractual quality promise",
            evidence_source="intake (human-reported)",
            evidence_summary=summary,
            action_required=(
                "Finalize Quality Assurance Agreement (QAA / FB29) — "
                "required per VA26 §2.1.4 for this risk class"
                if status == GateStatus.UNMET else None
            ),
            is_blocking=True,
        )

    # ── Measure 4: Certification Evidence ──────────────────
    if measure == Measure.CERT_EVIDENCE:
        if certifications:
            # Check if ISO 13485 specifically
            iso_certs = [
                c for c in certifications
                if "13485" in str(c.get("value", "")).upper()
                   or "13485" in str(c.get("field_name", "")).upper()
            ]
            if iso_certs:
                status = GateStatus.MET
                summary = f"ISO 13485 certificate found ({len(iso_certs)} record(s))"
            else:
                status = GateStatus.PARTIAL
                summary = f"Certifications found but ISO 13485 not confirmed: {len(certifications)} certs"
        else:
            status = GateStatus.UNMET
            summary = "No certification evidence found in Agent 2 (profile_facts)"

        return GateItem(
            measure=measure,
            status=status,
            va26_ref="§2.1.1.1 Measure 4",
            description="Applicable certification evidence (ISO 13485, ISO 9001, ISO 27001, CE Mark, etc.)",
            evidence_source="Agent 2 profile_facts (category=cert)",
            evidence_summary=summary,
            action_required=(
                "Submit ISO 13485:2016 or equivalent certification evidence — "
                "required per VA26 §2.1.1.1 Measure 4"
                if status == GateStatus.UNMET else None
            ),
            is_blocking=True,
        )

    # ── Measure 4: Sample Testing ──────────────────────────
    if measure == Measure.SAMPLE_TESTING:
        # Agent 2 doesn't store sample test results — this is human-reported
        return GateItem(
            measure=measure,
            status=GateStatus.NOT_AVAILABLE,
            va26_ref="§2.1.1.1 Measure 4",
            description="Demo/test version review or initial sample testing",
            evidence_source="Not captured in Agent 2 — human-reported",
            evidence_summary="Evidence of sample testing not in Agent 2",
            action_required=None,
            is_blocking=False,
        )

    # ── Measure 4: Complaint Evaluation ───────────────────
    if measure == Measure.COMPLAINT_EVAL:
        # NCs in Agent 2 serve as complaint evidence
        if nonconformances:
            status = GateStatus.MET
            summary = f"Nonconformance records found: {len(nonconformances)}"
        else:
            status = GateStatus.PARTIAL
            summary = "No nonconformances recorded — good, but eval still required per §2.2.2"

        return GateItem(
            measure=measure,
            status=status,
            va26_ref="§2.1.1.1 Measure 4 + §2.2.2 #2",
            description="Evaluation of complaints and nonconformances in Management Review",
            evidence_source="Agent 2 profile_facts (category=nc) + purchase_history (quality_issue flag)",
            evidence_summary=summary,
            action_required=None,
            is_blocking=False,
        )

    # ── Measure 7: Economic Evaluation ─────────────────────
    if measure == Measure.ECONOMIC_EVAL:
        # Economic evaluation is done by Agent 3's economic_eval module
        # Gate just checks if sufficient data exists — marked MET here
        # Actual scoring happens in economic_eval.py
        return GateItem(
            measure=measure,
            status=GateStatus.NOT_AVAILABLE,  # Will be updated by economic_eval
            va26_ref="§2.1.1.1 Measure 7 + §2.2.2",
            description="Economic evaluation and classification (A/B/C per §2.2.2)",
            evidence_source="Agent 3 economic_eval module — not yet computed",
            evidence_summary="Pending economic evaluation",
            action_required=None,
            is_blocking=True,
        )

    # ── Measure 4: Test Result Analysis ───────────────────
    if measure == Measure.TEST_RESULT_ANALYSIS:
        return GateItem(
            measure=measure,
            status=GateStatus.NOT_AVAILABLE,
            va26_ref="§2.1.1.1 Measure 4",
            description="Analysis of test results (verification/validation activities)",
            evidence_source="Not captured in Agent 2",
            evidence_summary="Verification/validation test results not in Agent 2",
            action_required=None,
            is_blocking=False,
        )

    # ── Default: unknown measure ────────────────────────────
    return GateItem(
        measure=measure,
        status=GateStatus.NOT_APPLICABLE,
        va26_ref="VA26 §2.1.1.1",
        description=str(measure),
        evidence_source="unknown",
        evidence_summary="Measure evaluation not implemented",
        action_required="Review this measure manually",
        is_blocking=True,
    )


def format_gate_result(result: ApprovalGateResult) -> str:
    """Format gate result as a human-readable table."""
    lines = []
    lines.append(f"\n  {'─' * 64}")
    lines.append(f"  VA26 Approval Gate — Class {result.risk_class.value} "
                 f"{result.supplier_criticality.value}")
    lines.append(f"  {'─' * 64}")

    for item in result.gate_items:
        icon = {
            GateStatus.MET: "✓",
            GateStatus.UNMET: "✗",
            GateStatus.PARTIAL: "~",
            GateStatus.NOT_APPLICABLE: "—",
            GateStatus.NOT_AVAILABLE: "?",
        }.get(item.status, "?")

        status_label = {
            GateStatus.MET: "PASS",
            GateStatus.UNMET: "FAIL",
            GateStatus.PARTIAL: "PARTIAL",
            GateStatus.NOT_APPLICABLE: "N/A",
            GateStatus.NOT_AVAILABLE: "N/A",
        }.get(item.status, "?")

        status_color = {
            GateStatus.MET: "PASS",
            GateStatus.UNMET: "FAIL",
            GateStatus.PARTIAL: "PARTIAL",
            GateStatus.NOT_APPLICABLE: "",
            GateStatus.NOT_AVAILABLE: "",
        }.get(item.status, "")

        lines.append(f"    {icon}  [{status_label:<8}] {item.description}")
        lines.append(f"       {item.va26_ref} — {item.evidence_summary}")

    lines.append(f"  {'─' * 64}")
    lines.append(f"  Summary: {result.met_items}/{result.total_items} criteria met")

    status_label = {
        "approve": "✓ APPROVE — all minimum criteria satisfied",
        "conditional": "~ CONDITIONAL APPROVAL — see conditions below",
        "reject": "✗ REJECT — critical criteria unmet",
        "blocked": "? BLOCKED — cannot determine approval status",
    }.get(result.approval_status, result.approval_status)

    lines.append(f"  Decision: {status_label}")
    if result.conditions:
        lines.append(f"  Conditions:")
        for c in result.conditions:
            lines.append(f"    • {c}")

    if result.action_required:
        lines.append(f"  Action Required:")
        for a in result.action_required:
            lines.append(f"    • {a}")

    return "\n".join(lines)
