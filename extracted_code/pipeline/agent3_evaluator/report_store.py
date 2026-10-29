"""report_store.py — H5 fix: immutable append-only evaluation reports in SQLite."""
from __future__ import annotations
import hashlib, json, sqlite3, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

def _db() -> Path:
    here = Path(__file__).resolve().parent
    for c in [here, here.parent, here.parent.parent]:
        if (c/"config.py").exists():
            if str(c) not in sys.path: sys.path.insert(0, str(c))
            from config import get_db_path; return get_db_path()
    return Path(__file__).resolve().parent.parent / "data" / "supplier_risk.db"

def _conn() -> sqlite3.Connection:
    p = _db(); p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p)); conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL"); return conn

def _init():
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS evaluation_reports (
                report_id TEXT PRIMARY KEY, supplier_id TEXT NOT NULL,
                procurement_ref TEXT NOT NULL DEFAULT 'default',
                report_hash TEXT NOT NULL, report_json TEXT NOT NULL,
                status TEXT, risk_class TEXT, generated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_rpt_sup ON evaluation_reports(supplier_id, generated_at);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_rpt_hash ON evaluation_reports(supplier_id, procurement_ref, report_hash);
        """)

def save_report(report: dict, procurement_ref: str = "default") -> str:
    _init()
    sid = report.get("supplier_id", "unknown")
    rjson = json.dumps(report, default=str, sort_keys=True)
    rhash = hashlib.sha256(rjson.encode()).hexdigest()
    now = report.get("generated_at") or datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        row = c.execute("SELECT report_id FROM evaluation_reports WHERE supplier_id=? AND procurement_ref=? AND report_hash=?",
                        (sid, procurement_ref, rhash)).fetchone()
        if row: return row["report_id"]
        rid = str(uuid.uuid4())
        c.execute("INSERT INTO evaluation_reports VALUES (?,?,?,?,?,?,?,?)",
                  (rid, sid, procurement_ref, rhash, rjson,
                   report.get("status"),
                   str((report.get("classification") or {}).get("risk_class","")), now))
    return rid

def get_latest_report(supplier_id: str, procurement_ref: str = "default") -> Optional[dict]:
    _init()
    with _conn() as c:
        row = c.execute("SELECT report_json FROM evaluation_reports WHERE supplier_id=? AND procurement_ref=? ORDER BY generated_at DESC LIMIT 1",
                        (supplier_id, procurement_ref)).fetchone()
    return json.loads(row["report_json"]) if row else None

def get_report_by_id(report_id: str) -> Optional[dict]:
    _init()
    with _conn() as c:
        row = c.execute("SELECT report_json FROM evaluation_reports WHERE report_id=?", (report_id,)).fetchone()
    return json.loads(row["report_json"]) if row else None

def get_report_history(supplier_id: str, procurement_ref: str = "default") -> list[dict]:
    _init()
    with _conn() as c:
        rows = c.execute("SELECT report_id, status, risk_class, generated_at FROM evaluation_reports WHERE supplier_id=? AND procurement_ref=? ORDER BY generated_at DESC",
                         (supplier_id, procurement_ref)).fetchall()
    return [dict(r) for r in rows]
