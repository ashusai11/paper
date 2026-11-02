# Document 01: System Architecture

**Supplier Qualification Pipeline - Regulatory Assessment**
**BEC Robotics - Medical Technology Company**
**Assessment Date: 2024**
**Document Version: 1.0**

---

## System Overview

The Supplier Qualification Pipeline is a **3-Agent RAG-based system** for automating supplier qualification at BEC Robotics.

### Architecture
```
User → Streamlit UI → FastAPI → Agent 1 (Parser) → Agent 2 (Vector Store) → Agent 3 (Evaluator) → SQLite/ChromaDB
```

### Key Features
- **3-Agent System**: Offline Parser, Vector Store, Evaluator
- **Dual Storage**: SQLite (system of record) + ChromaDB (vector index)
- **LLM Integration**: LM Studio (local, default) + configurable external API
- **Orchestration**: LangGraph workflow engine
- **Human Oversight**: Required for all final decisions (ISO 13485 compliant)

---

## Architecture Components

### Agent 1: Offline Parser
**Location**: `agent1_offline_parser/`

**Functionality**:
- Document ingestion (PDF, Excel, etc.)
- Text extraction via pypdfium2 (PDF) and RapidOCR (scanned docs)
- LLM-based structured data extraction
- Text cleaning and normalization

**Key Files**:
- `main.py` - Entry point
- `ingestion/document_ingestor.py` - Document processing
- `extraction/llm_extractor.py` - LLM extraction
- `extraction/pdf_parser.py` - PDF parsing
- `extraction/ocr_processor.py` - OCR processing

---

### Agent 2: Vector Store  
**Location**: `agent2_vectorstore/`

**Functionality**:
- Text chunking (configurable size)
- Embedding generation using BGE-M3
- Vector storage in ChromaDB
- Metadata storage in SQLite
- Document linking to suppliers

**Key Files**:
- `storage/sqlite_store.py` - SQLite operations
- `storage/chromadb_store.py` - ChromaDB operations  
- `embeddings/bge_m3_embeddings.py` - Embedding generation
- `chunker/text_chunker.py` - Text chunking

---

### Agent 3: Evaluator
**Location**: `agent3_evaluator/`

**Functionality**:
- VA26-compliant risk classification (A-D)
- Economic evaluation
- Monitoring interval determination
- Human approval workflow
- Report generation with full traceability

**Key Files**:
- `rules/va26.py` - VA26 rules
- `intake/risk_classifier.py` - Risk classification
- `evaluation/economic.py` - Economic evaluation
- `orchestrator/graph.py` - LangGraph workflow
- `report_store.py` - Report storage

---

## Data Flow

```
Document Upload → Agent 1 (Parsing/Extraction) → Agent 2 (Chunking/Embedding/Storage) → 
Agent 3 (Retrieval/Classification/Evaluation) → Human Review → Report Generation → SQLite Storage
```

### 9-Stage Data Lifecycle
1. **Upload**: User uploads documents via Streamlit
2. **Parsing**: Agent 1 extracts text from documents
3. **Storage**: Structured data stored in SQLite
4. **Chunking/Embedding**: Agent 2 processes text for RAG
5. **LLM Extraction**: Agent 1 uses LLM for structured extraction
6. **Evaluation**: Agent 3 classifies risk and evaluates
7. **Human Review**: Required approval for all decisions
8. **Report Generation**: Evaluation reports created
9. **Archival**: Reports stored in SQLite with full traceability

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend | FastAPI | REST API |
| Frontend | Streamlit | Web UI |
| Orchestration | LangGraph | Workflow engine |
| Database | SQLite | System of record |
| Vector DB | ChromaDB | Vector index |
| LLM | LM Studio | Local LLM inference |
| PDF Parsing | pypdfium2 | PDF extraction |
| OCR | RapidOCR | Text recognition |
| Embeddings | BGE-M3 | Vector generation |

---

## Security Characteristics

### Current State
- ❌ No authentication/authorization
- ❌ No encryption (data stored in plaintext)
- ❌ No access controls
- ⚠️ Partial logging
- ❓ Network security depends on BEC infrastructure

### Recommendations
1. Implement authentication for all services
2. Enable HTTPS for all communications
3. Implement encryption at rest for databases
4. Implement role-based access control
5. Implement comprehensive audit logging

---

**Document Control**
**Author**: Regulatory Affairs Consultant
**Version**: 1.0
**Date**: 2024-11-02
**Distribution**: QM, Regulatory Affairs, IT, Legal

*Document 01 of 15 - See Document 00 for navigation*
