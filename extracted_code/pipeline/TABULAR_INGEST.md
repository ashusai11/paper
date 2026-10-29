# Tabular Ingestion (CSV / Excel) — design & operating manual

**Scope:** how a spreadsheet (purchase history, supplier master list, NC log,
certificate register) becomes rows in the right SQLite table *and* searchable
chunks in ChromaDB — inside the existing three-agent architecture.

New code lives in `agent2_vectorstore/tabular/` (see `AGENTS.md`).

---

## 1. The problem with "just add CSV to the RAG pipeline"

Your Agent 1 already handles CSV — `anydoc` converts it to markdown, and
`file_detector.py` even documents the signature-less-CSV quirk. So the
"easy" path is: upload CSV → same pipeline as PDF.

That path is wrong for structured data, for three reasons:

1. **The grid is destroyed.** `anydoc` flattens a spreadsheet into a markdown
   table. Once flattened, `Bestelldatum | Bestell-Nr | Betrag` becomes prose.
   You can no longer write `("2024-03-01", "PO-1001", 1234.56)` into
   `purchase_history` — you only have a blob of text.
2. **Row-level truth is lost.** A row that failed validation must be
   *rejected and reported*, not silently embedded as text. "No invention"
   (AGENTS.md rule 2) means a broken date must not become a plausible-looking
   date in the vector index.
3. **You lose the ledger.** Purchase history is the input for continuous
   monitoring and for the economic evaluation (VA26 §2.2.2). It has to be a
   table with `purchase_date`, `amount`, `quality_issue` — queryable, not
   searchable. AGENTS.md already lists *"CSV purchase history importer"* as
   missing.

**So: a spreadsheet is not a document. It needs a second ingestion lane.**

---

## 2. The design: two lanes, one import

```
              file (csv / xlsx)
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
   LANE A (structured)         LANE B (RAG)
   route → map columns         rows → text chunks
   → normalize/validate        (header repeated per chunk)
   → upsert into the           → BGE-M3 embed
     "respected" table         → ChromaDB upsert
        │                           │
        └────────► documents row ◄──┘
             (one row per file → dedup + versioning)
```

Both lanes write to the same SQLite file, use the same `document_id`, and
share the same supplier. Nothing new to keep in sync.

### Lane A — structured (the "respected tables")

| Step | Who decides | Notes |
|------|-------------|-------|
| Route: which table? | rules → header score → (optional) LLM → safe fallback | always reports method + confidence |
| Map columns → canonical fields | alias table (EN + DE) + fuzzy match | unmapped columns are **kept**, never dropped |
| Normalize | Python only | dates, numbers, booleans, enums, mojibake |
| Validate | Python only | required fields, unparseable values → row rejected + logged |
| Write | SQL upsert | natural key → idempotent re-import |

### Lane B — RAG

Rows are re-serialized as text **with the header repeated**, because
`Betrag=1250,00` is meaningless without knowing that `Betrag` is the amount
column:

```
File: buy_history_2024.csv | Sheet: Orders | Table: purchase_history
Columns: Bestelldatum | Bestell-Nr | Artikel | Menge | Betrag | Währung | ...

Row 3: Bestelldatum=01.03.2024 | Bestell-Nr=PO-1001 | Artikel=Valve A | Betrag=1.234,56 | ...
Row 4: Bestelldatum=15.03.2024 | Bestell-Nr=PO-1002 | ...
```

Chunk metadata (`sheet_name`, `row_start`, `row_end`, `target_table`,
`source_file`) makes the citation precise: *"late deliveries → sheet Orders,
rows 3–4 of buy_history_2024.csv"*.

---

## 3. The decisions (and the alternatives you rejected)

### 3.1 Reading: `openpyxl` + stdlib `csv`, not pandas

| Option | Verdict |
|--------|---------|
| **openpyxl + csv module** (implemented) | ✅ works offline, no heavy deps, cell-level control, `data_only=True` for formulas, `read_only=True` for big files |
| pandas | overkill here; pulls numpy; `read_excel` hides formula/cached-value and merged-cell behaviour that matters for audit trails |
| anydoc for everything | flattens the grid → Lane A impossible |
| polars | fastest, but one more dependency for a 10 MB file |

`openpyxl` is the only new dependency (`requirements.txt`).

**Excel specifics that are handled:** multi-sheet, formulas read as cached
values (fallback to formula text when the file has no cached values), merged
header cells forward-filled, header row detected below title junk, `data_only`
so `=SUM(...)` never ends up in your evidence.

`.xls` (BIFF) is **not** supported — openpyxl cannot read it. The error
message says exactly that instead of failing silently. Convert once to
`.xlsx`.

### 3.2 Chunking: row windows, not markdown tables

* Chunk = 12 rows (configurable) + the header line.
* `chunk_type = "tabular"` → you can filter Chroma results with
  `where={"chunk_type": "tabular"}` and keep document chunks separate.
* The standard `TextChunker` is *not* used for tabular text: it splits on
  headings/paragraphs and re-inserts whole markdown tables, which produces
  huge chunks and loses row numbers. `row_chunker.py` is ~120 lines and does
  exactly what a spreadsheet needs.
* Rows-per-chunk is the only knob. 12 rows ≈ 600–900 tokens — good for
  BGE-M3 and for the hybrid BM25 component.

### 3.3 Routing a sheet to a table: 5 fallbacks, never a guess

1. **Explicit override** — `--target-table` / API form field / UI dropdown.
2. **Registry route rules** — file name pattern, sheet name, header contains
   (`*buy*history*` → `purchase_history`).
3. **Header score** — how many of the target's fields (weighted: required
   fields count double) the header matches. Ties broken by target priority.
4. **LLM fallback** — one narrow LM Studio call, only if 1–3 are unsure;
   degrades to `None` when the model is unreachable (AGENTS.md rule 10).
5. **Safe fallback** — `tabular_records`: the rows are stored verbatim with
   full provenance and flagged `needs_review`. *Nothing is ever dropped.*

The result always carries `method`, `confidence` and `reason`, and the UI
shows it. A reviewer can always see *why* a sheet landed in a table.

### 3.4 "Refining" — deterministic, not LLM

The refinery (Pass 2) in Agent 2 runs 7 LLM calls for *narrative* documents.
For a spreadsheet that would be wrong: an LLM that "reads" `01.03.2024` may
return `2024-01-03` (US order) or invent a date when the cell says
`kein Datum`. AGENTS.md rule 5 says determinism stays in code — so does the
tabular lane:

| Concern | Handled by |
|---------|-----------|
| `01.03.2024`, `2024-03-01`, `2024/03/01`, `1.3.24`, `März 2024`, Excel serial `45356` | `parse_date` → ISO |
| `1.234,56`, `1,234.56`, `(123,45)`, `EUR 1 250,00`, `12 %` | `parse_number` → float |
| `ja / nein / true / 0 / x / ✓` | `parse_bool` |
| `komplett / verspätet / offen` | enum alias table → `delivered / late / open` |
| UTF-8 read as cp1252 (`WÃ¤hrung`) | mojibake repair |
| required field missing / unparseable value | row **rejected**, logged in `tabular_errors`, import continues |

A rejected row never reaches the target table — but it *does* reach
`tabular_errors` with file, sheet, row number, column and raw value, so the
gap is visible instead of silent.

### 3.5 Idempotency: two levels of dedup

* **File level** — `documents.document_hash` (existing mechanism) gives you
  "same file, already stored" and keeps document versioning.
* **Row level** — the target's *natural key* (`purchase_reference` for
  purchase history, `legal_name` for supplier data) plus a payload hash:
  * new key → `inserted`
  * existing key, same content → `skipped` (no write at all)
  * existing key, changed content → `updated` (configurable: `update` |
    `skip` | `error` per target)

Re-running the same import twice does not duplicate rows.

### 3.6 ERP exports where every row is a different supplier

The most common real spreadsheet is an ERP purchase-order list: one row per
order, **one column naming the vendor**, 50+ different vendors in one file.
Uploaded for the buying company ("BEC Medical GmbH"), it must not become
279 purchase orders of BEC Medical.

Targets can declare a **row supplier field**:

```json
"purchase_history": {
  "row_supplier_field": "supplier_name",
  ...
}
```

Then, for every row:

* the vendor name is resolved to a `supplier_id` — existing supplier first
  (reusing the project's `AutoLinker` name matching: normalization + bigram
  and token similarity), otherwise a new supplier is created once;
* the row is written to `purchase_history` **under that vendor**;
* the supplier you uploaded for stays the *context* (the buying company) and
  owns the `documents` row and the import record.

Consequences worth knowing:

* One file can create 100+ supplier records — that is a feature for a
  supplier-qualification system (it is how you discover who you buy from),
  but review the new suppliers before qualifying them.
* Chunks are grouped per supplier, so the ChromaDB `supplier_id` filter
  still works (`where={"supplier_id": "..."}`).
* `Mouser Electronics` in one export and `Mouser Electronics Inc` in another
  resolve to the **same** supplier — the fuzzy matcher merges them.

### 3.7 Fields that are not table columns

A registry field marked `"table_column": false` is mapped, stored in the row
payload and indexed for search, but **not** written into the SQL table.
`purchase_history` uses this for ERP columns that have no column in the
table but must not be lost: `supplier_name`, `net_amount`, `buyer`,
`company`, `priority`, `billing_status`, `order_status`.

Everything that *does* have a column (`purchase_date`, `purchase_reference`,
`product_or_service`, `quantity`, `amount`, `currency`, `delivery_status`,
`quality_issue`, `notes`) is written to the table.

### 3.8 Provenance: every row knows where it came from

New tables (added, nothing existing changed):

| Table | Purpose |
|-------|---------|
| `tabular_imports` | one row per file/sheet import: route, mapping, counts, status |
| `tabular_rows` | row-level provenance: file, sheet, source row, natural key, payload, action, `document_id` |
| `tabular_errors` | rejected cells: file, sheet, row, column, message, raw value |
| `tabular_records` | the safe landing zone for unrouted sheets (verbatim payload) |
| `tabular_sheets` | the head of every imported sheet: the ordered column names, once |
| `tabular_raw_rows` | the raw grid, row by row, verbatim (original headers as keys) |
| `supplier_directory` | master lists with many suppliers (kept apart from `company_profile`) |

`supplier_directory` exists for a specific reason: a supplier master list
contains *many* suppliers. Writing it into `company_profile` would overwrite
the profile of the supplier you are currently qualifying. Files with a single
supplier still go to `company_profile`; files with more than one distinct
legal name are automatically redirected to `supplier_directory` and the route
reason says so.

### 3.9 Buying from the same supplier again and again

This is the normal case, not an edge case: 279 orders in your export come
from 120 vendors — Amazon EU SARL alone accounts for 32 of them.

What happens, per row:

| Step | Result |
|------|--------|
| Supplier resolution | the **first** row of a vendor resolves the name; every later row finds the same supplier → one supplier record, not 32 |
| Row write | one `purchase_history` row per **order** — 32 rows for Amazon, all with the same `supplier_id` |
| Raw mirror | 32 raw rows, all attributed to that supplier |
| Chunks | the vendor's rows are grouped together — 3 chunks for Amazon (12 rows each), each carrying that `supplier_id`, so `where={"supplier_id": …}` returns exactly their orders |
| Re-import | all 32 come back as `skipped` — same payload hash, nothing rewritten |

That is what makes the economics work: `economic.py` counts late deliveries
over *all* of a supplier's purchases, and `context_builder.py` reports
"n purchases · late/failed deliveries x/n · quality issues y/n" — which
only means something if the repeat orders are all there.

**A trap worth knowing:** some ERPs reuse the same order number for several
orders. A row is therefore identified by **reference *and* date**
(`match_fields`), not by the reference alone — otherwise the second order
would overwrite the first and the amount would silently disappear. Two orders
with one number stay two orders; the same order re-imported with a corrected
amount is updated.

### 3.10 The raw grid in SQLite — every row keeps its heads

The normalized tables answer questions ("which orders were late?") but they
are lossy by design: the original header names live in the import's mapping,
and a normalized date is no longer the string the supplier sent.

So every import also writes a **raw mirror**:

| Table | Content |
|-------|---------|
| `tabular_sheets` | one row per sheet: the **head** — the ordered column names — plus the preamble and the row count |
| `tabular_raw_rows` | one row per raw data row: `row_json` keyed by the **original headers**, values exactly as they were in the file, plus the resolved `supplier_id` and the source row number |

A raw row therefore explains itself — no join needed to know which company it
belongs to or what every cell means:

```json
{
  "Priority": "Normal",
  "Order Reference": "P-M-00294",
  "Vendor": "Elektroschmiede GmbH",
  "Company": "BEC Medical GmbH",
  "Buyer": "Dominik Hahn",
  "Order Deadline": "2026-07-16 10:10:51",
  "Activities": null,
  "Untaxed Amount": 12630,
  "Total": 15029.7,
  "Status": "Draft",
  "Billing Status": "Nothing to Bill"
}
```

and it is queryable with plain SQL (SQLite JSON1 is built in):

```sql
-- every Amazon order, straight from the raw grid
SELECT source_row,
       json_extract(row_json, '$.Order Reference')  AS ref,
       json_extract(row_json, '$.Total')            AS total
FROM   tabular_raw_rows
WHERE  json_extract(row_json, '$.Vendor') = 'Amazon EU SARL';

-- all raw rows of one company
SELECT * FROM tabular_raw_rows WHERE supplier_id = 'AMEUSA001';
```

Raw rows are written for **every** row, including rows that were later
rejected — the raw copy is the truth, the normalized table is the
interpretation. If the mapping was wrong, the raw data is still there to
re-process.

`GET /tabular/raw?supplier_id=…&sheet_name=…` serves the same data over the
API.

---

## 3.11 One entry point for every spreadsheet, not just financial data

The lane is **not** a purchase-order importer with a narrow field list. A
spreadsheet is described entirely by a **registry entry**:

```json
"risk_matrix": {
  "kind": "generic",
  "table": "risk_matrix",
  "match_fields": ["process_item", "failure_mode"],
  "fields": {
    "severity":   {"type": "score", "required": true, "min": 1, "max": 10,
                   "aliases": ["schweregrad", "s", "s (1-10)"]},
    "rpn":        {"type": "computed", "compute": "rpn",
                   "factors": ["severity", "occurrence", "detection"]},
    "risk_level": {"type": "computed", "compute": "threshold_level",
                   "source": "rpn",
                   "thresholds": [{"max": 39, "value": "low"},
                                  {"max": 99, "value": "medium"},
                                  {"value": "high"}]}
  }
}
```

* **The table is created on demand** from the registry (`kind: "generic"`) —
  a new kind of spreadsheet needs **no Python at all**, just JSON.
* **Field types**: `text`, `date`, `number`, `int`, `bool`, `enum`, `score`
  (bounded, e.g. 1–10) and `computed`.
* **Computed fields** are arithmetic in Python, never a model call
  (AGENTS.md rule 5): `rpn` = severity × occurrence × detection, and the risk
  level comes from thresholds *you* define in the registry.
* **A score outside its range rejects the row** (a severity of 12 is a data
  error, not a severity) — the raw row still lands in the raw mirror.

### The target catalogue (all VA26-relevant types ship in the box)

| Target | Table | What it is | VA26 link |
|--------|-------|-----------|-----------|
| `purchase_history` | `purchase_history` | orders, amounts, delivery status | §2.2.2 economic evaluation |
| `risk_matrix` | `risk_matrix` | FMEA: severity / occurrence / detection → RPN, risk level | §2.1.1.1 Measure 6 (risk analysis) |
| `nc_register` | `nc_register` | nonconformities and CAPA | complaints / NC evidence |
| `audit_findings` | `audit_findings` | findings from internal and supplier audits | §2.1.1.1 Measure 2 (supplier audit) |
| `certificate_register` | `certificate_register` | certificates with issue and expiry dates | §2.1.1.1 Measure 4 (cert evidence) |
| `supplier_master` | `company_profile` | one supplier's master data | supplier identity |
| `supplier_directory` | `supplier_directory` | master lists with many suppliers | supplier discovery |
| `tabular_records` | `tabular_records` | anything that matches no target | safe landing zone |

### Routing is checked against the whole catalogue

Each sheet is scored against **every** registered target:

* **required-field recall** — how many of the target's required fields matched
* **precision** — how much of *this* sheet the target explains (a match
  through a generic alias like "number" or "id" counts less than a match
  through "Bestell-Nr")

The winner has to be clearly ahead, otherwise the sheet goes to the safe
landing zone and is flagged for review. The self-test asserts all of it:

```
purchase order list -> purchase_history    FMEA in German -> risk_matrix
NC / CAPA register  -> nc_register          audit findings -> audit_findings
certificate register-> certificate_register supplier list  -> supplier_master
a sheet nothing matches -> tabular_records
```

---

## 3.12 The unified front door — any file, one entry point

`ingest.py` (pipeline root) is the superset: it sniffs the file type from
its **content** and routes the file to the lane that fits it.

```
one file → sniff → lane → store → index
                        │
   document ────────────┤  PDF · DOCX · PPTX · ODT · RTF · EPUB · TXT · MD · HTML
   (anydoc → Agent 1)   │  → Agent 2 pass 1 (store, chunk, embed)
                        │  → pass 2 (LLM) → profile_facts
                        │
   tabular ─────────────┤  CSV · TSV · XLSX · XLSM · JSON · JSONL · XML
   (route → refine)     │  → target table + raw mirror + row chunks
                        │
   raw ─────────────────┘  everything else (images, archives, legacy binaries)
                           → hashed, stored, descriptor indexed, flagged for review
```

**Nothing is ever refused.** A file the pipeline cannot parse still lands in
SQLite, is findable by name, and is marked `needs_review` so a human knows
to look at it.

| Where | How |
|---|---|
| CLI | `python ingest.py anything.xlsx --supplier-id SUP-acme-001` |
| API | `POST /ingest` (one route, dispatches internally; `/ingest/tabular` stays for explicit targeting) |
| UI | the "📄 Upload" page now accepts any file and shows which lane took it |

The three lanes end in the same two places — the SQLite file (system of
record) and ChromaDB (rebuildable index) — so the LLM and the search never
care where the content came from.

**The LLM layer sees tabular content too.** After a single-supplier
spreadsheet import, pass 2 runs on the sheet markdown, so a certificate or
an NC that lives in a spreadsheet becomes a `profile_fact` with provenance
instead of sitting in a table nobody reads. Multi-vendor exports skip it
(the facts would belong to a vendor, not to the supplier the file was
uploaded for) and say so in the report.

### Two pre-existing bugs this surfaced

Both were in the *document* lane and would have bitten a fresh install:

1. `agent1_offline/main.py` does `from agent1_offline import __version__`,
   but `agent1_offline/__init__.py` never defined it → **importing Agent 1
   raised ImportError**. Fixed by defining `__version__` in the package.
2. `requirements.txt` did not list `firecrawl-anydoc`, although every Agent
   1 module does `import anydoc` → `pip install -r requirements.txt` gave
   you a pipeline that could not parse a single PDF. Fixed by adding
   `firecrawl-anydoc>=0.2.0`.

Agent 1 is also now loaded **lazily** by the front door: a spreadsheet-only
install does not need anydoc or OCR, and the document lane reports the
missing dependency clearly instead of the whole front door failing to
start.

---

## 3.13 Spreadsheet → company facts: what goes where

A spreadsheet can be *financial records* (orders) **or** *supplier facts*
(certificates, nonconformities, audits, risks). They must not land in the
same place, because the downstream code reads them differently:

| Sheet | Structured table | `profile_facts` | Why |
|---|---|---|---|
| `purchase_history` | ✅ `purchase_history` | ❌ **no facts** | the orders *are* the economic evidence — `economic.py` and `context_builder.py` read the table directly. A second copy in facts would double-count n purchases, the late rate and the spend |
| `certificate_register` | ✅ `certificate_register` | ✅ `cert` | the certification criterion reads `category='cert'` facts with `valid_until`; without them the supplier looks uncertified |
| `nc_register` | ✅ `nc_register` | ✅ `nc` | the nonconformity criterion reads `category='nc'` facts |
| `audit_findings` | ✅ `audit_findings` | ✅ `audit` | the supplier-audit criterion reads `category='audit'` facts |
| `risk_matrix` | ✅ `risk_matrix` | ✅ `risk` | the evaluation context shows `category='risk'` facts as RISK SIGNALS |

The projection is **declared in the registry**, not in code:

```json
"facts": [
  {"category": "cert", "field_name": "certification",
   "value": "{certificate_type} ({certificate_number})",
   "fact_key": "certificate_number",
   "valid_from": "issued_date", "valid_until": "expiry_date"}
]
```

* `value` — a template over the mapped columns. If a placeholder has no
  value in the row, **no fact is written** — a half-filled value
  ("ISO 13485 ()") is worse than no fact.
* `fact_key` — the identity of the *item* (the certificate number, the NC
  id). Without it two certificates of the same supplier look like a
  conflict with each other and only the last one stays current.
* It is **deterministic** — the values are already parsed and canonical,
  so no model is involved (AGENTS.md rule 5).
* Every fact carries its provenance: document, sheet and row
  (`source_page = "certificates.csv!2"`), the chunk it lives in, and the
  snippet it was read from.

The import report shows the count: `"facts_written": 2`.

### The multi-valued fact bug this exposed

`profile_facts` conflict detection treated
`(supplier_id, category, field_name)` as identifying a *single* value.
A supplier with two certificates therefore kept only the second one as
`is_current=1` — and the evaluation context printed:

```
CERTIFICATIONS:
  • iso_9001 (DE-ISO9001-2025) — valid until 2028-02-29
  ISO 13485 NOT FOUND among certificates on file
```

...although ISO 13485 was on file. The same bug hit the PDF lane, where
the refinery wrote every certificate of a document under the same
`field_name`.

Fix: `add_profile_fact(..., fact_key=...)`. With a key, the fact identity
is the *item*:

| Situation | Result |
|---|---|
| two different certificates | both current |
| the same certificate re-imported unchanged | no-op (no duplicate) |
| the same certificate with a new expiry | the old one is superseded (`is_current=0`, kept for the audit trail), the new one is current |
| a changed value for a keyed item | same: old superseded, new current |

Without a key the behaviour is unchanged — single-valued fields (an
address, a summary) still supersede each other, which is what you want.

---

## 3.14 The API ↔ UI contract is tested

A router that exists but was never mounted is the quietest failure there
is: the page renders, the button works, and every call 404s. So the
contract is asserted in `tests/test_api_integration.py`:

* **Contract check (no FastAPI needed)** — reads `api/main.py`,
  `api/tabular_routes.py` and `ui/api_client.py` as source and proves that
  every endpoint the Streamlit page calls is *mounted* (not merely defined).
  Un-mounting the router fails the test with
  `missing: ['/tabular/imports', '/tabular/ingest', '/tabular/targets']`.
* **Live check (needs fastapi + httpx)** — boots the app with FastAPI's
  TestClient and exercises the real workflow: upload → targets → import
  history, plus **dry run writes nothing**, **a duplicate upload writes no
  new rows**, and **a failed import leaves a clear audit record**. It also
  drives the *UI's own client functions* over an ASGI transport, so the
  exact code path the Streamlit page uses is the one under test.

```
python tests/test_api_integration.py        # contract + live
python -m agent2_vectorstore.tabular.selftest   # ingestion behaviour
```

### What the audit trail guarantees

| Situation | What you find in `tabular_imports` |
|---|---|
| clean import | `status = completed`, row counts |
| some rows rejected | `status = completed_with_errors`, `rows_failed > 0`, the rejected cells in `tabular_errors` |
| the import crashed | `status = failed` with the error message — **never** a row left in `running` |
| dry run | **no row at all** — not even the database file is created; the report says `would write = N` |

---

## 4. Verified against a real ERP export

`Purchase Order (purchase.order).xlsx` (Odoo export, 279 orders, 121 vendors,
11 columns) — the exact file that motivated this lane:

```
Sheet     : Sheet1
  -> table   : purchase_history (method=header_score, confidence=0.85)
  -> columns : Priority->priority, Order Reference->purchase_reference,
               Vendor->supplier_name, Company->company, Buyer->buyer,
               Order Deadline->purchase_date, Untaxed Amount->net_amount,
               Total->amount, Status->delivery_status,
               Billing Status->billing_status
  -> kept as extra columns: Activities          (empty in all 279 rows)
  -> rows    : total=279 inserted=279 updated=0 skipped=0 failed=0
  -> chunks  : 125 (grouped per vendor, 120 distinct supplier_ids)
```

* 279 purchase orders, **0 failed rows**, 121 suppliers created
  (120 vendors + the context company — `Mouser Electronics` was merged into
  the existing `Mouser Electronics Inc`).
* `Order Deadline` (a real datetime) → `2026-07-16`; `Total` → `amount`;
  `Untaxed Amount` → `net_amount`; `Status` → `delivery_status`
  (`Purchase` → `ordered`, `Draft` → `draft`, `Cancelled` → `cancelled`).
* Re-importing the same file: `skipped=279`, no duplicate rows, no new
  suppliers.
* The context supplier (BEC Medical) has **zero** purchase orders — the
  orders belong to their vendors.

**One caveat to decide on:** cancelled orders are stored like any other
order, so they sit in the denominator of the delivery-reliability score
(`economic.py` counts `late/delayed/failed` over *all* purchases). If you
want cancelled orders excluded from the scoring, filter
`delivery_status != 'cancelled'` in `context_builder.py` / `economic.py` —
that is a metric decision, not an ingestion one.

---

## 5. The table registry — configuration, not code

`<data_dir>/table_registry.json` (created on first run). Everything the
pipeline needs to know about a target table lives there:

```json
{
  "decimal_separator": "auto",
  "dayfirst": true,
  "targets": {
    "purchase_history": {
      "kind": "purchase_history",
      "table": "purchase_history",
      "natural_key": ["purchase_reference"],
      "on_existing": "update",
      "row_supplier_field": "supplier_name",
      "fields": {
        "purchase_date":   {"type": "date",   "required": true,
                            "aliases": ["datum", "bestelldatum", "lieferdatum"]},
        "purchase_reference": {"type": "text", "required": true,
                            "aliases": ["bestell-nr", "bestellnummer", "po number"]},
        "delivery_status": {"type": "enum",
                            "aliases": ["lieferstatus", "status"]}
      },
      "enum_values": {
        "delivery_status": {"komplett": "delivered", "verspätet": "late",
                            "offen": "open", "unterwegs": "in_transit"}
      }
    }
  }
}
```

* `aliases` are matched after normalization (`Bestell-Nr.` → `bestell_nr`).
* `"table_column": false` → metadata-only field (payload + search, no SQL
  column). `purchase_history` uses it for `supplier_name`, `net_amount`,
  `buyer`, `company`, `priority`, `billing_status`, `order_status`.
* `"row_supplier_field"` → every row is attributed to the supplier named in
  that field (ERP exports with many vendors).
* Add a column alias → every file with that header now maps automatically.
* Add a new target table → new `kind` (see §7) or reuse `raw_records`.

---

## 6. Using it

### CLI (no server needed)

```bash
# what would happen? nothing is written
python -m agent2_vectorstore.tabular.cli --file buy_history_2024.xlsx \
    --supplier-id SUP-acme-001 --supplier-name "Acme Medizintechnik GmbH" --dry-run

# real import
python -m agent2_vectorstore.tabular.cli --file buy_history_2024.xlsx \
    --supplier-id SUP-acme-001

# force a table, import a whole folder
python -m agent2_vectorstore.tabular.cli --file ./inbox/ \
    --supplier-id SUP-acme-001 --target-table purchase_history

# which tables can it route to?
python -m agent2_vectorstore.tabular.cli --list-targets
```

### API

The tabular router is **registered in `api/main.py`** (it has to be — the
unified `/ingest` route does not register it for you):

```python
from api.tabular_routes import router as tabular_router
app.include_router(tabular_router)
```

`GET /_routes` lists every route the API actually serves, so a missing
router is visible in one call instead of a 404 in the UI.

| Route | Purpose |
|-------|---------|
| `POST /tabular/ingest` | upload a file (form: `supplier_id`, `supplier_name`, `target_table`, `dry_run`) |
| `GET /tabular/targets` | registered target tables + route rules |
| `GET /tabular/imports` | import history with row counts |
| `GET /tabular/imports/{id}` | one import incl. its row errors and sheet heads |
| `GET /tabular/raw` | the raw grid, row by row (`supplier_id`, `sheet_name`, `vendor`) |

### UI

`ui/pages/tabular_upload.py` — new "📊 Spreadsheet" page: pick supplier,
optionally force a target table, **Dry run** preview (column mapping, row
counts, rejected rows) then **Import now**.

---

## 7. What still needs you

* **New target table for a new kind of file** (e.g. a certificate register):
  add a target in the registry with `kind: "raw_records"` (goes to
  `tabular_records` with full provenance) or implement a new `kind` writer
  (see §7) — ~30 lines in `tabular_store.py`.
* **Value mapping** (e.g. `delivery_status` has a free-text value your
  supplier invented) — add it to `enum_values`; unknown values are kept
  verbatim and flagged, never dropped.
* **.xls files** — convert to .xlsx.

---

## 8. Extension point: a new `kind`

`tabular_store.py` implements three writers today:

| `kind` | writes to | upsert key |
|--------|-----------|-----------|
| `purchase_history` | `purchase_history` | `purchase_reference` |
| `supplier_profile` | `company_profile` | `supplier_id` |
| `supplier_directory` | `supplier_directory` | `legal_name` + context supplier |
| `raw_records` | `tabular_records` | row hash |

To add a new one: implement `upsert_<kind>(...)` on `TabularStore`, add the
`elif kind == "<kind>"` branch in `ingest.py`, and register the target. The
routing, mapping, normalization, validation, chunking and provenance all
work unchanged.

---

## 9. Honest limitations

* **Merged data cells** are not forward-filled (only merged *header* cells
  are) — a merged value cell would land as empty. If your files use merged
  data cells, pre-flatten them or extend `reader.py`.
* **Formulas** are read as their cached value; a file written by a tool that
  never calculated (openpyxl, some exports) has no cached values, and the
  fallback keeps the formula text — which will not parse as a number and
  will be reported as a row error.
* **Header detection is heuristic.** It picks the first row whose cells are
  mostly text and whose width matches the rows below. If a file has a title
  block, a merged logo cell and a "generated on" line, check the dry run.
  A header repeated *inside* the data (page breaks in ERP exports) is
  detected and skipped instead of becoming a fake order.
* **The row chunk text is not a table.** It is `Column=Value` pairs. That is
  deliberate (stable, token-friendly, citation-friendly) but it is not a
  markdown table, so an LLM asked to "show me the table" will reconstruct it
  rather than quote it.
* **Conflicts across files** (two files disagreeing about the same order)
  are still last-write-wins — the conflict resolver listed as missing in
  AGENTS.md is not part of this lane.
* **Vendor name merging** is fuzzy (`AutoLinker`, threshold 0.85): two
  spellings of the same company become one supplier, and two *different*
  companies with very similar names could be merged as well. Review
  `tabular_rows` before qualifying a newly discovered supplier.
* **Performance**: rows are processed one at a time in Python. A 50 k-row
  file takes a few seconds — fine for supplier data; if you need bulk
  loading, batch the SQLite inserts (the writer is the bottleneck, not the
  parser).
