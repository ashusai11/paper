"""
VA26 Risk Classifier
===================
Applies the VA26 §2.1.5 decision tree to determine risk class.

Inputs:
  - is_ready_to_sell_md: bool
  - is_critical_for_safety: bool
  - is_critical_for_performance: bool
  - is_critical_for_qms: bool
  - internal_control_level: "high" | "low"
  - supplier_type: from intake (material/service/etc.)

Output:
  - RiskClass (1/2/3)
  - SupplierCriticality (critical/noncritical)
  - InternalControl (high/low)
  - justification: str (VA26 reference)

This is entirely deterministic — VA26 defines exact rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agent3_evaluator.rules.va26 import RiskClass, SupplierCriticality, InternalControl


@dataclass
class ClassificationResult:
    """Result of applying VA26 §2.1.5 decision tree."""
    risk_class: RiskClass
    supplier_criticality: SupplierCriticality
    internal_control: InternalControl
    justification: str
    va26_reference: str = "VA26 §2.1.5"
    decision_path: str = ""  # Human-readable trace of which rule applied


def classify(
    *,
    is_ready_to_sell_md: bool | None,
    is_critical_safety: bool | None,
    is_critical_perf: bool | None,
    is_critical_qms: bool | None,
    internal_control: Literal["high", "low"] | None,
    supplier_type: str | None = None,
) -> ClassificationResult:
    """
    Apply VA26 §2.1.5 decision tree.

    Decision order (per flowchart §2.1.5):
      1. Is it a ready-to-sell medical device?
         YES → Class 1 (Critical)

      2. Is it critical? (safety OR performance OR QMS)
         NO  → Class 3 (Non-critical)

      3. If critical:
         LOW  internal control → Class 1 (Critical)
         HIGH internal control → Class 2 (Critical)

    Args:
        is_ready_to_sell_md: Is it approved as an independent medical device?
        is_critical_safety: Would failure alone compromise safety?
        is_critical_perf: Would failure in combination compromise performance?
        is_critical_qms: Does the service directly influence QM conformity?
        internal_control: LOW or HIGH per §2.1.5 criteria
        supplier_type: material / service / outsourced_process / economic_operator

    Returns:
        ClassificationResult with risk class, justification, and VA26 reference.

    Raises:
        ValueError: If required fields are None (risk class cannot be determined).
    """
    # ── Step 1: Ready-to-sell medical device ───────────────
    if is_ready_to_sell_md is True:
        return ClassificationResult(
            risk_class=RiskClass.CLASS_1,
            supplier_criticality=SupplierCriticality.CRITICAL,
            internal_control=InternalControl.LOW,  # implied by Q1
            justification=(
                "Class 1 — Ready-to-sell medical device. "
                "Per VA26 §2.1.5: 'Is it approved as an independent medical device? "
                "Or is it delivered to the customer as an independent medical device?' → YES"
            ),
            decision_path=(
                "Q1 (ready-to-sell MD): YES → Class 1 immediately"
            ),
        )

    if is_ready_to_sell_md is None:
        raise ValueError(
            "is_ready_to_sell_md is required to determine risk class (VA26 §2.1.5 Q1)"
        )

    # ── Step 2: Is it critical? ───────────────────────────
    # Critical if ANY of the three criteria is true
    is_critical = any([
        is_critical_safety is True,
        is_critical_perf is True,
        is_critical_qms is True,
    ])

    # If any criticality field is None, we can't fully determine
    criticality_fields = [is_critical_safety, is_critical_perf, is_critical_qms]
    if None in criticality_fields and not is_critical:
        # We can't say it's critical (no True found) but some fields are unanswered
        raise ValueError(
            "Criticality assessment incomplete. "
            f"is_critical_safety={is_critical_safety}, "
            f"is_critical_perf={is_critical_perf}, "
            f"is_critical_qms={is_critical_qms}. "
            "All three must be answered per VA26 §2.1.5 Q2-Q4."
        )

    if not is_critical:
        # NOT critical → Class 3
        return ClassificationResult(
            risk_class=RiskClass.CLASS_3,
            supplier_criticality=SupplierCriticality.NONCRITICAL,
            internal_control=InternalControl.LOW,  # Class 3 doesn't use internal control
            justification=(
                f"Class 3 — Not critical for safety, performance, or QMS. "
                f"(Safety: {is_critical_safety}, Performance: {is_critical_perf}, "
                f"QMS: {is_critical_qms}). "
                f"Per VA26 §2.1.5: 'Non-critical material, product, or service' → Class 3"
            ),
            decision_path=(
                f"Q2-Q4 (is critical): NO "
                f"(Safety={is_critical_safety}, Perf={is_critical_perf}, QMS={is_critical_qms}) "
                "→ NOT critical → Class 3"
            ),
        )

    # ── Step 3: Internal control level ────────────────────
    if internal_control is None:
        raise ValueError(
            "internal_control is required when supplier is critical (VA26 §2.1.5). "
            "Determine: HIGH (additional internal tests / service integrated into QMS) "
            "or LOW (tested against specs only / service not integrated into QMS)."
        )

    if internal_control == "low":
        return ClassificationResult(
            risk_class=RiskClass.CLASS_1,
            supplier_criticality=SupplierCriticality.CRITICAL,
            internal_control=InternalControl.LOW,
            justification=(
                f"Class 1 — Critical (Safety={is_critical_safety}, "
                f"Performance={is_critical_perf}, QMS={is_critical_qms}) "
                f"WITH LOW internal control. "
                f"Per VA26 §2.1.5: 'Critical material/product/service "
                f"AND LOW internal control' → Class 1"
            ),
            decision_path=(
                f"Q2-Q4: CRITICAL "
                f"(Safety={is_critical_safety}, Perf={is_critical_perf}, QMS={is_critical_qms}) "
                f"| Q5 (internal control): {internal_control} → Class 1"
            ),
        )

    # HIGH internal control → Class 2
    return ClassificationResult(
        risk_class=RiskClass.CLASS_2,
        supplier_criticality=SupplierCriticality.CRITICAL,
        internal_control=InternalControl.HIGH,
        justification=(
            f"Class 2 — Critical (Safety={is_critical_safety}, "
            f"Performance={is_critical_perf}, QMS={is_critical_qms}) "
            f"WITH HIGH internal control. "
            f"Per VA26 §2.1.5: 'Critical material/product/service "
            f"AND HIGH internal control' → Class 2"
        ),
        decision_path=(
            f"Q2-Q4: CRITICAL "
            f"(Safety={is_critical_safety}, Perf={is_critical_perf}, QMS={is_critical_qms}) "
            f"| Q5 (internal control): {internal_control} → Class 2"
        ),
    )


def is_critical_from_answers(
    safety: bool | None,
    perf: bool | None,
    qms: bool | None,
) -> bool | None:
    """Check if supplier is critical given three answers. Returns None if indeterminate."""
    if any(v is None for v in [safety, perf, qms]):
        return None
    return any([safety, perf, qms])
