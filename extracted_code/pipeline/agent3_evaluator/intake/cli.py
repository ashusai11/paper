"""
Agent 3 Evaluator — CLI Entry Point
====================================
Usage:
    python -m agent3_evaluator.intake run <supplier_id>
    python -m agent3_evaluator.intake status <supplier_id>
    python -m agent3_evaluator.intake report <supplier_id>
    python -m agent3_evaluator.intake gate <supplier_id>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure agent3_evaluator is on path
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))

from agent3_evaluator.intake.audit import audit_agent2_state, build_gap_report, format_gap_report_text
from agent3_evaluator.intake.wizard import run_wizard, run_full_evaluation
from agent3_evaluator.intake.store import EvaluatorStore


def cmd_run(supplier_id: str, agent2_db: str, chroma_dir: str):
    """Run full evaluation: audit → wizard → decision."""
    store = EvaluatorStore()
    result = run_full_evaluation(supplier_id, agent2_db, chroma_dir)
    return result


def cmd_status(supplier_id: str, agent2_db: str, chroma_dir: str):
    """Show current state of Agent 2 + Agent 3 for this supplier."""
    store = EvaluatorStore()
    state = audit_agent2_state(supplier_id, agent2_db, chroma_dir)
    intake = store.get_intake(supplier_id)
    gap = build_gap_report(supplier_id, state, intake)

    print(format_gap_report_text(gap))

    print("\n  ── Agent 3 Intake Record ─────────────────────────────")
    if intake:
        print(f"    Status: {intake.get('status', 'unknown')}")
        print(f"    Risk class: {intake.get('risk_class') or 'not set'}")
        print(f"    QAA status: {intake.get('qaa_status') or 'not reported'}")
        print(f"    Audit status: {intake.get('audit_status') or 'not reported'}")
    else:
        print("    (no intake record yet)")

    evals = store.list_evaluations(supplier_id)
    if evals:
        latest = evals[-1]
        print(f"\n  ── Latest Evaluation ─────────────────────────────────")
        print(f"    Date: {latest.get('eval_date', 'N/A')}")
        print(f"    Status: {latest.get('status', 'N/A')}")
        print(f"    Economic class: {latest.get('economic_class', 'N/A')}")
    else:
        print("\n  ── Latest Evaluation ─────────────────────────────────")
        print("    (no evaluations yet)")


def cmd_report(supplier_id: str, agent2_db: str, chroma_dir: str):
    """Show the latest evaluation report."""
    store = EvaluatorStore()
    evals = store.list_evaluations(supplier_id)

    if not evals:
        print(f"No evaluations found for {supplier_id}")
        return

    latest = evals[-1]
    report = latest.get("report", {})

    print("\n" + "=" * 70)
    print(f"  EVALUATION REPORT — {supplier_id}")
    print(f"  Date: {latest.get('eval_date', 'N/A')} | Status: {latest.get('status', 'N/A')}")
    print("=" * 70)

    # Risk Classification
    rc = report.get("risk_classification", {})
    if rc:
        print(f"\n  RISK CLASSIFICATION (VA26 §2.1.5)")
        print(f"  Class {rc.get('class', '?')} — {rc.get('type', 'unknown')}")
        print(f"  {rc.get('justification', 'N/A')}")

    # Economic Evaluation
    ee = report.get("economic_evaluation", {})
    if ee:
        print(f"\n  ECONOMIC EVALUATION (VA26 §2.2.2)")
        print(f"  Class {ee.get('class', '?')}-Supplier | Score: {ee.get('weighted_score', '?')}")
        if ee.get("criteria"):
            print(f"  {'─' * 60}")
            for c in ee["criteria"]:
                icon = "✓" if c["score"] <= 3 else "~" if c["score"] <= 4 else "✗"
                est = " [EST]" if c.get("is_estimated") else ""
                print(f"  {icon} {c['name']:<40} {c['score']}/6{est}")
                print(f"     {c.get('evidence', '')}")

    # Approval Gate
    ag = report.get("approval_gate", {})
    if ag:
        print(f"\n  APPROVAL GATE (VA26 §2.1.1.1)")
        print(f"  {ag.get('criteria_met', 0)}/{ag.get('criteria_total', 0)} criteria met")
        print(f"  Decision: {ag.get('status', 'N/A').upper()}")
        print(f"  {ag.get('va26_justification', '')}")
        if ag.get("conditions"):
            print(f"  Conditions: {', '.join(ag['conditions'])}")
        if ag.get("action_required"):
            print(f"  Action Required:")
            for a in ag["action_required"]:
                print(f"    • {a}")

    print("=" * 70)


def cmd_wizard(supplier_id: str, agent2_db: str, chroma_dir: str):
    """Run intake wizard only (no evaluation)."""
    store = EvaluatorStore()
    intake = run_wizard(supplier_id, agent2_db, chroma_dir, store)
    return intake


def main():
    parser = argparse.ArgumentParser(
        description="Agent 3 VA26 Supplier Evaluator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run — full evaluation
    run_parser = subparsers.add_parser("run", help="Run full VA26 evaluation")
    run_parser.add_argument("supplier_id", help="Supplier ID to evaluate")
    run_parser.add_argument("--db", default="agent2_vectorstore/data/supplier_risk.db",
                            help="Agent 2 SQLite path")
    run_parser.add_argument("--chroma", default="agent2_vectorstore/data/chroma",
                            help="Agent 2 ChromaDB directory")

    # status — show state
    status_parser = subparsers.add_parser("status", help="Show current state")
    status_parser.add_argument("supplier_id", help="Supplier ID")
    status_parser.add_argument("--db", default="agent2_vectorstore/data/supplier_risk.db")
    status_parser.add_argument("--chroma", default="agent2_vectorstore/data/chroma")

    # report — show evaluation report
    report_parser = subparsers.add_parser("report", help="Show latest evaluation report")
    report_parser.add_argument("supplier_id", help="Supplier ID")
    report_parser.add_argument("--db", default="agent2_vectorstore/data/supplier_risk.db")
    report_parser.add_argument("--chroma", default="agent2_vectorstore/data/chroma")

    # wizard — intake only
    wizard_parser = subparsers.add_parser("wizard", help="Run intake wizard only")
    wizard_parser.add_argument("supplier_id", help="Supplier ID")
    wizard_parser.add_argument("--db", default="agent2_vectorstore/data/supplier_risk.db")
    wizard_parser.add_argument("--chroma", default="agent2_vectorstore/data/chroma")

    args = parser.parse_args()

    # Resolve paths relative to workspace
    db_path = Path(args.db)
    chroma_path = Path(args.chroma)

    if args.command == "run":
        cmd_run(args.supplier_id, str(db_path), str(chroma_path))
    elif args.command == "status":
        cmd_status(args.supplier_id, str(db_path), str(chroma_path))
    elif args.command == "report":
        cmd_report(args.supplier_id, str(db_path), str(chroma_path))
    elif args.command == "wizard":
        cmd_wizard(args.supplier_id, str(db_path), str(chroma_path))


if __name__ == "__main__":
    main()
