"""
api/main.py — FastAPI backend
=============================
Run from the project root:  uvicorn api.main:app --reload --port 8000

Changes in this version
  * POST /evaluation/start takes a JSON body (the UI client sends JSON; the old
    route expected query parameters and would have answered 422).
  * POST /ingest reads supplier_id / supplier_name as form fields (they were
    plain parameters, so with a file upload they were silently ignored).
  * POST /evaluation/{id}/decide checks the evaluation is actually waiting for
    a decision, and refuses an override of an incomplete report unless an
    override_reason is given (HTTP 400). decision_log enforces the same rule.
  * Agent 1 / Agent 2 entry points are loaded by file path under unique names:
    both agents have a file called main.py and `from main import ...` can
    resolve to the wrong one.
  * Economic class comes from the latest decision record (company_profile has
    no such column).
  * Slug regex typo fixed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT, _ROOT / "agent2_vectorstore"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from config import get_data_dir, get_db_path                                   # noqa: E402
from agent3_evaluator.decision_log import get_decision_history                 # noqa: E402
from agent3_evaluator.orchestrator.graph import EvaluatorOrchestrator          # noqa: E402
from agent3_evaluator.orchestrator.session_store import list_active_sessions   # noqa: E402
from agent3_evaluator.report_store import get_latest_report                    # noqa: E402

try:                                                    # durable pauses (survive restarts)
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver
    _conn = sqlite3.connect(str(get_db_path()).replace(".db", "_checkpoints.db"),
                            check_same_thread=False)
    _checkpointer = SqliteSaver(_conn)
except ImportError:                                     # pip install langgraph-checkpoint-sqlite
    from langgraph.checkpoint.memory import MemorySaver
    _checkpointer = MemorySaver()
    print("[API] WARNING: langgraph-checkpoint-sqlite not installed — paused "
          "evaluations will be lost when the API restarts.")

orch = EvaluatorOrchestrator(checkpointer=_checkpointer)
app = FastAPI(title="Supplier Qualification API", version="1.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
                   allow_methods=["*"], allow_headers=["*"])

# ── Tabular (spreadsheet) routes ───────────────────────────────────────────
# The "📊 Spreadsheet" page calls /tabular/ingest, /tabular/targets and
# /tabular/imports. They live in api/tabular_routes.py and are only reachable
# if the router is registered HERE — the unified /ingest route does not
# register them. Import it directly: a broken tabular router must fail
# loudly at startup, not silently answer 404 later.
from api.tabular_routes import router as tabular_router          # noqa: E402

app.include_router(tabular_router)


# ── Models (all fields always present; null, never absent) ───────────────────
class SupplierSummary(BaseModel):
    supplier_id: str
    supplier_name: str
    risk_class: Optional[str] = None
    qualification_status: Optional[str] = None
    economic_classification: Optional[str] = None
    total_docs: int = 0
    open_nonconformances: int = 0
    last_eval_date: Optional[str] = None
    active_session: Optional[str] = None


class CertFact(BaseModel):
    value: str
    valid_until: Optional[str] = None
    is_expired: bool = False
    source_file: Optional[str] = None
    source_page: Optional[str] = None
    confidence: Optional[float] = None


class SupplierProfile(SupplierSummary):
    active_certs: list[CertFact] = []
    document_history: list[dict] = []
    recent_decisions: list[dict] = []


class IngestResponse(BaseModel):
    document_id: str
    supplier_id: str
    is_duplicate: bool
    chunks_created: int
    pass1_complete: bool
    pass2_complete: bool
    pass2_status: Optional[str] = None
    # unified front door (ingest.py) — which lane took the file
    lane: Optional[str] = None          # document | tabular | raw
    detected_type: Optional[str] = None
    tables: list[str] = []
    needs_review: bool = False
    degraded: bool = False
    degraded_reason: Optional[str] = None


class EvalStatus(BaseModel):
    status: str
    thread_id: str
    supplier_id: Optional[str] = None
    waiting_for: Optional[str] = None
    message: Optional[str] = None
    payload: Optional[dict] = None
    report: Optional[dict] = None
    needs_override: Optional[bool] = None
    open_items: Optional[list] = None
    decision: Optional[str] = None
    decided_by: Optional[str] = None
    report_id: Optional[str] = None
    loop_count: Optional[int] = None


class StartRequest(BaseModel):
    supplier_id: str
    procurement_ref: str = "default"


class ResumeRequest(BaseModel):
    answer: Any = None
    question_id: Optional[str] = None


class DecideRequest(BaseModel):
    decision: Literal["approved", "conditional", "rejected"]
    decided_by: str
    conditions: Optional[str] = None
    notes: Optional[str] = None
    override_reason: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────
def _store():
    from storage.sqlite_store import SQLiteStore
    return SQLiteStore()


def _expired(valid_until: Optional[str]) -> bool:
    if not valid_until:
        return False
    try:
        return datetime.fromisoformat(valid_until).date() < date.today()
    except ValueError:
        return False


def _parts(thread_id: str) -> tuple[str, str]:
    sid, _, ref = thread_id.partition("__")
    return sid, (ref or "default")


def _to_status(s: dict) -> EvalStatus:
    return EvalStatus(**{k: s.get(k) for k in EvalStatus.model_fields})


def _latest_economic_class(supplier_id: str) -> Optional[str]:
    hist = get_decision_history(supplier_id)
    return hist[0].get("economic_class_at_decision") if hist else None


def _summary(store, sid: str, name: str) -> dict:
    p = store.get_company_profile(sid) or {}
    active = list_active_sessions(sid)
    return dict(
        supplier_id=sid, supplier_name=name,
        risk_class=p.get("risk_class"), qualification_status=p.get("qualification_status"),
        economic_classification=_latest_economic_class(sid),
        total_docs=p.get("total_docs", 0) or 0,
        open_nonconformances=len(store.get_current_facts(sid, category="nc")),
        last_eval_date=p.get("last_evaluation_date"),
        active_session=active[0]["thread_id"] if active else None)


# ── Supplier routes ───────────────────────────────────────────────────────────
@app.get("/suppliers", response_model=list[SupplierSummary])
def list_suppliers():
    store = _store()
    try:
        rows = store.list_suppliers()
    except Exception:
        return []
    return [SupplierSummary(**_summary(store, s["supplier_id"], s.get("supplier_name") or s["supplier_id"]))
            for s in rows]


@app.get("/supplier/{supplier_id}/profile", response_model=SupplierProfile)
def get_profile(supplier_id: str):
    store = _store()
    sup = store.get_supplier(supplier_id)
    if not sup:
        raise HTTPException(404, f"Supplier {supplier_id} not found")
    certs = [CertFact(value=f.get("value", ""), valid_until=f.get("valid_until"),
                      is_expired=_expired(f.get("valid_until")),
                      source_file=f.get("source_file"), source_page=f.get("source_page"),
                      confidence=f.get("confidence"))
             for f in store.get_current_facts(supplier_id, category="cert")]
    docs = store.get_document_history(supplier_id) or []
    return SupplierProfile(
        **_summary(store, supplier_id, sup.get("supplier_name") or supplier_id),
        active_certs=certs, document_history=[dict(d) for d in docs[-10:]],
        recent_decisions=get_decision_history(supplier_id)[:5])


# ── Document ingestion ────────────────────────────────────────────────────────
def _load_agent2_main():
    """Agent 2's main.py, loaded by path (both agents have a main.py)."""
    if "agent2_main" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "agent2_main", _ROOT / "agent2_vectorstore" / "main.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["agent2_main"] = mod
        spec.loader.exec_module(mod)
    return sys.modules["agent2_main"]


def _stable_supplier_id(name: str) -> str:
    digest = hashlib.sha1(name.strip().lower().encode()).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:32] or "supplier"
    return f"SUP-{slug}-{digest}"


@app.get("/_routes")
def list_routes():
    """Every route this API actually serves.

    Cheap, and it makes a missing router visible instead of a 404 in the UI.
    """
    return sorted(
        f"{sorted(r.methods)[0]:6} {r.path}"
        for r in app.routes
        if getattr(r, "methods", None) and not r.path.startswith("/openapi")
    )


@app.post("/ingest", response_model=IngestResponse)
async def ingest(background_tasks: BackgroundTasks, file: UploadFile = File(...),
                 supplier_id: Optional[str] = Form(None),
                 supplier_name: Optional[str] = Form(None),
                 target_table: Optional[str] = Form(None)):
    """The unified front door: ANY file is accepted.

    The file type is sniffed from its content, and the file is routed to the
    lane that fits it:

      document  PDF / DOCX / PPTX / TXT / MD  → Agent 1 parse → Agent 2
                pass 1 (store, chunk, embed) → pass 2 (LLM extraction) in
                the background
      tabular   CSV / TSV / XLSX / JSON / XML → routed to a target table,
                refined in Python, mirrored raw, indexed as row chunks
      raw       anything else → stored, described and indexed, flagged for
                review. Nothing is ever refused.

    Pass 2 (LLM extraction) still runs in the background, so the response
    returns immediately.
    """
    if not supplier_id and not (supplier_name and supplier_name.strip()):
        raise HTTPException(400, "supplier_id or supplier_name is required")
    content = await file.read()
    suffix = Path(file.filename or "").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        import ingest as unified

        result = unified.ingest_any(
            tmp_path, supplier_id=supplier_id, supplier_name=supplier_name,
            target_table=target_table, llm_refine=False,
        )
        if not result.get("ok"):
            raise HTTPException(400, result.get("error", "ingestion failed"))

        # LLM extraction in the background (documents and single-supplier
        # spreadsheets) — the response returns immediately.
        document_id = result.get("document_id")
        if document_id and not result.get("is_duplicate") and not result.get("llm_refined"):
            background_tasks.add_task(_pass2, document_id, result["supplier_id"])

        return IngestResponse(
            document_id=document_id or "", supplier_id=result["supplier_id"],
            is_duplicate=bool(result.get("is_duplicate")),
            chunks_created=result.get("chunks_created", 0),
            pass1_complete=True,
            pass2_complete=bool(result.get("llm_refined")),
            pass2_status=("skipped (duplicate)" if result.get("is_duplicate")
                          else ("done" if result.get("llm_refined") else "queued")),
            lane=result.get("lane"), detected_type=result.get("detected_type"),
            tables=result.get("tables", []),
            needs_review=bool(result.get("needs_review")),
            degraded=bool(result.get("degraded")),
            degraded_reason=result.get("degraded_reason"),
        )
    finally:
        tmp_path.unlink(missing_ok=True)


def _pass2(document_id: str, supplier_id: str) -> None:
    try:
        _load_agent2_main().agent2_pass2(document_id=document_id, supplier_id=supplier_id,
                                         sqlite_store=_store())
    except Exception as e:                      # background task: log, never crash the API
        print(f"[pass2] {supplier_id}/{document_id}: {type(e).__name__}: {e}")


# ── Evaluation routes ─────────────────────────────────────────────────────────
@app.post("/evaluation/start", response_model=EvalStatus)
def start_eval(body: StartRequest):
    if not _store().get_supplier(body.supplier_id):
        raise HTTPException(404, f"Supplier {body.supplier_id} not found")
    return _to_status(orch.start(body.supplier_id, body.procurement_ref))


@app.get("/evaluation/{thread_id}/status", response_model=EvalStatus)
def eval_status(thread_id: str):
    sid, ref = _parts(thread_id)
    return _to_status(orch.get_status(sid, ref))


@app.post("/evaluation/{thread_id}/resume", response_model=EvalStatus)
def resume_eval(thread_id: str, body: ResumeRequest):
    sid, ref = _parts(thread_id)
    cur = orch.get_status(sid, ref)
    if cur["status"] != "paused" or cur.get("waiting_for") != "human_answer":
        raise HTTPException(409, f"Evaluation is not waiting for an answer (status: {cur['status']})")
    answer = {body.question_id: body.answer} if body.question_id else body.answer
    return _to_status(orch.resume(sid, answer, ref))


@app.post("/evaluation/{thread_id}/decide", response_model=EvalStatus)
def decide(thread_id: str, body: DecideRequest):
    sid, ref = _parts(thread_id)
    cur = orch.get_status(sid, ref)
    if cur.get("waiting_for") != "final_decision":
        raise HTTPException(409, f"Evaluation is not waiting for a decision (status: {cur['status']})")
    if not body.decided_by.strip():
        raise HTTPException(400, "decided_by is required — VA26 requires attribution")
    if body.decision == "conditional" and not (body.conditions or "").strip():
        raise HTTPException(400, "conditions are required for a conditional decision")
    if cur.get("needs_override") and not (body.override_reason or "").strip():
        raise HTTPException(400, "The evaluation report is incomplete. An override_reason is "
                                 "required to decide anyway.")
    return _to_status(orch.resume(sid, {
        "decision": body.decision, "decided_by": body.decided_by.strip(),
        "conditions": body.conditions or "", "notes": body.notes or "",
        "override_reason": (body.override_reason or "").strip()}, ref))


@app.get("/evaluation/{thread_id}/report")
def get_report(thread_id: str):
    sid, ref = _parts(thread_id)
    report = get_latest_report(sid, ref)
    if not report:
        raise HTTPException(404, "No report found")
    return report


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
