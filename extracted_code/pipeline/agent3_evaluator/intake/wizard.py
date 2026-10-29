"""
Interactive Intake Wizard
=========================
VA26-guided intake that ONLY asks questions where:
  1. Data is not in Agent 2's databases
  2. VA26 requires human judgment
  3. A prior intake record is incomplete

The wizard scans Agent 2 FIRST, then asks only the gaps.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from agent3_evaluator.intake.audit import audit_agent2_state, build_gap_report, format_gap_report_text, GapReport
from agent3_evaluator.intake.risk_classifier import classify, ClassificationResult
from agent3_evaluator.intake.gate_engine import build_gate, format_gate_result
from agent3_evaluator.intake.store import EvaluatorStore
from agent3_evaluator.evaluation.economic import evaluate_economic, format_economic_result


def _print(text: str = ""):
    print(text)


def _ask(prompt: str, options: list[str], descriptions: list[str] | None = None) -> str:
    """
    Ask a multiple-choice question.

    Args:
        prompt: Question text
        options: List of option strings (e.g. ["yes", "no"])
        descriptions: Optional list of descriptions for each option

    Returns:
        The selected option string
    """
    while True:
        _print(f"\n  {prompt}")
        if descriptions:
            for opt, desc in zip(options, descriptions):
                print(f"    [{opt}] {desc}")
        else:
            for opt in options:
                print(f"    [{opt}] {opt}")

        answer = input("\n  > ").strip().lower()
        if answer in options:
            return answer
        _print(f"  Invalid choice. Options: {', '.join(options)}")


def _ask_yn(prompt: str) -> bool:
    """Ask a yes/no question."""
    answer = _ask(
        prompt,
        options=["y", "n"],
        descriptions=["Yes", "No"],
    )
    return answer == "y"


def _ask_3way(
    prompt: str,
    descriptions: list[str] | None = None,
) -> str:
    """
    Ask a 3-way choice (yes / no / uncertain).
    Returns: "yes", "no", or "uncertain"
    """
    opts = ["yes", "no", "uncertain"]
    descs = descriptions or [
        "Yes — there is a risk",
        "No — there is no risk",
        "Uncertain — need more information",
    ]
    return _ask(prompt, opts, descs)


def run_wizard(
    supplier_id: str,
    agent2_db: str | Path = "agent2_vectorstore/data/supplier_risk.db",
    chroma_dir: str | Path = "agent2_vectorstore/data/chroma",
    store: EvaluatorStore | None = None,
) -> dict:
    """
    Run the interactive intake wizard.

    Steps:
      1. Scan Agent 2 databases → show gap report
      2. Determine which questions still need answers
      3. Ask only the missing questions, with VA26 references
      4. Compute risk class live after each answer
      5. Save intake record to store
      6. Return full intake data dict

    Returns:
        Full intake data dict (same structure as HTML wizard output)
    """
    if store is None:
        store = EvaluatorStore()

    _print("\n" + "=" * 70)
    _print(f"  AGENT 3 — VA26 Supplier Intake Wizard")
    _print(f"  Supplier: {supplier_id}")
    _print("=" * 70)

    # ── Step 0: Check Agent 2 state ──────────────────────────
    _print("\n  [1/5] Scanning Agent 2 databases...")
    state = audit_agent2_state(supplier_id, agent2_db, chroma_dir)

    # ── Step 1: Load or create intake ───────────────────────
    _print("  [2/5] Checking existing intake records...")
    existing = store.get_intake(supplier_id)

    intake = {
        "intake_version": "1.0",
        "supplier_id": supplier_id,
        "supplier_name": state.supplier_name,
        "intake_date": "",
        "status": "incomplete",
        "procurement_desc": "",
        "procurement_purpose": "",
        "procurement_spec": "",
        "docs_received": [],
        "docs_missing": [],
        "is_ready_to_sell_md": None,
        "is_critical_safety": None,
        "is_critical_perf": None,
        "is_critical_qms": None,
        "internal_control": None,
        "qaa_status": None,
        "audit_status": None,
        "supplier_type_ref": None,
        "risk_class": None,
        "risk_class_type": None,
        "is_critical": None,
        "va26_justification": "",
    }

    if existing:
        _print(f"  Found existing intake from {existing.get('intake_date', 'unknown')}")
        _print(f"  Status: {existing.get('status', 'unknown')}")
        _print(f"  Risk class: {existing.get('risk_class') or 'not yet determined'}")

        # Merge existing into intake
        for key in intake:
            if existing.get(key) not in (None, ""):
                intake[key] = existing[key]

        if existing.get("docs_received"):
            intake["docs_received"] = existing["docs_received"]

    # ── Step 2: Show gap report ──────────────────────────────
    _print("\n  [3/5] VA26 Compliance Audit:")
    gap = build_gap_report(supplier_id, state, existing)

    if gap.evaluation_blocked:
        _print(format_gap_report_text(gap))

    # ── Step 3: Ask only missing questions ───────────────────
    _print("\n  [4/5] Intake Questions (VA26-guided)")
    _print("  ─────────────────────────────────────────────────────────────")
    _print("  Answer the questions below. Each question is required by VA26")
    _print("  and cannot be determined from supplier documents alone.")
    _print("  VA26 section references are shown for your records.\n")

    # Q1: Procurement description
    if not intake.get("procurement_desc"):
        _print("  QUESTION 1 of ~7 — VA26 §3.1 Step 1")
        _print("  What product or service is being procured from this supplier?")
        _print("  (Describe what is being bought — e.g. 'Calibration service for QC lab equipment')")
        desc = input("  > ").strip()
        if desc:
            intake["procurement_desc"] = desc
        _print("")

    # Q2: Ready-to-sell medical device
    if intake.get("is_ready_to_sell_md") is None:
        _print("  QUESTION 2 of ~7 — VA26 §2.1.5 Q1")
        _print("  Is this supplier delivering a READY-TO-SELL MEDICAL DEVICE?")
        _print("  (Approved as an independent medical device, or delivered to")
        _print("   customers as a standalone device — e.g. a sub-assembly that")
        _print("   is itself CE-marked as a medical device?)")
        _print("")
        print("    [yes]  YES — it is an approved standalone medical device")
        print("    [no]   NO  — it is a component, material, or service")
        answer = input("    > ").strip().lower()
        if answer == "yes":
            intake["is_ready_to_sell_md"] = True
        elif answer == "no":
            intake["is_ready_to_sell_md"] = False
        _print("")

    # If ready-to-sell = YES → Class 1 immediately, skip criticality questions
    if intake.get("is_ready_to_sell_md") is True:
        _print("  → Ready-to-sell MD: Class 1 (Critical) — no further")
        _print("    criticality questions needed.")
        try:
            result = classify(
                is_ready_to_sell_md=True,
                is_critical_safety=None,
                is_critical_perf=None,
                is_critical_qms=None,
                internal_control=None,
            )
            intake["risk_class"] = result.risk_class.value
            intake["risk_class_type"] = "Critical"
            intake["is_critical"] = True
            intake["va26_justification"] = result.justification
            _print(f"  Computed: {result.risk_class.value} — {result.supplier_criticality.value}")
            _print(f"  {result.justification}")
        except ValueError:
            pass
    else:
        # Q3-5: Criticality assessment
        criticality_qs = [
            ("is_critical_safety", "Is the supplier's product/service CRITICAL FOR SAFETY?",
             "Would a failure of this item ALONE compromise the safety of patients, users, or third parties?\n"
             "  e.g. A faulty component in an implanted device, contaminated sterile packaging.",
             "VA26 §2.1.5 Q2 — Critical for Safety"),
            ("is_critical_perf", "Is the supplier's product/service CRITICAL FOR PERFORMANCE?",
             "Would a failure, in combination with other failures, compromise the PERFORMANCE of your medical device?\n"
             "  e.g. A substandard raw material that degrades device performance over time.",
             "VA26 §2.1.5 Q3 — Critical for Performance"),
            ("is_critical_qms", "Is the supplier's product/service CRITICAL FOR YOUR QMS?",
             "Does the supplier's activity directly influence the conformity of your QMS or your products?\n"
             "  e.g. Calibration service, sterilization, contract manufacturing, QMS consultant.",
             "VA26 §2.1.5 Q4 — Critical for QMS"),
        ]

        for field_key, question, context, va26_ref in criticality_qs:
            if intake.get(field_key) is None:
                _print(f"  QUESTION — {va26_ref}")
                _print(f"  {question}")
                _print(f"  {context}")
                print("")
                print(f"    [yes]  YES — this is a critical item")
                print(f"    [no]   NO  — this is not a critical item")
                answer = input("    > ").strip().lower()
                if answer == "yes":
                    intake[field_key] = True
                elif answer == "no":
                    intake[field_key] = False
                _print("")

        # Determine if critical
        is_critical = any([
            intake.get("is_critical_safety") is True,
            intake.get("is_critical_perf") is True,
            intake.get("is_critical_qms") is True,
        ])
        intake["is_critical"] = is_critical

        # If NOT critical → Class 3 — skip internal control
        if not is_critical:
            _print("  → Not critical: Class 3 (Non-critical) — no internal control")
            _print("    questions needed. Proceeding to QAA/Audit.")
            try:
                result = classify(
                    is_ready_to_sell_md=False,
                    is_critical_safety=intake.get("is_critical_safety"),
                    is_critical_perf=intake.get("is_critical_perf"),
                    is_critical_qms=intake.get("is_critical_qms"),
                    internal_control=None,
                )
                intake["risk_class"] = result.risk_class.value
                intake["risk_class_type"] = result.supplier_criticality.value
                intake["va26_justification"] = result.justification
                _print(f"  Computed: Class {result.risk_class.value} — {result.supplier_criticality.value}")
            except ValueError:
                _print(f"  Warning: {e}")
        else:
            # Q6: Internal control level
            if intake.get("internal_control") is None:
                _print("  QUESTION 6 of ~7 — VA26 §2.1.5 (Internal Control)")
                _print("  Is the procured item subject to HIGH or LOW internal control?")

                if intake.get("procurement_desc"):
                    _print(f"  Context: {intake['procurement_desc']}")

                print("")
                print("  LOW internal control — select LOW if:")
                print("    Material: Tested only against procurement specifications")
                print("    Service:  NOT integrated into your QMS")
                print("")
                print("  HIGH internal control — select HIGH if:")
                print("    Material: Subject to additional internal tests/validation")
                print("    Service:  Integrated into your QMS processes and controls")
                print("")
                print("    [low]   LOW  — tested against specs only / not QMS-integrated")
                print("    [high]  HIGH — additional internal tests / QMS-integrated")
                answer = input("    > ").strip().lower()
                if answer in ("low", "high"):
                    intake["internal_control"] = answer
                _print("")

            # Compute risk class
            try:
                result = classify(
                    is_ready_to_sell_md=False,
                    is_critical_safety=intake.get("is_critical_safety"),
                    is_critical_perf=intake.get("is_critical_perf"),
                    is_critical_qms=intake.get("is_critical_qms"),
                    internal_control=intake.get("internal_control"),
                )
                intake["risk_class"] = result.risk_class.value
                intake["risk_class_type"] = result.supplier_criticality.value
                intake["va26_justification"] = result.justification

                _print(f"  ══ Risk Class Computed: CLASS {result.risk_class.value} ══")
                _print(f"  {result.decision_path}")
                _print(f"  {result.justification}")
            except ValueError as e:
                _print(f"  Cannot compute risk class: {e}")
                _print("  Complete all criticality questions above.")

    # Q7: QAA status
    if intake.get("qaa_status") is None:
        _print("  QUESTION 7 of ~7 — VA26 §2.1.1.1 Measure 3 + §2.1.4")
        _print("  Is a Quality Assurance Agreement (QAA) in place?")
        if intake.get("risk_class"):
            _print(f"  (Required for Class {intake['risk_class']} suppliers per VA26)")
        print("")
        print("    [yes]  QAA signed and on file (FB29 / QMD000065)")
        print("    [in_progress]  QAA being negotiated / drafted")
        print("    [no]   No QAA — GTCs or verbal agreement only")
        answer = input("    > ").strip().lower()
        if answer in ("yes", "in_progress", "no"):
            intake["qaa_status"] = answer
        _print("")

    # Q8: Audit status
    if intake.get("audit_status") is None:
        if intake.get("risk_class") == "1":
            _print("  VA26 §2.1.1.1 Measure 2 — Supplier Audit")
            _print("  Has a supplier audit (per QM_AA17) been completed?")
            print("")
            print("    [yes]    Audit completed — report on file")
            print("    [planned]  Audit scheduled or in progress")
            print("    [no]     No audit — not yet planned")
            answer = input("    > ").strip().lower()
            if answer in ("yes", "planned", "no"):
                intake["audit_status"] = answer
        else:
            intake["audit_status"] = "not_required"

    # ── Step 4: Save and return ──────────────────────────────
    intake["intake_date"] = str(__import__("datetime").date.today())
    intake["status"] = "complete" if intake.get("risk_class") else "incomplete"

    store.upsert_intake(intake)

    _print("\n  [5/5] Intake saved.")
    _print(f"  Status: {intake['status']}")
    if intake.get("risk_class"):
        _print(f"  Risk Class: {intake['risk_class']} — {intake.get('risk_class_type', 'unknown')}")
    _print(f"  Record ID: {supplier_id}")

    return intake


def run_full_evaluation(
    supplier_id: str,
    agent2_db: str | Path = "agent2_vectorstore/data/supplier_risk.db",
    chroma_dir: str | Path = "agent2_vectorstore/data/chroma",
) -> dict:
    """
    Run the complete Agent 3 evaluation:
      1. Audit Agent 2 state
      2. Load/create intake
      3. If blocked → run wizard
      4. Compute risk class + gate + economic score
      5. Generate decision
      6. Save evaluation + decision
    """
    from intake.store import EvaluatorStore

    store = EvaluatorStore()

    # ── Audit Agent 2 ────────────────────────────────────────
    state = audit_agent2_state(supplier_id, agent2_db, chroma_dir)
    existing_intake = store.get_intake(supplier_id)
    gap = build_gap_report(supplier_id, state, existing_intake)

    # Print gap report
    print(format_gap_report_text(gap))

    # ── Blocked? Run wizard ──────────────────────────────────
    if gap.evaluation_blocked:
        print("\n  Intake wizard required before evaluation can proceed.")
        proceed = input("\n  Run intake wizard now? [Y/n] ").strip().lower()
        if proceed == "n":
            print("  Evaluation cancelled.")
            return {"status": "blocked", "supplier_id": supplier_id, "reason": gap.block_reason}

        intake = run_wizard(supplier_id, agent2_db, chroma_dir, store)
        existing_intake = store.get_intake(supplier_id)
        gap = build_gap_report(supplier_id, state, existing_intake)

    # ── Load complete intake ────────────────────────────────
    intake = store.get_intake(supplier_id)
    if not intake:
        print(f"  ERROR: No intake record for {supplier_id}")
        return {"status": "error", "supplier_id": supplier_id}

    # ── Risk Classification ──────────────────────────────────
    from rules.va26 import RiskClass, SupplierCriticality

    risk_class_str = intake.get("risk_class")
    if not risk_class_str:
        print("  ERROR: Risk class not determined. Complete intake wizard first.")
        return {"status": "error", "supplier_id": supplier_id}

    risk_class = RiskClass(risk_class_str)
    supplier_type = SupplierCriticality(intake.get("risk_class_type", "critical"))

    print(f"\n  Risk Class: Class {risk_class.value} — {supplier_type.value}")
    print(f"  Justification: {intake.get('va26_justification', 'N/A')}")

    # ── Approval Gate ────────────────────────────────────────
    gate_result = build_gate(
        risk_class=risk_class,
        supplier_criticality=supplier_type,
        certifications=state.certifications,
        nonconformances=state.nonconformances,
        audit_facts=state.audit_facts,
        purchases=state.purchases,
        profile=state.profile,
        qaa_status=intake.get("qaa_status"),
        audit_status=intake.get("audit_status"),
    )
    print(format_gate_result(gate_result))

    # ── Economic Evaluation ──────────────────────────────────
    econ_result = evaluate_economic(
        certifications=state.certifications,
        nonconformances=state.nonconformances,
        purchases=state.purchases,
        audit_facts=state.audit_facts,
        profile=state.profile,
    )
    print(format_economic_result(econ_result))

    # Update gate's economic eval item
    for item in gate_result.gate_items:
        if item.measure.value == "economic_evaluation":
            item.status = __import__("intake.gate_engine", fromlist=["GateStatus"]).GateStatus.MET
            item.evidence_summary = (
                f"Weighted score: {econ_result.weighted_score:.2f} "
                f"→ {econ_result.economic_class}-Supplier "
                f"({econ_result.confirmed_count}/{len(econ_result.criterion_scores)} criteria confirmed)"
            )

    # ── Final Decision ──────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"  AGENT 3 FINAL DECISION — {supplier_id}")
    print("=" * 70)
    print(f"  Risk Class:       Class {risk_class.value} ({supplier_type.value})")
    print(f"  Economic Class:   {econ_result.economic_class}-Supplier ({econ_result.weighted_score:.2f})")
    print(f"  Gate Status:      {gate_result.met_items}/{gate_result.total_items} criteria met")
    print(f"  Approval Status:  {gate_result.approval_status.upper()}")
    print(f"  VA26 Justification: {gate_result.va26_justification}")

    if gate_result.action_required:
        print(f"  Action Required:")
        for a in gate_result.action_required:
            print(f"    • {a}")

    # ── Save Evaluation ─────────────────────────────────────
    eval_data = {
        "supplier_id": supplier_id,
        "intake_id": intake.get("intake_id"),
        "eval_date": str(__import__("datetime").date.today()),
        "risk_class": risk_class.value,
        "economic_class": econ_result.economic_class,
        "economic_score": econ_result.weighted_score,
        "status": gate_result.approval_status,
        "gate_results": [
            {
                "measure": i.measure.value,
                "status": i.status.value,
                "va26_ref": i.va26_ref,
                "description": i.description,
                "evidence_summary": i.evidence_summary,
            }
            for i in gate_result.gate_items
        ],
        "report": {
            "risk_classification": {
                "class": risk_class.value,
                "type": supplier_type.value,
                "justification": intake.get("va26_justification", ""),
                "va26_ref": "VA26 §2.1.5",
            },
            "economic_evaluation": {
                "class": econ_result.economic_class,
                "weighted_score": econ_result.weighted_score,
                "criteria": [
                    {
                        "name": c.criterion_name,
                        "score": c.score,
                        "grade": c.grade_label,
                        "evidence": c.evidence,
                        "is_estimated": c.is_estimated,
                    }
                    for c in econ_result.criterion_scores
                ],
                "confirmed_count": econ_result.confirmed_count,
                "partial": econ_result.partial,
                "va26_ref": "VA26 §2.2.2",
            },
            "approval_gate": {
                "status": gate_result.approval_status,
                "criteria_met": gate_result.met_items,
                "criteria_total": gate_result.total_items,
                "blocking_unmet": gate_result.blocking_unmet,
                "va26_justification": gate_result.va26_justification,
                "conditions": gate_result.conditions,
                "action_required": gate_result.action_required,
            },
        },
    }

    eval_id = store.save_evaluation(eval_data)
    print(f"\n  Evaluation saved: {eval_id}")

    # Save decision
    from intake.gate_engine import GateStatus
    blocking = any(
        i.status == GateStatus.UNMET and i.is_blocking
        for i in gate_result.gate_items
    )

    decision_data = {
        "supplier_id": supplier_id,
        "eval_id": eval_id,
        "decision": gate_result.approval_status.upper(),
        "decision_date": str(__import__("datetime").date.today()),
        "conditions": gate_result.conditions + [
            f"Economic class: {econ_result.economic_class} ({econ_result.weighted_score:.2f})"
        ],
        "va26_justification": gate_result.va26_justification,
        "next_review": None,
    }
    decision_id = store.save_decision(decision_data)
    print(f"  Decision saved: {decision_id}")

    return eval_data
