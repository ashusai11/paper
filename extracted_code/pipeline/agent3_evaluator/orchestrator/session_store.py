"""session_store.py — session metadata persistence."""
from __future__ import annotations
import json, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

def _db():
    here = Path(__file__).resolve().parent
    for c in [here, here.parent, here.parent.parent, here.parent.parent.parent]:
        if (c/"config.py").exists():
            if str(c) not in sys.path: sys.path.insert(0, str(c))
            from config import get_db_path; return get_db_path()
    return Path(__file__).resolve().parent.parent.parent / "data" / "supplier_risk.db"

def _conn():
    p = _db(); p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p)); conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL"); return conn

def _init():
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS evaluation_sessions (
                thread_id TEXT PRIMARY KEY, supplier_id TEXT NOT NULL,
                procurement_ref TEXT NOT NULL DEFAULT 'default',
                status TEXT NOT NULL DEFAULT 'running',
                last_interrupt TEXT, started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, completed_at TEXT,
                decided_by TEXT, final_decision TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_sess_sup ON evaluation_sessions(supplier_id, updated_at);
        """)

def _now(): return datetime.now(timezone.utc).isoformat()

def save_session_state(thread_id, supplier_id, status, procurement_ref="default",
                       last_interrupt=None, decided_by=None, final_decision=None):
    _init(); now = _now()
    ij = json.dumps(last_interrupt) if last_interrupt else None
    with _conn() as c:
        ex = c.execute("SELECT thread_id FROM evaluation_sessions WHERE thread_id=?", (thread_id,)).fetchone()
        if not ex:
            c.execute("INSERT INTO evaluation_sessions VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (thread_id, supplier_id, procurement_ref, status, ij, now, now, None, decided_by, final_decision))
        else:
            c.execute("UPDATE evaluation_sessions SET status=?,last_interrupt=?,updated_at=?,decided_by=?,final_decision=? WHERE thread_id=?",
                      (status, ij, now, decided_by, final_decision, thread_id))

def load_session_state(thread_id) -> Optional[dict]:
    _init()
    with _conn() as c:
        row = c.execute("SELECT * FROM evaluation_sessions WHERE thread_id=?", (thread_id,)).fetchone()
    if not row: return None
    d = dict(row)
    if d.get("last_interrupt"):
        try: d["last_interrupt"] = json.loads(d["last_interrupt"])
        except Exception: pass
    return d

def list_active_sessions(supplier_id=None) -> list[dict]:
    _init()
    with _conn() as c:
        if supplier_id:
            rows = c.execute("SELECT * FROM evaluation_sessions WHERE supplier_id=? AND status NOT IN ('complete') ORDER BY updated_at DESC", (supplier_id,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM evaluation_sessions WHERE status NOT IN ('complete') ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]
