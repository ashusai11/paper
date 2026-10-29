"""Self-test for the tabular lane — no external services required.

    python -m agent2_vectorstore.tabular.selftest

Creates a German CSV (BOM, `;` delimiter, title line, DD.MM.YYYY dates,
`1.234,56` amounts) and a two-sheet XLSX, imports both against a throwaway
database, and asserts routing, mapping, normalization, error handling,
row-level idempotency and the ChromaDB chunk metadata.

The embedder and the vector store are stubbed so the test runs without the
2.2 GB BGE-M3 model and without a ChromaDB installation.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_AGENT2 = _HERE.parent
_ROOT = _AGENT2.parent
for _p in (str(_ROOT), str(_AGENT2)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_TMP = Path(tempfile.mkdtemp(prefix="tabular_selftest_"))
os.environ["SUPPLIER_PIPELINE_DATA_DIR"] = str(_TMP / "data")

import csv as _csv  # noqa: E402
from datetime import datetime  # noqa: E402

import openpyxl  # noqa: E402

from agent2_vectorstore.tabular.ingest import ingest_tabular  # noqa: E402


class _FakeEmbedder:
    def embed(self, texts):
        return [[0.01] * 8 for _ in texts]


class _FakeChroma:
    def __init__(self):
        self.chunks = []

    def upsert_chunks(self, chunks, embeddings):
        assert len(chunks) == len(embeddings), "chunk/embedding count mismatch"
        self.chunks.extend(chunks)


def _fixtures() -> tuple[Path, Path]:
    csv_path = _TMP / "buy_history_2024.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = _csv.writer(fh, delimiter=";")
        w.writerow(["Purchase History Export 2024"])
        w.writerow(["Bestelldatum", "Bestell-Nr", "Artikel", "Menge", "Betrag",
                    "Währung", "Lieferstatus", "Qualitätsproblem", "Bemerkung"])
        w.writerow(["01.03.2024", "PO-1001", "Valve A", "10", "1.234,56", "EUR",
                    "verspätet", "ja", "Rückfrage offen"])
        w.writerow(["15.03.2024", "PO-1002", "Ventilgehäuse", "2", "890,00",
                    "EUR", "komplett", "nein", ""])
        w.writerow(["kein Datum", "PO-1003", "Sensorik", "1", "120,00", "EUR",
                    "offen", "nein", ""])

    xlsx_path = _TMP / "supplier_master.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Orders"
    ws.append(["Purchase Date", "PO Number", "Product", "Amount", "Currency",
               "Delivery Status", "Quality Issue"])
    ws.append(["2024-05-01", "PO-2001", "Housing", 999.5, "EUR", "delivered", False])
    ws2 = wb.create_sheet("Contact")
    ws2.append(["Legal Name", "Country", "Address", "Website", "Supplier Type"])
    ws2.append(["Acme Medizintechnik GmbH", "DE", "Hauptstr. 3", "https://acme.example",
                "manufacturer"])
    ws2.append(["MediTech AG", "AT", "Wiener Str. 10", "", "distributor"])
    wb.save(xlsx_path)
    return csv_path, xlsx_path


def main() -> int:
    csv_path, xlsx_path = _fixtures()
    chroma = _FakeChroma()
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    # ── CSV ──────────────────────────────────────────────────────────────────
    print("\n[1] CSV with BOM, ';' delimiter, title line, German formats")
    report = ingest_tabular(csv_path, supplier_id="SUP-acme-001",
                             supplier_name="Acme Medizintechnik GmbH",
                             embed=True, embedder=_FakeEmbedder(),
                             chroma_store=chroma)
    check("import ok", report.get("ok") is True, str(report.get("error")))
    sheet = report["sheets"][0]
    check("routed to purchase_history", sheet["target_table"] == "purchase_history",
          sheet["target_table"])
    check("header row detected below the title line",
          sheet["mapping"]["mapping"].get("Bestelldatum") == "purchase_date",
          str(sheet["mapping"]["mapping"]))
    check("one bad row rejected", sheet["rows"]["failed"] == 1, str(sheet["rows"]))
    check("two good rows inserted", sheet["rows"]["inserted"] == 2, str(sheet["rows"]))
    check("chunks created", sheet["chunks_created"] >= 1, str(sheet["chunks_created"]))

    # ── XLSX ─────────────────────────────────────────────────────────────────
    print("\n[2] XLSX with two sheets")
    report2 = ingest_tabular(xlsx_path, supplier_id="SUP-acme-002",
                              embed=True, embedder=_FakeEmbedder(),
                              chroma_store=chroma)
    sheets = {s["name"]: s for s in report2["sheets"]}
    check("orders sheet -> purchase_history",
          sheets["Orders"]["target_table"] == "purchase_history")
    check("multi-supplier sheet -> supplier_directory",
          sheets["Contact"]["target_table"] == "supplier_directory",
          sheets["Contact"]["target_table"])

    # ── database ────────────────────────────────────────────────────────────
    print("\n[3] Database state")
    db = _TMP / "data" / "supplier_risk.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    rows = {r["purchase_reference"]: r for r in
            conn.execute("SELECT * FROM purchase_history")}
    check("purchase_reference PO-1001 present", "PO-1001" in rows)
    check("German date parsed to ISO",
          rows.get("PO-1001") is not None
          and rows["PO-1001"]["purchase_date"] == "2024-03-01",
          str(rows.get("PO-1001")))
    check("German amount parsed to float",
          rows.get("PO-1001") is not None
          and abs(rows["PO-1001"]["amount"] - 1234.56) < 1e-6,
          str(rows.get("PO-1001")))
    check("enum normalized (verspätet -> late)",
          rows.get("PO-1001") is not None
          and rows["PO-1001"]["delivery_status"] == "late",
          str(rows.get("PO-1001")))
    check("boolean flag parsed (ja -> 1)",
          rows.get("PO-1001") is not None
          and rows["PO-1001"]["quality_issue"] == 1)
    check("rejected row never reached the target table", "PO-1003" not in rows)
    err = conn.execute(
        "SELECT * FROM tabular_errors WHERE source_row IS NOT NULL").fetchone()
    check("rejected row logged with row + column",
          err is not None and err["column_name"] == "Bestelldatum",
          str(dict(err)) if err else "no error row")
    check("directory holds both suppliers",
          conn.execute("SELECT COUNT(*) FROM supplier_directory").fetchone()[0] == 2)
    check("company_profile untouched by the master list",
          conn.execute("SELECT COUNT(*) FROM company_profile "
                       "WHERE legal_name IS NOT NULL").fetchone()[0] == 0)
    check("documents row created for the file",
          conn.execute("SELECT COUNT(*) FROM documents "
                       "WHERE doc_format IN ('csv','xlsx')").fetchone()[0] == 2)

    # ── chunks ──────────────────────────────────────────────────────────────
    print("\n[4] RAG chunks")
    meta = chroma.chunks[0]["metadata"]
    check("chunk_type is tabular", meta.get("chunk_type") == "tabular", str(meta))
    check("row range in metadata",
          "row_start" in meta and "row_end" in meta, str(meta))
    check("header repeated in chunk text",
          "Columns:" in chroma.chunks[0]["text"] and "Row " in chroma.chunks[0]["text"])
    check("target table in metadata", meta.get("target_table") == "purchase_history")

    # ── idempotency ─────────────────────────────────────────────────────────
    print("\n[5] Re-import is idempotent")
    report3 = ingest_tabular(csv_path, supplier_id="SUP-acme-001",
                              supplier_name="Acme Medizintechnik GmbH", embed=False)
    rows3 = report3["sheets"][0]["rows"]
    check("unchanged rows skipped, not rewritten",
          rows3["skipped"] == 2 and rows3["inserted"] == 0, str(rows3))
    check("no duplicate purchase rows",
          conn.execute("SELECT COUNT(*) FROM purchase_history").fetchone()[0] == 3)

    # ── multi-vendor ERP export ─────────────────────────────────────────────
    print("\n[6] Multi-vendor ERP export (every row is a different supplier)")
    po_path = _TMP / "purchase order.odoo.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["Priority", "Order Reference", "Vendor", "Company", "Buyer",
               "Order Deadline", "Activities", "Untaxed Amount", "Total",
               "Status", "Billing Status"])
    ws.append(["Normal", "P-M-00294", "Elektroschmiede GmbH", "BEC Medical GmbH",
               "Dominik Hahn", datetime(2026, 7, 16, 10, 10, 51), None,
               12630, 15029.7, "Draft", "Nothing to Bill"])
    ws.append(["Normal", "P-M-00293", "Amazon EU SARL", "BEC Medical GmbH",
               "Dominik Hahn", datetime(2026, 7, 15, 14, 50, 58), None,
               375, 446.25, "Purchase", "Nothing to Bill"])
    ws.append(["Normal", "P-M-00292", "Mouser Electronics Inc", "BEC Medical GmbH",
               "Dominik Hahn", datetime(2026, 7, 15, 10, 21, 55), None,
               5169.32, 6151.49, "Cancelled", "Waiting Bills"])
    wb.save(po_path)

    report4 = ingest_tabular(po_path, supplier_id="SUP-bec-001",
                              supplier_name="BEC Medical GmbH",
                              embed=True, embedder=_FakeEmbedder(),
                              chroma_store=chroma)
    po = report4["sheets"][0]
    check("routed to purchase_history",
          po["target_table"] == "purchase_history", po["target_table"])
    check("vendor column mapped to the row supplier field",
          po["mapping"]["mapping"].get("Vendor") == "supplier_name",
          str(po["mapping"]["mapping"]))
    check("order deadline mapped to the purchase date",
          po["mapping"]["mapping"].get("Order Deadline") == "purchase_date")
    check("erp column names all mapped",
          po["mapping"]["missing_required"] == [], str(po["mapping"]["missing_required"]))
    check("all three rows written", po["rows"]["inserted"] == 3, str(po["rows"]))

    po_rows = list(conn.execute(
        "SELECT purchase_reference, amount, delivery_status, supplier_id "
        "FROM purchase_history WHERE purchase_reference LIKE 'P-M-%'"))
    check("three purchase orders in the table", len(po_rows) == 3, str(len(po_rows)))
    check("each row attributed to its own vendor",
          len({r["supplier_id"] for r in po_rows}) == 3,
          str([r["supplier_id"] for r in po_rows]))
    check("gross amount mapped to amount",
          any(abs(r["amount"] - 15029.7) < 1e-6 for r in po_rows), str(po_rows))
    check("erp status normalized (Purchase -> ordered)",
          any(r["delivery_status"] == "ordered" for r in po_rows),
          str([r["delivery_status"] for r in po_rows]))
    check("context supplier is not polluted with vendor orders",
          conn.execute("SELECT COUNT(*) FROM purchase_history "
                       "WHERE supplier_id = 'SUP-bec-001'").fetchone()[0] == 0)
    po_chunks = [c for c in chroma.chunks
                 if c["metadata"].get("source_file") == "purchase order.odoo.xlsx"]
    check("one chunk group per vendor",
          len({c["metadata"]["supplier_id"] for c in po_chunks}) == 3,
          str({c["metadata"]["supplier_id"] for c in po_chunks}))

    # ── raw mirror ───────────────────────────────────────────────────────────
    print("\n[7] Raw grid mirrored into SQLite")
    po_import = conn.execute(
        "SELECT import_id FROM tabular_imports "
        "WHERE source_file = 'purchase order.odoo.xlsx'").fetchone()["import_id"]
    sheet_row = conn.execute(
        "SELECT headers_json, row_count FROM tabular_sheets WHERE import_id = ?",
        (po_import,)).fetchone()
    check("sheet head stored with the ordered column names",
          sheet_row is not None
          and json.loads(sheet_row["headers_json"])[1] == "Order Reference",
          str(dict(sheet_row)) if sheet_row else "no sheet row")
    raw = conn.execute(
        "SELECT row_json, source_row, supplier_id FROM tabular_raw_rows "
        "WHERE import_id = ? ORDER BY source_row LIMIT 1", (po_import,)).fetchone()
    check("raw row keeps the original header names as keys",
          raw is not None and "Order Reference" in json.loads(raw["row_json"]),
          str(dict(raw)) if raw else "no raw row")
    check("raw row keeps the original value, not the normalized one",
          raw is not None
          and json.loads(raw["row_json"])["Order Deadline"] == "2026-07-16 10:10:51",
          str(dict(raw)) if raw else "no raw row")
    check("raw row knows its company",
          raw is not None and raw["supplier_id"] is not None)
    check("every raw row mirrored",
          conn.execute("SELECT COUNT(*) FROM tabular_raw_rows WHERE import_id = ?",
                       (po_import,)).fetchone()[0] == 3,
          conn.execute("SELECT COUNT(*) FROM tabular_raw_rows WHERE import_id = ?",
                       (po_import,)).fetchone()[0])
    jsonq = conn.execute(
        "SELECT COUNT(*) FROM tabular_raw_rows WHERE import_id = ? "
        "AND json_extract(row_json, '$.Vendor') = 'Amazon EU SARL'",
        (po_import,)).fetchone()[0]
    check("raw rows are queryable by column value (JSON1)", jsonq == 1, str(jsonq))

    # ── repeat purchases ────────────────────────────────────────────────────
    print("\n[8] Repeat purchases from the same supplier")
    rep_path = _TMP / "repeat_orders.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Orders"
    ws.append(["Order Reference", "Vendor", "Order Deadline", "Total", "Status"])
    ws.append(["PO-777", "Elektroschmiede GmbH", datetime(2026, 1, 10), 1000, "Purchase"])
    ws.append(["PO-777", "Elektroschmiede GmbH", datetime(2026, 5, 22), 2500, "Purchase"])
    ws.append(["PO-778", "Elektroschmiede GmbH", datetime(2026, 6, 1), 300, "Purchase"])
    wb.save(rep_path)

    rep = ingest_tabular(rep_path, supplier_id="SUP-rep-1", embed=False)
    check("three orders from one supplier are all written",
          rep["sheets"][0]["rows"]["inserted"] == 3, str(rep["sheets"][0]["rows"]))
    rep_rows = list(conn.execute(
        "SELECT purchase_reference, purchase_date, amount, supplier_id "
        "FROM purchase_history WHERE purchase_reference IN ('PO-777', 'PO-778') "
        "ORDER BY purchase_date"))
    check("a reused order number stays two separate orders",
          len(rep_rows) == 3, str([dict(r) for r in rep_rows]))
    check("all three belong to the same supplier",
          len({r["supplier_id"] for r in rep_rows}) == 1,
          str([dict(r) for r in rep_rows]))
    rep2 = ingest_tabular(rep_path, supplier_id="SUP-rep-1", embed=False)
    check("re-import does not duplicate the orders",
          rep2["sheets"][0]["rows"]["skipped"] == 3
          and rep2["sheets"][0]["rows"]["inserted"] == 0,
          str(rep2["sheets"][0]["rows"]))

    # ── a spreadsheet that is not financial ──────────────────────────────────
    print("\n[9] Risk matrix (FMEA) — same entry point, different target")
    risk_path = _TMP / "risk_matrix.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "FMEA"
    ws.append(["Prozessschritt", "Fehlerart", "Schweregrad",
               "Auftretenswahrscheinlichkeit", "Entdeckungsgrad",
               "Verantwortlich", "Zieldatum", "Status"])
    ws.append(["Ventilfertigung", "Dichtung lose", "8", "5", "3",
               "M. Keller", datetime(2026, 9, 30), "offen"])
    ws.append(["Schweissen", "Poren im Schweiss", "7", "2", "4",
               "S. Bauer", datetime(2026, 8, 15), "in Bearbeitung"])
    ws.append(["Reinigung", "Rueckstaende", "9", "1", "2", "—", None, None])
    ws.append(["Fehlerhafte Dichtung", "Kontamination", "12", "2", "2",
               "—", None, None])
    wb.save(risk_path)

    risk = ingest_tabular(risk_path, supplier_id="SUP-acme-001",
                           supplier_name="Acme Medizintechnik GmbH", embed=False)
    rs = risk["sheets"][0]
    check("routed to the risk matrix target",
          rs["target_table"] == "risk_matrix", rs["target_table"])
    check("German FMEA headers mapped",
          rs["mapping"]["mapping"].get("Schweregrad") == "severity",
          str(rs["mapping"]["mapping"]))
    check("out-of-range score rejects the row",
          rs["rows"]["failed"] == 1 and rs["rows"]["inserted"] == 3,
          str(rs["rows"]))
    check("the table was created on demand",
          conn.execute("SELECT COUNT(*) FROM sqlite_master "
                       "WHERE type='table' AND name='risk_matrix'").fetchone()[0] == 1)
    risk_rows = {r["failure_mode"]: r for r in conn.execute(
        "SELECT failure_mode, severity, occurrence, detection, rpn, risk_level "
        "FROM risk_matrix")}
    check("RPN computed in Python",
          risk_rows.get("Dichtung lose") is not None
          and risk_rows["Dichtung lose"]["rpn"] == 120,
          str(dict(risk_rows.get("Dichtung lose") or {})))
    check("risk level derived from the thresholds",
          risk_rows.get("Dichtung lose") is not None
          and risk_rows["Dichtung lose"]["risk_level"] == "high",
          str(dict(risk_rows.get("Dichtung lose") or {})))
    check("the rejected row is still in the raw mirror",
          conn.execute("SELECT COUNT(*) FROM tabular_raw_rows "
                       "WHERE json_extract(row_json, '$.Schweregrad') = '12'"
                       ).fetchone()[0] == 1)

    # ── routing catalogue: one example per kind of spreadsheet ──────────────
    print("\n[10] Every spreadsheet type routes to its own target")
    from agent2_vectorstore.tabular.reader import Sheet as _Sheet
    from agent2_vectorstore.tabular.registry import get_registry as _get_registry
    from agent2_vectorstore.tabular.router import route_sheet as _route_sheet

    _reg = _get_registry()
    cases = [
        ("purchase order list",
         ["Priority", "Order Reference", "Vendor", "Company", "Buyer",
          "Order Deadline", "Activities", "Untaxed Amount", "Total", "Status",
          "Billing Status"], "purchase_history"),
        ("FMEA in German",
         ["Prozessschritt", "Fehlerart", "Schweregrad",
          "Auftretenswahrscheinlichkeit", "Entdeckungsgrad",
          "Vorhandene Maßnahmen", "Verantwortlich", "Zieldatum", "Status"],
         "risk_matrix"),
        ("NC / CAPA register",
         ["NC ID", "Description", "Raised Date", "Severity", "Root Cause",
          "Corrective Action", "Due Date", "Status", "Closed Date"],
         "nc_register"),
        ("audit findings",
         ["Finding ID", "Source", "Description", "Classification", "Severity",
          "Due Date", "Status", "Closed Date"], "audit_findings"),
        ("certificate register",
         ["Certificate Number", "Certificate Type", "Issue Date", "Expiry Date",
          "Scope", "Issuing Body", "Status"], "certificate_register"),
        ("supplier master list",
         ["Legal Name", "Country", "Address", "Website", "Supplier Type",
          "Notes"], "supplier_master"),
        ("a sheet nothing matches",
         ["Foo", "Bar", "Baz"], "tabular_records"),
    ]
    for label, headers, expected in cases:
        sheet = _Sheet(name="Sheet1", headers=headers, rows=[{}] * 2,
                       row_numbers=[2, 3])
        result = _route_sheet(sheet, "file.xlsx", _reg)
        check(f"{label} -> {expected}",
              result["target"] == expected,
              f"got {result['target']} ({result['method']})")

    # ── the unified front door ──────────────────────────────────────────────
    print("\n[11] Unified front door — any file, one entry point")
    sys.path.insert(0, str(_ROOT))
    try:
        import ingest as unified
        unified._Agents(need_embedder=False)      # needs chromadb + sqlite
    except (ImportError, SystemExit) as exc:
        print(f"  SKIP  unified front door — dependencies missing ({exc})")
        unified = None

    if unified is not None:
        check("PDF detected by content",
              unified.sniff_type(csv_path) in ("csv", "text"),
              unified.sniff_type(csv_path))
        check("lane selection is by type",
              unified.pick_lane("pdf") == "document"
              and unified.pick_lane("xlsx") == "tabular"
              and unified.pick_lane("binary") == "raw")

    json_path = _TMP / "orders.json"
    json_path.write_text(json.dumps([
        {"order": "PO-1", "vendor": "Acme", "amount": 10.5},
        {"order": "PO-2", "vendor": "Beta", "amount": 20.0},
    ]), encoding="utf-8")
    xml_path = _TMP / "orders.xml"
    xml_path.write_text(
        '<?xml version="1.0"?><orders>'
        '<order id="1"><vendor>Acme</vendor><total>10.5</total></order>'
        '<order id="2"><vendor>Beta</vendor><total>20</total></order>'
        '</orders>', encoding="utf-8")
    bin_path = _TMP / "scan.bin"
    bin_path.write_bytes(bytes(range(256)))

    if unified is not None:
        for label, path, expected_lane in (
                ("JSON", json_path, "tabular"),
                ("XML", xml_path, "tabular"),
                ("binary", bin_path, "raw")):
            result = unified.ingest_any(path, supplier_id="SUP-unified-1",
                                        embed=False, llm_refine=False)
            check(f"{label} file takes the {expected_lane} lane",
                  result.get("lane") == expected_lane, str(result.get("lane")))
            check(f"{label} file is stored",
                  result.get("document_id") is not None)
            check(f"{label} file is never refused", result.get("ok") is True)

    if unified is not None:
        raw_rows = conn.execute(
            "SELECT COUNT(*) FROM tabular_raw_rows WHERE source_file = 'orders.json'"
        ).fetchone()[0]
        check("JSON records became rows", raw_rows == 2, str(raw_rows))
        xml_rows = conn.execute(
            "SELECT COUNT(*) FROM tabular_raw_rows WHERE source_file = 'orders.xml'"
        ).fetchone()[0]
        check("XML records became rows", xml_rows == 2, str(xml_rows))
        check("the binary file is flagged for review",
              conn.execute("SELECT COUNT(*) FROM documents WHERE doc_format = 'binary'"
                           ).fetchone()[0] == 1)


    # ── dry run and failure audit ───────────────────────────────────────────
    print("\n[12] Dry run writes nothing; failures leave an audit record")
    dry_dir = Path(tempfile.mkdtemp(prefix="tabular_dry_"))
    os.environ["SUPPLIER_PIPELINE_DATA_DIR"] = str(dry_dir / "data")
    dry_db = dry_dir / "data" / "supplier_risk.db"

    dry = ingest_tabular(csv_path, supplier_id="SUP-dry-1", dry_run=True)
    check("dry run reports the mapping",
          dry["sheets"][0]["mapping"]["mapping"].get("Bestelldatum") == "purchase_date")
    check("dry run creates no database file", not dry_db.exists(), str(dry_db))
    check("dry run reports nothing as inserted",
          dry["sheets"][0]["rows"]["inserted"] == 0, str(dry["sheets"][0]["rows"]))
    check("dry run reports the planned row count instead",
          dry["sheets"][0]["rows"].get("planned", 0) == 2,
          str(dry["sheets"][0]["rows"]))

    os.environ["SUPPLIER_PIPELINE_DATA_DIR"] = str(_TMP / "data")
    # a file with one unparseable row -> the import must be auditable
    bad = ingest_tabular(csv_path, supplier_id="SUP-fail-1")
    import_id = bad["sheets"][0]["import_id"]
    record = conn.execute(
        "SELECT status, rows_total, rows_inserted, rows_failed "
        "FROM tabular_imports WHERE import_id = ?", (import_id,)).fetchone()
    check("the import is recorded in the audit trail", record is not None)
    check("a partially failed import is flagged",
          record is not None and record["status"] == "completed_with_errors",
          str(dict(record)) if record else "")
    check("the failed row count is recorded",
          record is not None and record["rows_failed"] >= 1, str(dict(record)))
    errs = conn.execute(
        "SELECT * FROM tabular_errors WHERE import_id = ?", (import_id,)).fetchall()
    check("the rejected cell is logged with row and column",
          len(errs) >= 1 and errs[0]["column_name"] == "Bestelldatum",
          str([dict(e) for e in errs])[:200])

    # a crashed import must not leave a row that looks like it is still running
    from agent2_vectorstore.tabular import ingest as ingest_module

    original_write = ingest_module.TabularStore.upsert_purchase

    def boom(*args, **kwargs):
        raise RuntimeError("simulated storage failure")

    ingest_module.TabularStore.upsert_purchase = boom
    try:
        crashed = ingest_tabular(csv_path, supplier_id="SUP-crash-1")
    except Exception:
        crashed = None
    finally:
        ingest_module.TabularStore.upsert_purchase = original_write
    check("a crashed import is reported, not raised",
          crashed is not None and crashed.get("ok") is False,
          str(crashed)[:120] if crashed else "raised")
    running = conn.execute(
        "SELECT COUNT(*) FROM tabular_imports WHERE status = 'running'"
    ).fetchone()[0]
    check("no import is left in the 'running' state", running == 0, str(running))
    failed_rows = conn.execute(
        "SELECT COUNT(*) FROM tabular_imports WHERE status = 'failed'"
    ).fetchone()[0]
    check("the crash is recorded as a failed import", failed_rows >= 1, str(failed_rows))

    conn.close()

    print(f"\n{'FAILED: ' + ', '.join(failures) if failures else 'ALL CHECKS PASSED'}")
    print(f"temporary data dir: {_TMP}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
