"""ui/api_client.py — every HTTP call to the FastAPI backend goes through here."""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

API_BASE = os.environ.get("SUPPLIER_API_URL", "http://localhost:8000")
TIMEOUT = 300.0     # an evaluation step can include several local-LLM calls


class ApiError(Exception):
    """An error answer from the API, carrying the server's explanation."""


def _check(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise ApiError(str(detail))


def _get(path: str, params: dict | None = None):
    with httpx.Client(base_url=API_BASE, timeout=TIMEOUT) as c:
        r = c.get(path, params=params or {})
        _check(r)
        return r.json()


def _post(path: str, json: dict | None = None, data: dict | None = None, files: dict | None = None):
    with httpx.Client(base_url=API_BASE, timeout=TIMEOUT) as c:
        r = c.post(path, json=json, data=data, files=files)
        _check(r)
        return r.json()


def list_suppliers() -> list[dict]:
    try:
        return _get("/suppliers")
    except Exception:
        return []


def get_supplier_profile(supplier_id: str) -> Optional[dict]:
    try:
        return _get(f"/supplier/{supplier_id}/profile")
    except Exception:
        return None


def ingest_document(file_bytes: bytes, filename: str, supplier_id: Optional[str] = None,
                    supplier_name: Optional[str] = None,
                    target_table: Optional[str] = None) -> dict:
    """Upload a file to the unified front door (POST /ingest).

    The API sniffs the file type and routes it to the right lane:
    document (PDF/DOCX/…), tabular (CSV/XLSX/JSON/XML) or raw (anything else).
    """
    data = {k: v for k, v in (("supplier_id", supplier_id),
                              ("supplier_name", supplier_name),
                              ("target_table", target_table)) if v}
    return _post("/ingest", data=data, files={"file": (filename, file_bytes, "application/octet-stream")})


def ingest_tabular(file_bytes: bytes, filename: str, supplier_id: Optional[str] = None,
                   supplier_name: Optional[str] = None, target_table: Optional[str] = None,
                   dry_run: bool = False) -> dict:
    """Upload a CSV/Excel file to the tabular ingestion lane."""
    data = {k: v for k, v in (
        ("supplier_id", supplier_id), ("supplier_name", supplier_name),
        ("target_table", target_table), ("dry_run", str(dry_run).lower()),
    ) if v}
    return _post("/tabular/ingest", data=data,
                 files={"file": (filename, file_bytes, "application/octet-stream")})


def list_tabular_targets() -> dict:
    try:
        return _get("/tabular/targets")
    except Exception:
        return {"targets": [], "routes": []}


def list_tabular_imports(supplier_id: Optional[str] = None) -> list[dict]:
    try:
        params = {"supplier_id": supplier_id} if supplier_id else {}
        return _get("/tabular/imports", params).get("imports", [])
    except Exception:
        return []


def start_evaluation(supplier_id: str, procurement_ref: str = "default") -> dict:
    return _post("/evaluation/start", json={"supplier_id": supplier_id, "procurement_ref": procurement_ref})


def get_evaluation_status(thread_id: str) -> dict:
    try:
        return _get(f"/evaluation/{thread_id}/status")
    except Exception as e:
        return {"status": "error", "thread_id": thread_id, "message": str(e)}


def resume_evaluation(thread_id: str, answer: Any, question_id: Optional[str] = None) -> dict:
    return _post(f"/evaluation/{thread_id}/resume", json={"answer": answer, "question_id": question_id})


def record_decision(thread_id: str, decision: str, decided_by: str, conditions: Optional[str] = None,
                    notes: Optional[str] = None, override_reason: Optional[str] = None) -> dict:
    return _post(f"/evaluation/{thread_id}/decide", json={
        "decision": decision, "decided_by": decided_by, "conditions": conditions,
        "notes": notes, "override_reason": override_reason})


def get_report(thread_id: str) -> Optional[dict]:
    try:
        return _get(f"/evaluation/{thread_id}/report")
    except Exception:
        return None
