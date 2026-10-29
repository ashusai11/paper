"""
context_builder.py — Agent 2 evidence → LLM-readable narrative
===============================================================
The LLM never queries the database. It reads what this module produces, so
anything not in the narrative does not exist as far as the LLM is concerned.

Changes in this version
  * Uses the shared rules in questions.py to say exactly what is still needed
    from the human (and in which order), instead of its own copy of the rules.
  * Shows answers the reviewer deferred ("Skip for now") and which tools have
    already succeeded, so the LLM does not repeat finished work.
  * Imports are package-qualified and the store is opened via SQLiteStore()
    (config path) — no directory-walking.
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT, _ROOT / "agent2_vectorstore"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from agent3_evaluator.orchestrator.questions import (          # noqa: E402
    FIELD_ORDER, QUESTION_CATALOG, next_to_ask, skipped_fields,
)

_LATE = {"late", "failed", "delayed"}


def _days(ds: Optional[str]) -> Optional[int]:
    if not ds:
        return None
    try:
        return (datetime.fromisoformat(ds).date() - date.today()).days
    except ValueError:
        return None


def _cert_line(value: str, valid_until: Optional[str]) -> str:
    d = _days(valid_until)
    if d is None:
        return f"  • {value} (no expiry date on file)"
    if d < 0:
        return f"  • {value} — EXPIRED {abs(d)} days ago"
    if d < 90:
        return f"  • {value} — EXPIRING in {d} days ({valid_until})"
    return f"  • {value} — valid until {valid_until}"


def build_context(supplier_id: str, intake_answers: Optional[dict] = None,
                  procurement_ref: str = "default",
                  tool_history: Optional[list] = None) -> dict:
    """
    Returns {"narrative", "missing", "blockers", "agent2_summary"}.
      missing  = human answers still needed and not deferred, in asking order
      blockers = hard stops (currently: no documents on file)
    """
    from storage.sqlite_store import SQLiteStore
    store = SQLiteStore()
    intake = intake_answers or {}

    supplier = store.get_supplier(supplier_id) or {}
    docs = store.get_document_history(supplier_id) or []
    certs = store.get_current_facts(supplier_id, category="cert")
    ncs = store.get_current_facts(supplier_id, category="nc")
    risks = store.get_current_facts(supplier_id, category="risk")
    purchases = store.get_purchase_history(supplier_id, limit=500)
    refined = store.get_refined_data(supplier_id) or []

    degraded_rows = [r for r in refined if r.get("degraded")]
    name = supplier.get("supplier_name", "Unknown")

    L: list[str] = [f"=== SUPPLIER: {name} ({supplier_id}) ===", ""]

    L.append(f"DOCUMENTS ON FILE: {len(docs)}")
    for d in docs[-5:]:
        L.append(f"  • {d.get('source_file', '?')} ({d.get('doc_type', '?')})")
    if not docs:
        L.append("  NO DOCUMENTS — evaluation cannot proceed without evidence")
    L.append("")

    L.append("CERTIFICATIONS:")
    if certs:
        for f in certs:
            L.append(_cert_line(f.get("value", "?"), f.get("valid_until")))
        if not any("13485" in str(f.get("value", "")) for f in certs):
            L.append("  ISO 13485 NOT FOUND among certificates on file")
    else:
        L.append("  NONE ON FILE" + (" (extraction failed for some documents — may be incomplete)"
                                      if degraded_rows else ""))
    L.append("")

    L.append(f"NONCONFORMANCES: {len(ncs)}")
    for f in ncs[-3:]:
        L.append(f"  • {f.get('value', '?')}")
    L.append("")

    L.append("PURCHASE HISTORY:")
    if len(purchases) >= 3:
        late = sum(1 for p in purchases if str(p.get("delivery_status", "")).lower() in _LATE)
        qi = sum(1 for p in purchases if p.get("quality_issue"))
        n = len(purchases)
        L.append(f"  {n} purchases · late/failed deliveries {late}/{n} · quality issues {qi}/{n}")
    elif purchases:
        L.append(f"  Only {len(purchases)} purchase(s): too few for reliable auto-scoring")
    else:
        L.append("  NONE ON FILE")
    L.append("")

    if risks:
        L.append("RISK SIGNALS: " + "; ".join(str(f.get("value", "?")) for f in risks[:5]))
        L.append("")

    if degraded_rows:
        L.append(f"EXTRACTION WARNING: {len(degraded_rows)} document(s) were not fully processed by the LLM.")
        for r in sorted({str(r.get("degraded_reason")) for r in degraded_rows if r.get("degraded_reason")})[:2]:
            L.append(f"  Reason: {r}")
        L.append("")

    skipped = set(skipped_fields(intake))
    L.append("HUMAN ANSWERS SO FAR:")
    for f in FIELD_ORDER:
        v = intake.get(f)
        shown = "DEFERRED by reviewer" if f in skipped and v is None else \
                ("not yet answered" if v is None else str(v))
        L.append(f"  {f}: {shown}")
    L.append("")

    todo = next_to_ask(intake)
    L.append("STILL NEEDED FROM THE HUMAN (ask in this order): " + (", ".join(todo) if todo else "nothing"))
    if tool_history is not None:
        from agent3_evaluator.orchestrator.tools import REQUIRED_TOOLS, last_success
        done = [t for t in REQUIRED_TOOLS if last_success(tool_history, t) is not None]
        L.append("TOOLS ALREADY SUCCEEDED: " + (", ".join(done) if done else "none"))

    blockers = [] if docs else ["No documents uploaded. Upload at least one supplier document, then retry."]

    return {
        "narrative": "\n".join(L),
        "missing": todo,
        "blockers": blockers,
        "agent2_summary": {
            "supplier_name": name, "document_count": len(docs), "cert_count": len(certs),
            "nc_count": len(ncs), "purchase_count": len(purchases),
            "has_iso_13485": any("13485" in str(f.get("value", "")) for f in certs),
            "any_expired_certs": any((_days(f.get("valid_until")) or 1) < 0 for f in certs),
            "extraction_degraded": bool(degraded_rows),
            "has_purchase_history": len(purchases) >= 3,
        },
    }
