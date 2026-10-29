# **Agent 4: Supplier Risk Matrix Autofill System - Architecture Overview**

---

## **Document Information**
- **Version**: 1.0
- **Author**: Vibe Code (Mistral AI)
- **Date**: 2025
- **Purpose**: Comprehensive architecture documentation for the Supplier Risk Matrix Autofill System
- **Target Audience**: Developers, Architects, Compliance Officers (ISO 13485)

---

## **Table of Contents**
1. [Executive Summary](#executive-summary)
2. [System Overview](#system-overview)
3. [Evolution of Approaches](#evolution-of-approaches)
4. [Current Architecture Decision](#current-architecture-decision)
5. [Integration with Existing Pipeline](#integration-with-existing-pipeline)
6. [Documentation Structure](#documentation-structure)

---

## **Executive Summary**

This document provides a comprehensive overview of the **Supplier Risk Matrix Autofill System (Agent 4)**, designed for a medical device company following **ISO 13485** standards. The system automatically fills an Excel supplier risk matrix template by:

1. Reading supplier data from **SQLite** and **ChromaDB** databases
2. Applying **custom scoring rules** (configurable via YAML)
3. Using **LLM intelligence** to understand deep data context (delivery delays, nonconformance patterns)
4. Generating **filled Excel templates** with all 4 sheets preserved
5. Operating **100% offline** (no external services, no API calls)
6. Maintaining **ISO 13485 compliance** (human approval, audit trails, deterministic execution)

---

## **System Overview**

### **Core Objectives**
- **Automation**: Automatically fill the `Lieferantenbewertung_2025.xlsx` template
- **Intelligence**: Use LLM to understand data patterns and generate scoring logic
- **Compliance**: Ensure ISO 13485 compliance with human approval and audit trails
- **Offline Operation**: No external dependencies (MCP servers, APIs, cloud services)
- **Configurability**: All scoring rules in a separate YAML file
- **Formula Preservation**: Maintain all Excel formulas and formatting

### **Template Structure**
The Excel template contains **4 sheets**:
1. **ABC-Bew**: Main scoring sheet (140 rows, 9 columns) with weighted scores
2. **Zert-Satus**: Certificate status (94 rows, 5 columns) with expiry dates
3. **krit Lieferante**: Critical suppliers list (42 rows, 9 columns)
4. **Versionsverw**: Version history (13 rows, 5 columns)

### **Scoring System**
- **ABC Scale**: 1 (Best) to 3 (Poor)
- **Weighted Average Formula**: `=(B*2 + C*2 + D + E + F + G) / 8`
- **Result Classes**:
  - A: 0-1.5
  - B: 1.51-2.5
  - C: 2.51-3.0

---

## **Evolution of Approaches**

### **1. Initial Approach: No LLM (Pure Python)**
**Description**: Basic approach using only Python with `openpyxl` for Excel manipulation.

**Pros**:
- Simple and straightforward
- No external dependencies
- Easy to debug and maintain
- Deterministic execution

**Cons**:
- Limited intelligence in scoring
- Cannot understand deep data context (e.g., patterns in delivery delays)
- Static rules only
- No adaptive learning

**Implementation**: Direct cell manipulation using `openpyxl`

---

### **2. Enhanced Approach: Deep Agents**
**Description**: Using Deep Agents framework for agent orchestration with LLM capabilities.

**Pros**:
- More intelligent decision-making
- Can understand data context
- Agent-based architecture
- Better for complex workflows

**Cons**:
- Additional dependency (Deep Agents)
- More complex to set up
- May be overkill for this specific use case

**Implementation**: Agent-based orchestration with LLM for scoring logic

---

### **3. Current Approach: LangGraph**
**Description**: Using LangGraph for workflow orchestration with LLM integration.

**Pros**:
- **Best of both worlds**: LangGraph for orchestration + LLM for intelligence
- **Modular**: Separate layers for orchestration, intelligence, and execution
- **Compliant**: Human approval gate, audit trail, deterministic execution
- **Scalable**: Can handle complex workflows and multiple agents
- **Offline**: Works with local LLM (LM Studio)

**Cons**:
- More complex architecture
- Requires understanding of LangGraph concepts

**Implementation**: 
- **Layer 1 (Orchestrator)**: LangGraph workflow (deterministic)
- **Layer 2 (Intelligence)**: LLM understands data, generates rules, explains anomalies
- **Layer 3 (Execution)**: Python runs LLM-generated logic deterministically

---

## **Current Architecture Decision**

### **Final Architecture: Hybrid Approach**
We have decided on a **hybrid architecture** that combines:

1. **LangGraph** for workflow orchestration
2. **LLM (LM Studio)** for intelligence (rule generation, anomaly detection)
3. **Python** for deterministic execution
4. **`openpyxl`** for Excel manipulation (pre-search plan) or **`xlsxtpl`** (post-search plan)

### **Architecture Layers**

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                            │
│  (Streamlit API, CLI, or Direct Function Calls)                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATION LAYER                          │
│  (LangGraph Workflow - Deterministic)                            │
│  - Agent 4 Orchestrator                                           │
│  - Workflow: Extract → Score → Validate → Fill → Export           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      INTELLIGENCE LAYER                           │
│  (LLM - LM Studio Local Model)                                   │
│  - Rule Generator: Creates/optimizes scoring rules               │
│  - Anomaly Detector: Identifies patterns, expiring certs         │
│  - Data Analyzer: Understands deep context (delays, trends)       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      EXECUTION LAYER                              │
│  (Python - Deterministic)                                         │
│  - Data Extractor: Reads SQLite + ChromaDB                        │
│  - Rule Scorer: Applies rules from rules.yaml                     │
│  - Excel Filler: Fills template (openpyxl or xlsxtpl)             │
│  - Validator: ISO 13485 compliance checks                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                   │
│  - SQLite: System of record (suppliers, audit findings, etc.)    │
│  - ChromaDB: Vector index for document search                    │
│  - rules.yaml: Configurable scoring rules                        │
│  - Templates: Excel template files                               │
└─────────────────────────────────────────────────────────────────┘
```

### **Key Design Principles**

1. **Separation of Concerns**: Each layer has a distinct responsibility
2. **Configurability**: All rules in `rules.yaml` (no code changes needed)
3. **Compliance**: Human approval for final decisions (ISO 13485 §7.4.1)
4. **Auditability**: Full traceability of all data and decisions
5. **Offline Operation**: No external services or internet dependency
6. **Deterministic Execution**: Same input → same output
7. **Preservation**: Excel formulas and formatting must remain intact

---

## **Integration with Existing Pipeline**

### **Existing Pipeline Overview**
The current pipeline consists of:

1. **Agent 1: Offline Parser**
   - Parses documents (PDFs, Word, Excel) offline
   - Extracts structured data
   - Stores in SQLite

2. **Agent 2: Vector Store**
   - Manages ChromaDB vector index
   - Handles tabular ingestion (Excel/CSV → SQLite)
   - Target tables: `purchase_history`, `risk_matrix`, `certificate_register`

3. **Agent 3: VA26 Evaluator**
   - Implements VA26 rules (risk classes, economic evaluation)
   - Full ISO 13485/VA26 compliance
   - Monitoring intervals and risk classification

4. **API & UI**
   - FastAPI backend
   - Streamlit frontend
   - Central configuration via `config.py`

### **Agent 4 Integration Points**

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXISTING PIPELINE                               │
│  ┌─────────────┐    ┌─────────────┐    ┌───────────────────┐  │
│  │ Agent 1:     │    │ Agent 2:     │    │ Agent 3: VA26      │  │
│  │ Offline      │    │ Vector Store │    │ Evaluator          │  │
│  │ Parser       │    │              │    │                    │  │
│  └──────┬───────┘    └──────┬───────┘    └──────────┬────────┘  │
│         │                  │                     │              │
│         ▼                  ▼                     ▼              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    SHARED INFRASTRUCTURE                    │   │
│  │  - SQLite Database (System of Record)                       │   │
│  │  - ChromaDB (Vector Index)                                  │   │
│  │  - config.py (Central Configuration)                       │   │
│  │  - LM Studio (Local LLM)                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         │                                          │
│                         ▼                                          │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    AGENT 4: RISK MATRIX                       │  │
│  │  - Data Extractor (uses SQLite + ChromaDB from Agents 1-2)   │  │
│  │  - Rule Scorer (uses VA26 rules from Agent 3 as reference)   │  │
│  │  - Excel Filler (generates filled template)                  │  │
│  │  - Validator (ISO 13485 compliance)                          │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### **Data Flow Integration**

1. **Input Data Sources**:
   - **SQLite**: Supplier data, audit findings, purchase history, certificate register
   - **ChromaDB**: Document embeddings for semantic search

2. **Rule Integration**:
   - Agent 4 uses its own `rules.yaml` for scoring
   - Can reference VA26 rules from Agent 3 for consistency

3. **Output Integration**:
   - Filled Excel templates stored in shared location
   - Results can be imported back into SQLite for tracking
   - API endpoints for programmatic access

4. **UI Integration**:
   - New Streamlit page for risk matrix generation
   - Integrated with existing UI workflows

---

## **Documentation Structure**

This documentation is organized into multiple documents for clarity:

### **📁 /docs/**
```
docs/
├── 01_Architecture_Overview.md          # This document
├── 02_PreSearch_Plan_OpenPyXL.md         # Detailed pre-search plan (openpyxl only)
├── 03_Approach_Comparison.md             # Comparison of all approaches
├── 04_Integration_With_Existing_Pipeline.md  # Deep dive on integration
├── 05_Data_Flow_Diagrams.md             # Flow diagrams and interactions
├── 06_Implementation_Details.md          # Detailed implementation of each file
└── comparisons/
    ├── no_llm_approach.md
    ├── deep_agents_approach.md
    └── langgraph_approach.md
```

### **Document Descriptions**

| Document | Purpose | Focus |
|----------|---------|-------|
| `01_Architecture_Overview.md` | High-level system overview | Architecture, layers, principles |
| `02_PreSearch_Plan_OpenPyXL.md` | **Detailed pre-search implementation** | Code structure, data flow, file interactions |
| `03_Approach_Comparison.md` | Compare different approaches | No LLM vs Deep Agents vs LangGraph |
| `04_Integration_With_Existing_Pipeline.md` | Integration details | How Agent 4 connects to Agents 1-3 |
| `05_Data_Flow_Diagrams.md` | Visual diagrams | Flowcharts, sequence diagrams |
| `06_Implementation_Details.md` | Implementation specifics | Each Python file, functions, classes |

---

## **Next Steps**

1. **Read `02_PreSearch_Plan_OpenPyXL.md`** for the detailed pre-search implementation plan
2. **Read `03_Approach_Comparison.md`** to understand the evolution of our approach
3. **Read `04_Integration_With_Existing_Pipeline.md`** for integration details
4. **Read `05_Data_Flow_Diagrams.md`** for visual representations
5. **Read `06_Implementation_Details.md`** for the actual code implementation

---

## **Glossary**

| Term | Definition |
|------|------------|
| ISO 13485 | International standard for medical device quality management systems |
| VA26 | German medical device regulation (similar to ISO 13485) |
| SQLite | Lightweight relational database (system of record) |
| ChromaDB | Vector database for document indexing and search |
| LM Studio | Local LLM runtime for offline AI capabilities |
| LangGraph | Workflow orchestration framework for LLM agents |
| Deep Agents | Alternative agent orchestration framework |
| openpyxl | Python library for Excel file manipulation |
| xlsxtpl | Jinja2 + openpyxl for Excel template filling |

---

*Document Version: 1.0 | Last Updated: 2025 | Author: Vibe Code (Mistral AI)*
