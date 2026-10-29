"""Certificate register (spreadsheet) → profile_facts → the gate engine's view.

Proves the answer to "should a financial CSV also feed company facts":
  * purchase history  → NO facts (the orders are the economic evidence)
  * certificate register → cert facts with valid_until, readable by the
    context builder and the certification criterion
"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent2_vectorstore.tabular.ingest import ingest_tabular
from agent2_vectorstore.tabular.registry import get_registry

failures = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if not ok:
        failures.append(f"{name} — {detail}")


tmp = tempfile.mkdtemp(prefix="tabular_facts_")
os.environ["SUPPLIER_PIPELINE_DATA_DIR"] = tmp
data_dir = Path(tmp)

# ── a certificate register, as a supplier would send it ────────────────────
cert_csv = data_dir / "certificates.csv"
cert_csv.write_text(
    "Certificate Number,Certificate Type,Issued Date,Expiry Date,Scope\n"
    "DE-ISO13485-2024,ISO 13485,2024-01-15,2027-01-14,Design and manufacture of medical devices\n"
    "DE-ISO9001-2025,ISO 9001,2025-03-01,2028-02-29,Quality management\n",
    encoding="utf-8",
)

report = ingest_tabular(
    cert_csv, supplier_id="SUP-CERT-001", supplier_name="Muster Medizintechnik GmbH",
    target_table="certificate_register", embed=False, store=None,
)

print("\n[1] The certificate register reaches profile_facts")
check("import succeeded", report.get("ok") is True, str(report.get("error")))
sheet = (report.get("sheets") or [{}])[0]
check("routed to certificate_register",
      sheet.get("target_table") == "certificate_register", str(sheet.get("target_table")))
check("rows written", sheet.get("rows", {}).get("inserted") == 2,
      str(sheet.get("rows")))
check("facts written", sheet.get("facts_written") == 2, str(sheet.get("facts_written")))

db = data_dir / "supplier_risk.db"
conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row
facts = conn.execute(
    "SELECT * FROM profile_facts WHERE supplier_id=? AND category='cert'",
    ("SUP-CERT-001",),
).fetchall()
check("two cert facts in the database", len(facts) == 2, f"got {len(facts)}")

values = [f["value"] for f in facts]
check("the cert type is in the value (the '13485 NOT FOUND' check needs it)",
      any("13485" in v for v in values), str(values))
check("the certificate number is in the value",
      any("DE-ISO13485-2024" in v for v in values), str(values))
check("expiry date is stored as valid_until",
      any(f["valid_until"] == "2027-01-14" for f in facts),
      str([f["valid_until"] for f in facts]))
check("issue date is stored as valid_from",
      any(f["valid_from"] == "2024-01-15" for f in facts),
      str([f["valid_from"] for f in facts]))
check("every fact has a provenance snippet",
      all(f["snippet"] for f in facts), str([f["snippet"] for f in facts]))
check("every fact points at the document",
      all(f["source_document_id"] for f in facts),
      str([f["source_document_id"] for f in facts]))
check("the source page names the sheet and row",
      any("certificates!" in str(f["source_page"]) for f in facts),
      str([f["source_page"] for f in facts]))
check("each fact carries its own item key",
      len({f["fact_key"] for f in facts}) == 2, str([f["fact_key"] for f in facts]))

print("\n[2] The context builder sees what it needs")
from agent3_evaluator.orchestrator.context_builder import build_context

ctx = build_context("SUP-CERT-001")
text = ctx if isinstance(ctx, str) else json.dumps(ctx, default=str)
check("certificates appear in the evaluation context",
      "13485" in text, text[:400])
check("no 'ISO 13485 NOT FOUND' warning", "NOT FOUND" not in text,
      text[:400])

print("\n[3] Purchase history must NOT become facts")
po_csv = data_dir / "purchase.csv"
po_csv.write_text(
    "Order Reference,Order Date,Vendor,Total,Delivery Status\n"
    "PO-001,2026-03-01,Acme GmbH,1250.00,delivered\n"
    "PO-002,2026-04-02,Acme GmbH,800.50,late\n",
    encoding="utf-8",
)
po_report = ingest_tabular(
    po_csv, supplier_id="SUP-PO-001", supplier_name="Buyer GmbH",
    target_table="purchase_history", embed=False, store=None,
)
po_sheet = (po_report.get("sheets") or [{}])[0]
check("the orders went into purchase_history",
      po_sheet.get("rows", {}).get("inserted") == 2, str(po_sheet.get("rows")))
check("no facts were projected from purchase history",
      po_sheet.get("facts_written", 0) == 0, str(po_sheet.get("facts_written")))

po_facts = conn.execute(
    "SELECT COUNT(*) AS n FROM profile_facts WHERE supplier_id=?", ("SUP-PO-001",)
).fetchone()["n"]
check("the database holds no duplicate copy of the orders", po_facts == 0, str(po_facts))

purchases = conn.execute(
    "SELECT COUNT(*) AS n FROM purchase_history"
).fetchone()["n"]
check("the orders are readable as purchase history", purchases == 2, str(purchases))
purch_vendors = conn.execute(
    "SELECT DISTINCT supplier_id FROM purchase_history"
).fetchall()
check("each order is attributed to the vendor named in the row",
      len(purch_vendors) == 1 and purch_vendors[0][0] != "SUP-PO-001",
      str([r[0] for r in purch_vendors]))

print("\n[4] Re-importing the same certificate file does not duplicate facts")
again = ingest_tabular(
    cert_csv, supplier_id="SUP-CERT-001", supplier_name="Muster Medizintechnik GmbH",
    target_table="certificate_register", embed=False, store=None,
)
facts_after = conn.execute(
    "SELECT COUNT(*) AS n FROM profile_facts WHERE supplier_id=? AND category='cert'",
    ("SUP-CERT-001",),
).fetchone()["n"]
check("still two cert facts after the second import", facts_after == 2, str(facts_after))

print("\n[4b] A CHANGED certificate supersedes the old one (no stale pile-up)")
# the SAME certificate number, extended to a new expiry date
cert_csv.write_text(
    "Certificate Number,Certificate Type,Issued Date,Expiry Date,Scope\n"
    "DE-ISO13485-2024,ISO 13485,2024-01-15,2029-01-31,Design and manufacture\n"
    "DE-ISO9001-2025,ISO 9001,2025-03-01,2028-02-29,Quality management\n",
    encoding="utf-8",
)
ingest_tabular(cert_csv, supplier_id="SUP-CERT-001", supplier_name="Muster Medizintechnik GmbH",
               target_table="certificate_register", embed=False, store=None)
current = conn.execute(
    "SELECT value, valid_until FROM profile_facts "
    "WHERE supplier_id=? AND category='cert' AND is_current=1",
    ("SUP-CERT-001",),
).fetchall()
check("two certificates on file, both current",
      len(current) == 2, str([dict(r) for r in current]))
check("the renewed certificate replaced the old expiry",
      any(r["valid_until"] == "2029-01-31" for r in current)
      and not any(r["valid_until"] == "2027-01-14" for r in current),
      str([dict(r) for r in current]))
check("the superseded row is kept for the audit trail",
      conn.execute(
          "SELECT COUNT(*) FROM profile_facts WHERE supplier_id=? AND is_current=0",
          ("SUP-CERT-001",)).fetchone()[0] >= 1)

print("\n[5] The registry declares the projections")
reg = get_registry()
check("certificate_register declares a cert projection",
      bool(reg["targets"]["certificate_register"].get("facts")))
check("purchase_history declares none (orders are the evidence, not facts)",
      not reg["targets"]["purchase_history"].get("facts"))

conn.close()

print("\n" + ("=" * 70))
if failures:
    print(f"{len(failures)} CHECK(S) FAILED")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("ALL CHECKS PASSED")
print(f"temporary data dir: {tmp}")
