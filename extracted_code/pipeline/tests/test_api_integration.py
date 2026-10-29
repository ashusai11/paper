"""
tests/test_api_integration.py — the API ↔ UI contract, and the real endpoints.

Two layers:

**1. Contract check (always runs, no FastAPI needed).**
Reads `api/main.py`, `api/tabular_routes.py` and `ui/api_client.py` as
source and proves that every endpoint the Streamlit page calls is actually
registered by the API. This is the check that catches a missing
`app.include_router(tabular_router)` — the bug where the "📊 Spreadsheet"
page looks fine but every call 404s, because the router was written and
never attached.

**2. Live check (needs fastapi + httpx).**
Boots the app with FastAPI's TestClient and exercises the real workflow:
upload → targets → import history, dry run (writes nothing), duplicate
upload (no duplicate rows), and a failed import (clear audit record).
It also drives the *UI's own client functions* over an ASGI transport, so
the exact code path the Streamlit page uses is the one under test.

    python tests/test_api_integration.py
"""

from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "agent2_vectorstore")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        FAILURES.append(name)


# ── 1. contract check (source-level) ─────────────────────────────────────────

def _tree(rel: str) -> ast.Module:
    return ast.parse((_ROOT / rel).read_text(encoding="utf-8"))


def api_router_paths(rel: str = "api/tabular_routes.py") -> set[str]:
    """The full paths a router in `rel` serves (prefix + route decorators)."""
    tree = _tree(rel)
    prefix = ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "router":
            for kw in getattr(node.value, "keywords", []):
                if kw.arg == "prefix":
                    prefix = ast.literal_eval(kw.value)
    paths: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            if dec.func.attr not in ("get", "post", "put", "delete", "patch"):
                continue
            if dec.args:
                try:
                    paths.add(prefix + ast.literal_eval(dec.args[0]))
                except Exception:
                    pass
    return paths


def main_app_paths(rel: str = "api/main.py") -> set[str]:
    """Paths registered directly on the app in `rel`."""
    tree = _tree(rel)
    paths: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                if dec.func.attr in ("get", "post", "put", "delete", "patch") and dec.args:
                    try:
                        paths.add(ast.literal_eval(dec.args[0]))
                    except Exception:
                        pass
    return paths


def include_router_calls(rel: str = "api/main.py") -> list[str]:
    tree = _tree(rel)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "include_router":
            out.append(ast.unparse(node))
    return out


def ui_endpoints(rel: str = "ui/api_client.py") -> set[str]:
    """The API URLs the UI actually calls."""
    tree = _tree(rel)
    urls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in ("_get", "_post"):
            if node.args and isinstance(node.args[0], ast.Constant) \
                    and isinstance(node.args[0].value, str):
                urls.add(node.args[0].value)
    return urls


def contract_check() -> None:
    print("\n[1] API ↔ UI contract (source-level)")
    calls = include_router_calls()
    check("api/main.py registers a router", bool(calls), str(calls))
    check("the registered router is the tabular one",
          any("tabular" in c for c in calls), str(calls))

    router_paths = api_router_paths()
    check("api/tabular_routes.py defines routes", bool(router_paths),
          str(router_paths))

    # A route only counts as served if its router is actually MOUNTED —
    # a router module that exists but was never included serves nothing.
    registered = any("tabular" in c for c in calls)
    served = main_app_paths() | (router_paths if registered else set())
    ui_urls = {u for u in ui_endpoints() if u.startswith("/tabular")}
    check("the UI calls the tabular endpoints", bool(ui_urls), str(ui_urls))
    missing = sorted(ui_urls - served)
    check("every endpoint the UI calls is served by the API",
          not missing, f"missing: {missing}")

    check("the unified /ingest route exists", "/ingest" in main_app_paths())
    check("the import-history route exists", "/tabular/imports" in served)
    check("the target-list route exists", "/tabular/targets" in served)
    check("the tabular upload route exists", "/tabular/ingest" in served)


# ── 2. live check (FastAPI TestClient) ──────────────────────────────────────

def live_check() -> bool:
    print("\n[2] Live endpoints (FastAPI TestClient)")
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        print("  SKIP  fastapi is not installed — run this on the server "
              "environment: pip install -r requirements.txt")
        return False

    tmp = Path(tempfile.mkdtemp(prefix="api_integration_"))
    os.environ["SUPPLIER_PIPELINE_DATA_DIR"] = str(tmp / "data")

    import api.main as api_main          # noqa: E402  (registers the routers)

    client = TestClient(api_main.app)

    # every route is actually mounted
    routes = client.get("/_routes")
    check("GET /_routes works", routes.status_code == 200, str(routes.status_code))
    served = routes.json() if routes.status_code == 200 else []
    for path in ("/tabular/targets", "/tabular/imports", "/tabular/ingest"):
        check(f"{path} is mounted", any(path in r for r in served), str(served))

    # a spreadsheet with one good and one broken row
    csv = ("Bestelldatum;Bestell-Nr;Artikel;Betrag;Lieferstatus\n"
           "01.03.2024;PO-1;Ventil;1.234,56;komplett\n"
           "kein Datum;PO-2;Kabel;120,00;offen\n")

    # --- dry run writes nothing -------------------------------------------
    dry = client.post("/tabular/ingest",
                      files={"file": ("buy.csv", csv.encode(), "text/csv")},
                      data={"supplier_id": "SUP-test-1", "dry_run": "true"})
    check("POST /tabular/ingest (dry run) answers 200", dry.status_code == 200,
          dry.text[:200])
    if dry.status_code == 200:
        body = dry.json()
        check("dry run reports the column mapping",
              bool(body.get("sheets")), str(body)[:200])
        check("dry run inserted nothing",
              all(s["rows"]["inserted"] == 0 for s in body["sheets"]),
              str(body["sheets"][0]["rows"]) if body.get("sheets") else "")

    # --- real upload -------------------------------------------------------
    up = client.post("/tabular/ingest",
                     files={"file": ("buy.csv", csv.encode(), "text/csv")},
                     data={"supplier_id": "SUP-test-1", "target_table": "purchase_history"})
    check("POST /tabular/ingest answers 200", up.status_code == 200, up.text[:300])
    if up.status_code == 200:
        rows = up.json()["sheets"][0]["rows"]
        check("one row inserted, one rejected", rows["inserted"] == 1
              and rows["failed"] == 1, str(rows))

    # --- target list -------------------------------------------------------
    targets = client.get("/tabular/targets")
    check("GET /tabular/targets answers 200", targets.status_code == 200,
          targets.text[:200])
    if targets.status_code == 200:
        keys = [t["key"] for t in targets.json()["targets"]]
        check("the target catalogue is served", "purchase_history" in keys, str(keys))
        check("the risk matrix target is served", "risk_matrix" in keys, str(keys))

    # --- import history ----------------------------------------------------
    history = client.get("/tabular/imports", params={"supplier_id": "SUP-test-1"})
    check("GET /tabular/imports answers 200", history.status_code == 200,
          history.text[:200])
    if history.status_code == 200:
        imports = history.json()["imports"]
        check("the import is in the history", len(imports) >= 1, str(len(imports)))
        failed = [i for i in imports if i["rows_failed"]]
        check("the rejected row is recorded in the audit trail",
              bool(failed), str(imports))
        if failed:
            check("the audit record says what happened",
                  failed[0]["status"] == "completed_with_errors",
                  failed[0]["status"])

    # --- duplicate upload --------------------------------------------------
    dup = client.post("/tabular/ingest",
                      files={"file": ("buy.csv", csv.encode(), "text/csv")},
                      data={"supplier_id": "SUP-test-1", "target_table": "purchase_history"})
    if dup.status_code == 200:
        rows = dup.json()["sheets"][0]["rows"]
        check("a duplicate upload writes no new rows",
              rows["inserted"] == 0 and rows["skipped"] >= 1, str(rows))

    # --- the UI's own client functions, over ASGI --------------------------
    import httpx
    from ui import api_client

    original_client = httpx.Client

    def patched_client(*args, **kwargs):
        kwargs.pop("transport", None)
        kwargs["transport"] = httpx.ASGITransport(app=api_main.app)
        kwargs.setdefault("base_url", "http://testserver")
        return original_client(*args, **kwargs)

    httpx.Client = patched_client
    try:
        ui_targets = api_client.list_tabular_targets()
        check("the UI can load the target list",
              any(t["key"] == "purchase_history" for t in ui_targets.get("targets", [])),
              str(ui_targets)[:200])
        ui_imports = api_client.list_tabular_imports("SUP-test-1")
        check("the UI can load the import history", len(ui_imports) >= 1,
              str(len(ui_imports)))
        ui_upload = api_client.ingest_tabular(
            csv.encode(), "ui.csv", supplier_id="SUP-test-ui",
            target_table="purchase_history")
        check("the UI can upload a spreadsheet",
              bool(ui_upload.get("sheets")), str(ui_upload)[:200])
    finally:
        httpx.Client = original_client

    return True


def main() -> int:
    print("=" * 70)
    print("API ↔ UI integration check")
    print("=" * 70)
    contract_check()
    live_check()
    print("\n" + "=" * 70)
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
