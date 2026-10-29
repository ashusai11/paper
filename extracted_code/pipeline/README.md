# Supplier Qualification Pipeline — BEC Robotics
**ISO 13485 · VA26 · EU MDR 2017/745**

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure LM Studio URL
cp .env.example .env
# Edit .env → set LM_STUDIO_URL to your LM Studio machine

# 3. Start LM Studio, load your model, start the server

# 4. Start the API
uvicorn api.main:app --reload --port 8000

# 5. Start the UI (separate terminal)
streamlit run ui/app.py

# 6. Ingest documents from the command line
python run_pipeline.py ./supplier_docs/ --supplier-name "Acme Medizintechnik GmbH"
```

## Directory Structure

```
pipeline/                             ← project root (add this to sys.path)
├── config.py                         ← MUST be at the root; all paths live here
├── run_pipeline.py                   ← CLI ingest: Agent 1 → Agent 2
├── requirements.txt
├── .env.example
├── AGENTS.md                         ← full operating specification
│
├── agent1_offline/                   ← import as: agent1_offline
│   ├── main.py                       ← parse_document(path, output_dir) → dict
│   ├── processors/
│   │   ├── anydoc_processor.py
│   │   └── rapidocr_processor.py
│   └── utils/
│       ├── file_detector.py
│       ├── page_detector.py
│       └── text_cleaner.py
│
├── agent2_vectorstore/               ← import as: agent2_vectorstore
│   ├── main.py                       ← agent2_pass1(), agent2_pass2(), hybrid_search()
│   ├── backfill_reclassify.py        ← re-label docs after a classifier change
│   ├── rebuild_index.py              ← rebuild ChromaDB from SQLite (no re-parsing)
│   ├── auto_linker.py
│   ├── extract_supplier.py
│   ├── link_supplier.py
│   ├── chunker/
│   │   └── text_chunker.py
│   ├── embeddings/
│   │   └── bge_m3_embeddings.py
│   ├── refinery/
│   │   ├── classifier.py             ← includes QAA rule (10 EN/DE patterns)
│   │   ├── extractor.py              ← M5: 7 field-group LLM calls
│   │   └── refiner.py
│   └── storage/
│       ├── sqlite_store.py           ← system of record
│       └── chromadb_store.py         ← vector index
│
├── agent3_evaluator/                 ← import as: agent3_evaluator
│   ├── decision_log.py               ← append-only audit record (FIX 1)
│   ├── report_store.py               ← immutable SQLite reports (H5)
│   ├── VA26.md
│   ├── evaluation/
│   │   ├── economic.py               ← VA26 §2.2.2 auto criteria 1-3
│   │   ├── economic_adapter.py       ← wraps economic.py; human scores 4-6 required
│   │   └── monitoring.py
│   ├── intake/
│   │   ├── risk_classifier.py        ← VA26 §2.1.5 decision tree (D1 fix)
│   │   ├── gate_engine.py            ← VA26 §2.1.1.1 measure checks (D2 fix)
│   │   ├── audit.py
│   │   ├── cli.py
│   │   ├── store.py
│   │   └── wizard.py
│   ├── orchestrator/
│   │   ├── graph.py                  ← LangGraph evaluation graph
│   │   ├── tools.py                  ← guarded tool dispatch (FIX 2+3)
│   │   ├── questions.py              ← VA26 question catalog
│   │   ├── context_builder.py        ← Agent 2 data → LLM narrative
│   │   └── session_store.py
│   └── rules/
│       └── va26.py                   ← VA26 as typed Enums
│
├── api/
│   └── main.py                       ← uvicorn api.main:app --port 8000
│
└── ui/
    ├── app.py                        ← streamlit run ui/app.py
    ├── api_client.py
    ├── components.py
    └── pages/
        ├── suppliers.py
        ├── profile.py
        ├── evaluate.py
        └── upload.py
```

## Import / Package Name Mapping

| Folder on disk | How it is imported | Who imports it |
|---|---|---|
| `agent1_offline/` | `import agent1_offline.main` (by file path in API + run_pipeline.py) | api, run_pipeline |
| `agent2_vectorstore/` | `_ROOT / "agent2_vectorstore"` added to sys.path; sub-packages imported as `from storage.sqlite_store import ...` | agent3, api |
| `agent3_evaluator/` | `from agent3_evaluator.orchestrator.graph import ...` | api, ui |
| `config.py` | `from config import get_db_path` | all agents |

**The project root (`pipeline/`) must be on `sys.path`.**
Every file that does cross-package imports adds it at startup:
```python
_ROOT = Path(__file__).resolve().parents[N]   # N depends on file depth
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
```
You do not need to set PYTHONPATH manually; the code handles it.

## Fixes Applied

| ID | Files | Description |
|---|---|---|
| D8 | config.py, sqlite_store.py, main.py | Unified DB path — was split across two .db files |
| H2 | config.py | LM Studio defaults to localhost:1234 |
| D1 | intake/risk_classifier.py | ready_to_sell=True always → Class 1 |
| D2 | intake/gate_engine.py | Zero gate items → blocked |
| D3 | agent2_vectorstore/main.py | Chunks written to SQLite; ChromaDB is rebuildable |
| D4 | sqlite_store.py, refinery/refiner.py | Chunk provenance on every profile fact |
| D5 | refinery/extractor.py, sqlite_store.py | llm_used/degraded/degraded_reason flags |
| M5 | refinery/extractor.py | 7 field-group calls replaced one large prompt |
| H5 | agent3_evaluator/report_store.py | Immutable append-only reports |
| FIX 1 | agent3_evaluator/decision_log.py | Final decision was never recorded — module was missing |
| FIX 2 | orchestrator/tools.py | gate_check passed wrong arguments to build_gate() |
| FIX 3 | evaluation/economic_adapter.py | economic_eval called functions that do not exist |
| QAA | refinery/classifier.py | 10 EN/DE patterns for Quality Assurance Agreements |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SUPPLIER_PIPELINE_DATA_DIR` | `<project_root>/data` | SQLite + ChromaDB location |
| `LM_STUDIO_URL` | `http://localhost:1234` | LM Studio base URL |
| `LM_STUDIO_MODEL` | `gpt-oss-20b` | Model name |
| `LM_STUDIO_TIMEOUT` | `120` | LLM call timeout (seconds) |
| `SUPPLIER_API_URL` | `http://localhost:8000` | FastAPI URL (for the Streamlit UI) |
