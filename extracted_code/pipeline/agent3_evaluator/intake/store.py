"""
SQLite Store for Agent 3 Evaluator
==================================
Stores intake records, evaluation reports, and decisions.
Separate from Agent 2's SQLite — Agent 3 maintains its own QMS records.

Schema:
  - intake_records: Form 69 intake data per supplier
  - evaluations: Full evaluation reports per supplier per cycle
  - monitoring_reports: Generated monitoring reports
  - decisions: Approval/rejection decisions
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from agent3_evaluator.rules.va26 import RiskClass


class EvaluatorStore:
    """
    SQLite store for Agent 3 QMS records.

    Schema:
      intake_records  — Form 69 intake per supplier
      evaluations     — Full evaluation per cycle
      decisions      — Approval/rejection per evaluation
      monitoring     — Monitoring reports
    """

    def __init__(self, database_path: str = "db/evaluator.db"):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()  # Auto-create tables on first use

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.database_path))
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self):
        """Create all tables. Safe to call on existing DB."""
        with self.connect() as conn:
            cursor = conn.cursor()

            # ── Intake Records ──────────────────────────────
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS intake_records (
                    intake_id     TEXT PRIMARY KEY,
                    supplier_id   TEXT NOT NULL UNIQUE,
                    supplier_name TEXT,
                    intake_date   TEXT NOT NULL,
                    updated_at    TEXT NOT NULL,
                    status        TEXT NOT NULL DEFAULT 'incomplete',
                    -- Step 1
                    procurement_desc   TEXT,
                    procurement_purpose TEXT,
                    procurement_spec   TEXT,
                    -- Step 2 (JSON list of doc IDs received)
                    docs_received   TEXT,
                    docs_missing    TEXT,
                    -- Step 3 — Criticality
                    is_ready_to_sell_md  TEXT,
                    is_critical_safety   TEXT,
                    is_critical_perf    TEXT,
                    is_critical_qms     TEXT,
                    -- Step 4 — Internal Control
                    internal_control    TEXT,
                    qaa_status          TEXT,
                    audit_status        TEXT,
                    supplier_type_ref  TEXT,
                    -- Computed
                    risk_class          TEXT,
                    risk_class_type     TEXT,
                    is_critical         TEXT,
                    va26_justification  TEXT,
                    -- Full record
                    raw_json            TEXT,
                    va26_ref            TEXT DEFAULT 'QMD000035 Rev.06'
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_intake_supplier
                ON intake_records(supplier_id)
            """)

            # ── Evaluations ────────────────────────────────
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evaluations (
                    eval_id        TEXT PRIMARY KEY,
                    supplier_id    TEXT NOT NULL,
                    intake_id      TEXT,
                    eval_date      TEXT NOT NULL,
                    risk_class     TEXT,
                    economic_class TEXT,
                    economic_score REAL,
                    status         TEXT NOT NULL,
                    -- Approval gate results (JSON)
                    gate_results   TEXT,
                    -- Full report (JSON)
                    report_json    TEXT,
                    va26_ref       TEXT DEFAULT 'QMD000035 Rev.06'
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_eval_supplier
                ON evaluations(supplier_id)
            """)

            # ── Decisions ─────────────────────────────────
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id   TEXT PRIMARY KEY,
                    supplier_id   TEXT NOT NULL,
                    eval_id       TEXT,
                    decision_date TEXT NOT NULL,
                    decision      TEXT NOT NULL,
                    -- APPROVE | REJECT | CONDITIONAL | BLOCKED
                    conditions    TEXT,
                    va26_justification TEXT,
                    decided_by    TEXT DEFAULT 'Agent 3',
                    next_review   TEXT,
                    va26_ref      TEXT DEFAULT 'QMD000035 Rev.06'
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_decision_supplier
                ON decisions(supplier_id)
            """)

            conn.commit()

    # ──────────────────────────────────────────────────────────
    # Intake Records
    # ──────────────────────────────────────────────────────────

    def upsert_intake(self, data: dict) -> str:
        """
        Insert or update an intake record.

        Args:
            data: Full intake dict from intake wizard.
                  Must contain: supplier_id, supplier_name
                  May contain all other intake fields.

        Returns:
            intake_id
        """
        now = datetime.utcnow().isoformat()
        intake_id = str(uuid.uuid4())

        # Check if record already exists
        existing = self.get_intake(data["supplier_id"])

        if existing:
            intake_id = existing["intake_id"]
            now = existing["updated_at"]

        # Serialize lists
        docs_received = json.dumps(data.get("docs_received", []), ensure_ascii=False)
        docs_missing  = json.dumps(data.get("docs_missing", []), ensure_ascii=False)

        raw_json = json.dumps(data, ensure_ascii=False)

        with self.connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO intake_records (
                    intake_id, supplier_id, supplier_name, intake_date,
                    updated_at, status,
                    procurement_desc, procurement_purpose, procurement_spec,
                    docs_received, docs_missing,
                    is_ready_to_sell_md, is_critical_safety,
                    is_critical_perf, is_critical_qms,
                    internal_control, qaa_status, audit_status,
                    supplier_type_ref,
                    risk_class, risk_class_type, is_critical,
                    va26_justification,
                    raw_json
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?,
                    ?, ?, ?,
                    ?,
                    ?
                )
            """, (
                intake_id,
                data.get("supplier_id"),
                data.get("supplier_name"),
                data.get("intake_date", now[:10]),
                now,
                data.get("status", "incomplete"),
                data.get("procurement_desc"),
                data.get("procurement_purpose"),
                data.get("procurement_spec"),
                docs_received,
                docs_missing,
                data.get("is_ready_to_sell_md"),
                data.get("is_critical_safety"),
                data.get("is_critical_perf"),
                data.get("is_critical_qms"),
                data.get("internal_control"),
                data.get("qaa_status"),
                data.get("audit_status"),
                data.get("supplier_type_ref"),
                data.get("risk_class"),
                data.get("risk_class_type"),
                data.get("is_critical"),
                data.get("va26_justification"),
                raw_json,
            ))
            conn.commit()

        return intake_id

    def get_intake(self, supplier_id: str) -> Optional[dict]:
        """Get the latest intake record for a supplier."""
        with self.connect() as conn:
            row = conn.execute("""
                SELECT * FROM intake_records
                WHERE supplier_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
            """, (supplier_id,)).fetchone()

            if not row:
                return None

            result = dict(row)
            # Deserialize JSON fields
            for col in ("docs_received", "docs_missing"):
                val = result.pop(col, None)
                try:
                    result[col] = json.loads(val) if val else []
                except (json.JSONDecodeError, TypeError):
                    result[col] = []
            # Re-parse raw_json
            raw = result.pop("raw_json", None)
            if raw:
                try:
                    result["raw"] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    result["raw"] = {}
            return result

    def list_intakes(self, status: str | None = None) -> list[dict]:
        """List all intake records, optionally filtered by status."""
        with self.connect() as conn:
            if status:
                rows = conn.execute("""
                    SELECT intake_id, supplier_id, supplier_name, intake_date,
                           updated_at, status, risk_class
                    FROM intake_records
                    WHERE status = ?
                    ORDER BY updated_at DESC
                """, (status,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT intake_id, supplier_id, supplier_name, intake_date,
                           updated_at, status, risk_class
                    FROM intake_records
                    ORDER BY updated_at DESC
                """).fetchall()
            return [dict(row) for row in rows]

    # ──────────────────────────────────────────────────────────
    # Evaluations
    # ──────────────────────────────────────────────────────────

    def save_evaluation(self, data: dict) -> str:
        """Save a full evaluation report."""
        eval_id = data.get("eval_id") or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        gate_results = json.dumps(data.get("gate_results", []), ensure_ascii=False)
        report_json  = json.dumps(data.get("report", {}), ensure_ascii=False)

        with self.connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO evaluations (
                    eval_id, supplier_id, intake_id, eval_date,
                    risk_class, economic_class, economic_score,
                    status, gate_results, report_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                eval_id,
                data.get("supplier_id"),
                data.get("intake_id"),
                data.get("eval_date", now[:10]),
                data.get("risk_class"),
                data.get("economic_class"),
                data.get("economic_score"),
                data.get("status"),
                gate_results,
                report_json,
            ))
            conn.commit()

        return eval_id

    def get_latest_evaluation(self, supplier_id: str) -> Optional[dict]:
        """Get the most recent evaluation for a supplier."""
        with self.connect() as conn:
            row = conn.execute("""
                SELECT * FROM evaluations
                WHERE supplier_id = ?
                ORDER BY eval_date DESC
                LIMIT 1
            """, (supplier_id,)).fetchone()

            if not row:
                return None

            result = dict(row)
            for col in ("gate_results", "report_json"):
                val = result.pop(col, None)
                try:
                    result[col] = json.loads(val) if val else {}
                except (json.JSONDecodeError, TypeError):
                    result[col] = {}
            return result

    def list_evaluations(self, supplier_id: str) -> list[dict]:
        """List all evaluations for a supplier."""
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT eval_id, supplier_id, eval_date, risk_class,
                       economic_class, economic_score, status
                FROM evaluations
                WHERE supplier_id = ?
                ORDER BY eval_date DESC
            """, (supplier_id,)).fetchall()
            return [dict(row) for row in rows]

    # ──────────────────────────────────────────────────────────
    # Decisions
    # ──────────────────────────────────────────────────────────

    def save_decision(self, data: dict) -> str:
        """Save an approval/rejection decision."""
        decision_id = data.get("decision_id") or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        conditions = json.dumps(data.get("conditions", []), ensure_ascii=False)

        with self.connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO decisions (
                    decision_id, supplier_id, eval_id, decision_date,
                    decision, conditions, va26_justification,
                    next_review
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decision_id,
                data.get("supplier_id"),
                data.get("eval_id"),
                data.get("decision_date", now[:10]),
                data.get("decision"),
                conditions,
                data.get("va26_justification"),
                data.get("next_review"),
            ))
            conn.commit()

        return decision_id

    def get_latest_decision(self, supplier_id: str) -> Optional[dict]:
        """Get the most recent decision for a supplier."""
        with self.connect() as conn:
            row = conn.execute("""
                SELECT * FROM decisions
                WHERE supplier_id = ?
                ORDER BY decision_date DESC
                LIMIT 1
            """, (supplier_id,)).fetchone()

            if not row:
                return None

            result = dict(row)
            val = result.pop("conditions", None)
            try:
                result["conditions"] = json.loads(val) if val else []
            except (json.JSONDecodeError, TypeError):
                result["conditions"] = []
            return result

    def list_decisions(self, supplier_id: str) -> list[dict]:
        """List all decisions for a supplier."""
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT decision_id, supplier_id, decision_date,
                       decision, next_review
                FROM decisions
                WHERE supplier_id = ?
                ORDER BY decision_date DESC
            """, (supplier_id,)).fetchall()
            return [dict(row) for row in rows]
