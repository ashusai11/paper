# AGENTS.md — Supplier Qualification Pipeline: Agent Operating Specification
**BEC Robotics · ISO 13485:2016 · VA26 · EU MDR 2017/745**

This document is the authoritative reference for every agent, module, and
data flow in the system. It is the first file a new developer (or a new
Claude session) should read.

---

## System Overview

The pipeline qualifies suppliers against VA26 requirements through three agents
that share one SQLite database and one ChromaDB vector index.

```
Document (PDF / DOCX)
        │
        ▼
┌──────────────┐   markdown + per-page JSON
│  Agent 1     │──────────────────────────────────────────────┐
│  Offline     │                                              │
│  Parser      │  No LLM. No network. Fully offline.         │
└──────────────┘                                              │
                                                              ▼
                                              ┌──────────────────────────┐
                                              │  Agent 2 — Pass 1        │
                                              │  Classify, chunk, embed,  │
                                              │  store in SQLite + Chroma │
                                              └──────────────┬───────────┘
                                                             │
                                              ┌──────────────▼───────────┐
                                              │  Agent 2 — Pass 2        │
                                              │  LLM field-group extract  │
                                              │  Certificates, dates, NCs │
                                              └──────────────┬───────────┘
                                                             │
                                              ┌──────────────▼───────────┐
                                              │  Agent 3 — Evaluation    │
                                              │  LangGraph orchestration  │
                                              │  VA26 risk + gate + econ  │
                                              │  Human questions via UI   │
                                              └──────────────┬───────────┘
                                                             │
                                              ┌──────────────▼───────────┐
                                              │  Human Reviewer          │
                                              │  Approve / Conditional /  │
                                              │  Reject via web UI       │
                                              └──────────────────────────┘
```

**The unified front door** — `ingest.py` accepts ANY file: it sniffs the
type from the content and routes to the document lane (Agent 1 + Agent 2),
the tabular lane (target table + raw mirror) or the raw lane (stored and
indexed, flagged for review). Nothing is ever refused. `POST /ingest` does
the same.

**Shared infrastructure (every agent uses the same files):**
- `config.py` — single source of truth for all file paths and LM Studio settings
- `agent2_vectorstore/storage/sqlite_store.py` — the system of record
- `agent2_vectorstore/storage/chromadb_store.py` — rebuildable vector search index
- `api/main.py` — FastAPI routes
- `ui/` — Streamlit frontend

---

## Global Rules (apply to every agent, always)

1. **Grounding.** Never state a fact not present in retrieved evidence.
   If evidence does not contain it, return `null` and set `status: "not_found"`.

2. **No invention.** Never guess a certificate number, date, address, or legal
   entity name. A missing value is a valid, expected result.

3. **Citations mandatory.** Every non-null extracted value carries
   `source_document_id`, `source_chunk_id`, `source_page`, and the verbatim
   `snippet` it came from.

4. **Structured output only.** Every agent returns a documented dict shape.
   On parse failure the degraded flags are set and the caller is informed.

5. **Determinism stays in code.** Date comparisons, expiry checks, completeness
   checks, scoring arithmetic, and VA26 rule lookups are Python. The LLM never
   computes them.

6. **Small-model discipline.** One narrow task per LLM call. Prompts must work
   on a 14B–20B local model. No multi-step reasoning chains in a single call.

7. **Language.** Documents may be in any EU language. Extracted values are
   returned in their original language. `snippet` is quoted verbatim.

8. **No side effects from agents.** Agents return data. Persistence, file
   writes, and status changes are performed by the orchestrator or the calling
   layer — never by an agent itself.

9. **Human decisions are never automated.** No agent produces an
   approve / conditional / reject outcome. That belongs exclusively to a human,
   captured via the `node_decision` interrupt in `graph.py`.

10. **LLM unavailability degrades gracefully.** Every LLM-dependent path
    returns `degraded=True` with a `degraded_reason` string rather than raising
    or returning empty data silently.

---

## Agent 1 — Offline Document Parser

| Property | Value |
|---|---|
| Entry point | `agent1_offline/main.py` → `parse_document(path, output_dir)` |
| LLM | None |
| Network | None |
| Input | File path (PDF or DOCX) |
| Output | `{"full_markdown", "pages", "page_count", "format"}` |

**What it does:**
Converts raw documents into structured markdown with per-page provenance.
Each page entry carries `page`, `text`, `is_scanned`, `extraction_method`
(`native` / `ocr` / `empty`), and `ocr_confidence`.

**Key modules:**
- `processors/anydoc_processor.py` — native text extraction (pypdfium2, python-docx)
- `processors/rapidocr_processor.py` — OCR for scanned pages (RapidOCR)
- `utils/file_detector.py` — detects format from content; extension as fallback
- `utils/page_detector.py` — labels each PDF page native / scanned / empty
- `utils/text_cleaner.py` — deterministic whitespace and artifact cleanup

**Rules:**
- pypdfium2 for native; RapidOCR as fallback for scanned pages
- Resource cleanup is mandatory (pypdfium2 bitmap/doc objects must be freed)
- Returns the per-page JSON as well as the assembled markdown — both are
  stored in SQLite so the chunker can use page boundaries

---

## Agent 2 — Document Storage and Retrieval

### Pass 1 — Store, chunk, embed, index

| Property | Value |
|---|---|
| Entry point | `agent2_vectorstore/main.py` → `agent2_pass1(...)` |
| LLM | None |
| Input | Parsed markdown + per-page JSON, supplier identity |
| Output | `{"document_id", "is_duplicate", "chunks_created", ...}` |

**What it does:**
Deduplicates (SHA-256 of markdown), stores the document in SQLite, chunks it
(page boundaries from JSON if available, markdown fallback), embeds with
BGE-M3, and upserts into ChromaDB. **D3 fix:** every chunk is also written to
the SQLite `chunks` table, making ChromaDB rebuildable.

### Pass 2 — LLM field-group extraction (Refinery)

| Property | Value |
|---|---|
| Entry point | `agent2_vectorstore/main.py` → `agent2_pass2(...)` |
| LLM | LM Studio (temperature 0.0) |
| Input | Stored document markdown, doc_type |
| Output | Structured facts written to SQLite; `{"refined", "doc_type", ...}` |

**What it does:**
Runs 7 focused LLM calls (M5 fix), one per field group, writing structured
facts with full provenance (chunk_id, page, snippet) to `profile_facts` and
`refined_data`. Returns `degraded=True` with a reason if LM Studio is
unreachable or all groups fail (D5 fix).

**Field groups (7 calls):**

| Group | Fields extracted |
|---|---|
| `identity` | supplier_name, legal_name, country, address, website |
| `certifications` | certifications list, iso_clauses list |
| `quality_system` | quality_system, capa_process, change_control, complaint_handling |
| `regulatory` | eu_mdr_role, notified_body, udi_capability, eudamed_registration |
| `dates` | date_issued, expiry_date |
| `risk_signals` | nonconformances, ctq_items, risk_signals, summary |
| `meta` | asl_status, supplier_type, risk_class |

**Key modules:**
- `refinery/classifier.py` — doc_type classification (rule-based, includes QAA rule)
- `refinery/extractor.py` — field-group LLM calls (M5 fix)
- `refinery/refiner.py` — orchestrates extraction, writes facts with provenance
- `storage/sqlite_store.py` — system of record (D8: config path, D5: degraded schema, D4: provenance)
- `storage/chromadb_store.py` — vector index
- `embeddings/bge_m3_embeddings.py` — offline BGE-M3
- `chunker/text_chunker.py` — page-level chunking with stable IDs

**Maintenance utilities:**
- `backfill_reclassify.py` — re-label documents stored before a classifier change
- `rebuild_index.py` — rebuild ChromaDB from SQLite chunks (no re-parsing needed)

### Pass 1b — Tabular lane (CSV / Excel)

> One entry point for **every** spreadsheet, not only financial data. A target
> (purchase history, risk matrix, NC register, audit findings, certificate
> register, supplier master) is a registry entry; generic targets get their
> SQLite table created on demand, and computed fields (RPN, risk level) are
> Python arithmetic, never a model call.

| Property | Value |
|---|---|
| Entry point | `agent2_vectorstore/tabular/ingest.py` → `ingest_tabular(path, supplier_id, ...)` |
| CLI | `python -m agent2_vectorstore.tabular.cli --file X.xlsx --supplier-id SUP-x [--dry-run]` |
| LLM | None (optional LM Studio fallback for ambiguous header routing only) |
| Input | CSV / TSV / XLSX / XLSM file |
| Output | rows in the target SQLite table + row-window chunks in ChromaDB |

**What it does:**
A spreadsheet is not a document — flattening it to markdown destroys the grid,
so tabular files get their own lane instead of Agent 1 + Pass 1:

1. **Route** the sheet to a target table (explicit override → registry route
   rules → header score → optional LLM → safe fallback `tabular_records`).
2. **Map** source columns to canonical fields (EN + DE alias table, fuzzy
   fallback). Unmapped columns are kept, never dropped.
3. **Refine** deterministically in Python (dates, numbers, booleans, enums,
   mojibake). Invalid cells reject the row and are logged in
   `tabular_errors` — the LLM never computes or guesses a value.
4. **Write** the rows into the routed table (natural-key upsert → idempotent
   re-import) with row-level provenance in `tabular_rows`. Files that name a
   supplier per row (ERP exports) are attributed to that supplier
   (`row_supplier_field`) — the uploaded supplier stays the context. A row is
   identified by `match_fields` (reference **and** date for purchase
   history), so an ERP that reuses an order number keeps every order.
5. **Index** the same rows as text chunks with the header repeated
   (`chunk_type="tabular"`, metadata `sheet_name` / `row_start` / `row_end`)
   → BGE-M3 → ChromaDB. Chunks are grouped per supplier so the ChromaDB
   `supplier_id` filter keeps working.
6. **Mirror the raw grid** — `tabular_sheets` stores the head (ordered column
   names) once per sheet, `tabular_raw_rows` stores every row verbatim with
   the original headers as keys, so a single row always explains itself and
   stays queryable with SQLite JSON1. Written for every row, including rows
   that were later rejected.

**Key modules:**
- `tabular/reader.py` — robust CSV/XLSX reading (encoding, delimiter, header
  detection, multi-sheet, merged headers, formula handling)
- `tabular/registry.py` — target tables, field aliases, computed fields,
  routing rules (editable: `<data_dir>/table_registry.json`; a new
  spreadsheet type = a new JSON entry, no Python)
- `tabular/router.py` — sheet → target table resolution
- `tabular/refine.py` — normalization, validation, column mapping
- `tabular/row_chunker.py` — row-window chunks for the RAG lane
- `tabular/tabular_store.py` — `tabular_imports` / `tabular_rows` /
  `tabular_errors` / `tabular_records` / `supplier_directory`
- `tabular/ingest.py` — orchestrator
- `api/tabular_routes.py` — `POST /tabular/ingest`, `GET /tabular/targets`,
  `GET /tabular/imports`, `GET /tabular/raw` (include the router in
  `api/main.py`)

Full design: see `TABULAR_INGEST.md`.

---

## Agent 3 — VA26 Evaluation Engine

### Orchestration (LangGraph)

| Property | Value |
|---|---|
| Entry point | `agent3_evaluator/orchestrator/graph.py` → `EvaluatorOrchestrator` |
| LLM | LM Studio (temperature 0.1); deterministic fallback if unreachable |
| Persistence | LangGraph `SqliteSaver` checkpointer |

**Graph nodes:**
```
START → node_audit → node_llm_act ──ask──→ node_ask_human → node_llm_act
                            │
                           done
                            │
                     node_build_report → node_human_decision → node_writeback → END
                            │
                       (blocked path)
                     node_blocked → node_audit
```

**Interrupt points:**
1. `node_ask_human` — one VA26 catalog question at a time (human intake answers)
2. `node_human_decision` — the final approve / conditional / reject (human only)

### Deterministic tools (no LLM)

| Tool | File | VA26 ref |
|---|---|---|
| `classify_risk` | `intake/risk_classifier.py` | §2.1.5 |
| `gate_check` | `intake/gate_engine.py` | §2.1.1.1 |
| `economic_eval` | `evaluation/economic.py` + `evaluation/economic_adapter.py` | §2.2.2 |
| `monitoring_plan` | `rules/va26.py` | monitoring intervals |

**D1 fix:** `ready_to_sell_md=True` always → Risk Class 1 (before this it could
produce Class 2 with `internal_control="high"`).

**D2 fix:** Zero gate items → `blocked`, never `approved`.

**FIX 2:** `gate_check` now passes the correct evidence arguments to
`build_gate()` (certifications, nonconformances, audit_facts, purchases,
profile, qaa_status, audit_status). Previously it passed `supplier_id=...`
with no evidence lists, which raised on every call.

**FIX 3:** `economic_eval` now uses `economic_adapter.py` which requires the
three human subjective scores. Missing scores → `incomplete`, not a guessed
neutral 3.

**Tool call boundary:**
The LLM decides **when** to call a tool. It does **not** supply the arguments.
`run_guarded_tool()` in `tools.py` builds arguments from (a) verified human
answers and (b) Agent 2 evidence. A tool whose prerequisite answers are missing
returns `{"status": "needs_input"}` rather than running with guessed values.

**Hard boundary — tools the LLM cannot call:**
`record_decision`, `save_intake`, any database write. The LLM reads and sequences;
the graph writes; the human decides.

### Key modules

| File | Purpose |
|---|---|
| `orchestrator/questions.py` | Fixed VA26 question catalog; question ordering and validation |
| `orchestrator/tools.py` | Tool schemas, guarded execution, prerequisite checks |
| `orchestrator/graph.py` | LangGraph graph: nodes, routing, interrupt logic |
| `orchestrator/context_builder.py` | Agent 2 data → LLM narrative |
| `orchestrator/session_store.py` | Session metadata persistence |
| `decision_log.py` | Append-only audit record (**FIX 1** — was missing from the package) |
| `report_store.py` | Immutable SQLite-backed evaluation reports (H5 fix) |
| `rules/va26.py` | VA26 as typed Enums: RiskClass, SupplierCriticality, Measure, etc. |
| `evaluation/economic_adapter.py` | Wraps `economic.py`; human scores 4–6 required, no silent defaults (**FIX 3**) |

---

## API — FastAPI Backend

`api/main.py` — run with `uvicorn api.main:app --reload --port 8000`

| Route | Method | Purpose |
|---|---|---|
| `/suppliers` | GET | List all suppliers with summary |
| `/supplier/{id}/profile` | GET | Full profile: certs, docs, decisions |
| `/ingest` | POST | Upload document → Agent 1 + Agent 2 pass 1 (pass 2 in background) |
| `/evaluation/start` | POST | Start a new evaluation |
| `/evaluation/{tid}/status` | GET | Current status (paused / running / complete) |
| `/evaluation/{tid}/resume` | POST | Send one human answer to the paused graph |
| `/evaluation/{tid}/decide` | POST | Record the final decision |
| `/evaluation/{tid}/report` | GET | Fetch the built report |

**Validation enforced by the API (HTTP 400 / 409):**
- `/decide` with `decision="conditional"` and no `conditions` → 400
- `/decide` on an incomplete report with no `override_reason` → 400
- `/resume` when the evaluation is not waiting for an answer → 409
- `/decide` when the evaluation is not waiting for a decision → 409

---

## UI — Streamlit Frontend

`ui/app.py` — run with `streamlit run ui/app.py`

| Page | File | What it shows |
|---|---|---|
| Suppliers | `ui/pages/suppliers.py` | List with status badges and filters |
| Profile | `ui/pages/profile.py` | Certs, document history, decision log |
| Evaluate | `ui/pages/evaluate.py` | The 6-state evaluation wizard |
| Upload | `ui/pages/upload.py` | Document upload with pass 2 progress |

**Evaluation wizard states:**
1. `not_started` → Start button
2. `paused / human_answer` → Question form (one question, submitted or skipped)
3. `running` → Spinner + 3-second polling
4. `ready_for_human_review` → Full report + decision panel
5. `complete` → Confirmed decision
6. `blocked` → Blocker message + action buttons

---

## Database Schema (SQLite — one file, all agents)

Path: `config.get_db_path()` → `<data_dir>/supplier_risk.db`

| Table | Written by | Purpose |
|---|---|---|
| `suppliers` | Agent 2 pass 1 | Supplier registry |
| `documents` | Agent 2 pass 1 | Raw markdown + per-page JSON |
| `chunks` | Agent 2 pass 1 | Chunk text + metadata (D3: source of truth for ChromaDB) |
| `refined_data` | Agent 2 pass 2 | Per-document extraction result + degraded flags (D5) |
| `company_profile` | Agent 2 pass 2, Agent 3 writeback | Latest aggregated profile |
| `profile_facts` | Agent 2 pass 2 | Individual facts with chunk provenance (D4) |
| `purchase_history` | Agent 2 / API | Order-level delivery and quality records |
| `evaluation_reports` | Agent 3 report_store | Immutable reports (H5: content-hashed) |
| `evaluation_sessions` | Agent 3 session_store | Session metadata and last interrupt payload |
| `decision_log` | Agent 3 decision_log | Append-only audit record of all decisions |
| `tabular_imports` | Agent 2 tabular lane | One row per spreadsheet import: route, mapping, row counts |
| `tabular_rows` | Agent 2 tabular lane | Row-level provenance: file, sheet, source row, natural key, action |
| `tabular_errors` | Agent 2 tabular lane | Rejected cells: row, column, message, raw value |
| `tabular_records` | Agent 2 tabular lane | Safe landing zone for sheets that match no target table |
| `tabular_sheets` | Agent 2 tabular lane | The head of every imported sheet: the ordered column names |
| `tabular_raw_rows` | Agent 2 tabular lane | The raw grid row by row, verbatim (original headers as keys) |
| `supplier_directory` | Agent 2 tabular lane | Master lists containing many suppliers (separate from `company_profile`) |
| `checkpoints_*` | LangGraph SqliteSaver | Graph state (separate `_checkpoints.db` file) |

---

## Fixes Applied (chronological)

| ID | File(s) | Description |
|---|---|---|
| D8 | `config.py`, `sqlite_store.py`, `main.py`, `auto_linker.py` | Unified database path — was split across two different .db files |
| H2 | `config.py` | LM Studio defaults to `localhost:1234` (was a literal placeholder string) |
| D1 | `intake/risk_classifier.py` | `ready_to_sell_md=True` always → Class 1 |
| D2 | `intake/gate_engine.py` | Zero gate items → `blocked`, not `approved` |
| D5 | `refinery/extractor.py`, `sqlite_store.py` | `llm_used` / `degraded` / `degraded_reason` flags always returned |
| D3 | `agent2_vectorstore/main.py` | Chunks written to SQLite so ChromaDB is rebuildable |
| M5 | `refinery/extractor.py` | 7 focused field-group calls replaced one large prompt |
| H5 | `agent3_evaluator/report_store.py` | Immutable append-only reports in SQLite |
| D4 | `sqlite_store.py`, `refinery/refiner.py` | `source_chunk_id` + `source_page` + `snippet` on every profile fact |
| FIX 1 | `decision_log.py` | The final decision was never recorded — module was missing from the package |
| FIX 2 | `orchestrator/tools.py`, `orchestrator/questions.py` | `gate_check` passed wrong arguments to `build_gate()`; raised on every call |
| FIX 3 | `evaluation/economic_adapter.py`, `orchestrator/tools.py` | `economic_eval` called functions that do not exist in `economic.py` |
| FIX 4 | `agent1_offline/__init__.py` | `main.py` imported `__version__` from a package that did not define it — Agent 1 could not be imported at all |
| FIX 5 | `requirements.txt` | `firecrawl-anydoc` was missing although every Agent 1 module imports `anydoc` — a fresh install could not parse a single PDF |
| FIX 6 | `api/main.py` | the tabular router was written but never registered — the "📊 Spreadsheet" page called `/tabular/*` endpoints that 404'd. `app.include_router(tabular_router)` + `GET /_routes` to make mounted routes visible |
| FIX 8 | `storage/sqlite_store.py`, `tabular/facts.py` | `profile_facts` conflict detection treated `(supplier, category, field_name)` as a single value — a supplier with two certificates kept only the last one, and the context printed "ISO 13485 NOT FOUND" although it was on file. `add_profile_fact(..., fact_key=...)` identifies the *item*; spreadsheets can now project certificates / NCs / audits / risks into `profile_facts` (purchase history deliberately does not) |
| FIX 7 | `tabular/ingest.py`, `tabular/tabular_store.py` | a dry run created the database; a crashed import left a row in `running` forever. Dry run now touches nothing, a crash is recorded as `status='failed'` |
| QAA | `refinery/classifier.py` | 10 EN/DE patterns for Quality Assurance Agreement documents |

---

## Entry Points

```bash
# Unified front door — ANY file (sniffs the type, picks the lane)
python ingest.py report.pdf     --supplier-name "Acme Medizintechnik GmbH"
python ingest.py buy_history.xlsx --supplier-id SUP-acme-001
python ingest.py ./inbox/       --supplier-id SUP-acme-001 --dry-run
#   lanes: document (anydoc/OCR) | tabular (target table) | raw (stored as-is)
#   POST /ingest does the same through the API.

# Document ingestion (batch / CLI)
python run_pipeline.py ./docs/ --supplier-name "Acme Medizintechnik GmbH"
python run_pipeline.py cert.pdf --supplier-id SUP-acme-001 --skip-pass2

# Spreadsheet ingestion (CSV / Excel)
python -m agent2_vectorstore.tabular.cli --list-targets
python -m agent2_vectorstore.tabular.cli --file buy_history.xlsx --supplier-id SUP-acme-001 --dry-run
python -m agent2_vectorstore.tabular.cli --file buy_history.xlsx --supplier-id SUP-acme-001

# Tests (contract + behaviour)
python tests/test_api_integration.py          # API ↔ UI contract, live endpoints
python -m agent2_vectorstore.tabular.selftest # ingestion behaviour, 70+ checks
python tests/test_fact_projection.py           # spreadsheet → profile_facts semantics

# Database maintenance
python agent2_vectorstore/backfill_reclassify.py --dry-run  # re-label after classifier change
python agent2_vectorstore/rebuild_index.py --dry-run         # check ChromaDB drift
python agent2_vectorstore/rebuild_index.py                   # rebuild ChromaDB from SQLite

# API
uvicorn api.main:app --reload --port 8000

# UI (separate terminal)
streamlit run ui/app.py
```

---

## What Is NOT in This Package

These features were designed and built in earlier sessions but are not in the
current package and would need to be merged from earlier deliveries:

- **`run_pipeline.py --evaluate` branch** — the old one-shot evaluate-after-ingest
  flag imported from the v8 Agent 3 architecture. That architecture no longer
  exists; evaluation is now interactive via the UI.
- **CSV purchase history importer** — **now included** as the Agent 2
  tabular lane (`agent2_vectorstore/tabular/`, see `TABULAR_INGEST.md`).
  Buy-history still has to be entered manually until that lane is wired to
  the source system.
- **Re-evaluation / monitoring workflow** — VA26 §3.2 triggered re-evaluation
  (interval-based and event-driven). Designed but not built.
- **Conflict resolver** — when two documents give different values for the same
  field, the last-written value wins silently.
- **Gap analyst** — structured supplier follow-up email when required documents
  are missing.
- **Langfuse tracing** — observability for LLM calls. `requirements.txt` lists
  it as optional.
