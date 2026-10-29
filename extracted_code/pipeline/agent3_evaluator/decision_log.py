"""
decision_log.py — Append-only audit record of final human decisions
====================================================================
FIX 1: graph.py's writeback called this module, but it was not part of the
package, so the final decision was never recorded (the error was printed and
swallowed). This restores it.

VA26 §3.1 requires every approval decision to be recorded, attributed and
traceable. This table is written ONLY by record_decision(), which is called
only from the graph's writeback node after a human has decided. No agent,
tool or LLM can produce an approve / conditional / reject outcome.

Override tracking: when the human decides although the evaluation report was
not 'ready_for_human_review' (open or unresolved items), that is a knowing
exception. It is stored as its own event (override_confirmed / override_by /
override_reason / override_at) so a clean decision and a knowing override are
never ambiguous in the history. A reason is mandatory — enforced HERE, not
only in the UI, so no caller can bypass it.

Rows are never updated or deleted.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

VALID_DECISIONS = {"approved", "conditional", "rejected"}


def _db_path() -> Path:
    here = Path(__file__).resolve().parent
    for c in [here, here.parent, here.parent.parent]:
        if (c / "config.py").exists():
            if str(c) not in sys.path:
                sys.path.insert(0, str(c))
            from config import get_db_path
            return get_db_path()
    return here.parent / "data" / "supplier_risk.db"


def _connect() -> sqlite3.Connection:
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_table() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS decision_log (
                decision_id        TEXT PRIMARY KEY,
                supplier_id        TEXT NOT NULL,
                procurement_ref    TEXT NOT NULL DEFAULT 'default',
                decision           TEXT NOT NULL,
                decided_by         TEXT NOT NULL,
                decided_at         TEXT NOT NULL,
                conditions         TEXT,
                notes              TEXT,
                report_status_at_decision TEXT,
                risk_class_at_decision    TEXT,
                economic_class_at_decision TEXT,
                report_id          TEXT,
                report_snapshot    TEXT,
                override_confirmed INTEGER NOT NULL DEFAULT 0,
                override_by        TEXT,
                override_reason    TEXT,
                override_at        TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_decision_supplier
                ON decision_log(supplier_id, decided_at);
        """)


def record_decision(
    supplier_id: str,
    decision: str,
    decided_by: str,
    *,
    procurement_ref: str = "default",
    conditions: Optional[str] = None,
    notes: Optional[str] = None,
    report: Optional[dict] = None,
    report_id: Optional[str] = None,
    override_confirmed: bool = False,
    override_reason: Optional[str] = None,
    override_by: Optional[str] = None,
) -> str:
    """
    Record a final human decision. Returns the decision_id.

    Raises ValueError if:
      - decision is not approved / conditional / rejected
      - decision is 'conditional' without conditions
      - decided_by is empty (VA26 requires attribution)
      - override_confirmed is True without an override_reason
    """
    if decision not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of {sorted(VALID_DECISIONS)}, got {decision!r}")
    if decision == "conditional" and not (conditions and conditions.strip()):
        raise ValueError("conditions are required when decision is 'conditional'")
    if not decided_by or not decided_by.strip():
        raise ValueError("decided_by is required — VA26 requires attribution")
    if override_confirmed and not (override_reason and override_reason.strip()):
        raise ValueError(
            "override_reason is required when the decision overrides an "
            "incomplete evaluation report"
        )

    init_table()
    decision_id = str(uuid.uuid4())
    now = _now()
    rep = report or {}

    with _connect() as conn:
        conn.execute(
            """INSERT INTO decision_log (
                   decision_id, supplier_id, procurement_ref, decision, decided_by,
                   decided_at, conditions, notes, report_status_at_decision,
                   risk_class_at_decision, economic_class_at_decision, report_id,
                   report_snapshot, override_confirmed, override_by,
                   override_reason, override_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                decision_id, supplier_id, procurement_ref, decision, decided_by.strip(),
                now, conditions, notes, rep.get("status"),
                str((rep.get("classification") or {}).get("risk_class", "")) or None,
                (rep.get("economic") or {}).get("classification"),
                report_id,
                json.dumps(rep, default=str) if rep else None,
                int(bool(override_confirmed)),
                (override_by or decided_by).strip() if override_confirmed else None,
                override_reason.strip() if override_confirmed else None,
                now if override_confirmed else None,
            ),
        )
    return decision_id


def get_latest_decision(supplier_id: str, procurement_ref: str = "default") -> Optional[dict]:
    init_table()
    with _connect() as conn:
        row = conn.execute(
            """SELECT * FROM decision_log WHERE supplier_id=? AND procurement_ref=?
               ORDER BY decided_at DESC LIMIT 1""",
            (supplier_id, procurement_ref),
        ).fetchone()
    return dict(row) if row else None


def get_decision_history(supplier_id: str) -> list[dict]:
    """All decisions for a supplier, newest first (snapshot omitted for size)."""
    init_table()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT decision_id, procurement_ref, decision, decided_by, decided_at,
                      conditions, notes, report_status_at_decision, risk_class_at_decision,
                      economic_class_at_decision, report_id, override_confirmed,
                      override_by, override_reason, override_at
               FROM decision_log WHERE supplier_id=? ORDER BY decided_at DESC""",
            (supplier_id,),
        ).fetchall()
    return [dict(r) for r in rows]
