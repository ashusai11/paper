# Architecture Overview: Agent 4 Excel Template Autofill System

## 1. System Overview

### 1.1 Purpose
Agent 4 automatically fills the Lieferantenbewertung_2025.xlsx template with supplier data, evaluation results, and risk scores.

### 1.2 Key Features
- Template Autofill: Fill all 4 sheets using openpyxl
- Formula Preservation: All Excel formulas remain intact
- Configurable Rules: Scoring rules in YAML file
- LLM Intelligence: Optional rule optimization
- ISO 13485 Compliance: Human approval, audit trail

---

## 2. Architecture Diagram

### 2.1 High-Level Architecture
```
User Request -> API/UI -> Agent 4 Orchestrator -> Data Extractor -> Rule Scorer -> Excel Filler -> Human Approval -> Output
                                       -> LLM Client (Optional)
                                       -> Validator
```

### 2.2 Component Architecture
- **Orchestration Layer**: main.py, graph.py
- **Data Layer**: data_extractor.py (SQLite + ChromaDB)
- **Logic Layer**: scorer.py, validator.py
- **Presentation Layer**: excel_filler.py
- **LLM Layer**: client.py, rule_generator.py

---

## 3. Component Breakdown

### 3.1 Orchestration Layer
**main.py** - CLI Entry Point
- Coordinates all components
- Manages workflow execution
- Handles human approval gate

**graph.py** - LangGraph Workflow (Optional)
- Alternative orchestration
- Manages state between nodes
- Provides resumability

### 3.2 Data Layer
**data_extractor.py** - Data Extraction
- Queries SQLite for supplier data
- Queries ChromaDB for document context
- Transforms data into scoring-ready format

### 3.3 Logic Layer
**scorer.py** - Rule Execution Engine
- Loads rules from rules.yaml
- Calculates scores for each criterion
- Computes weighted averages
- Determines result classes (A, B, C)

**validator.py** - ISO 13485 Validation
- Validates data completeness
- Validates scoring logic
- Validates ISO 13485 compliance
- Generates validation reports

### 3.4 Presentation Layer
**excel_filler.py** - Excel Template Filling
- Loads Excel template
- Identifies formula cells to preserve
- Maps data to template cells
- Updates only data cells
- Preserves all formatting

### 3.5 LLM Layer
**client.py** - LM Studio Integration
- Manages connection to LM Studio
- Sends prompts and receives responses
- Handles errors and retries

**rule_generator.py** - Rule Generation
- Generates new rules based on data
- Optimizes existing rules
- Validates generated rules

---

## 4. Integration with Existing Pipeline

### 4.1 Existing Components
- **Agent 1**: PDF/OCR processing
- **Agent 2**: SQLite + ChromaDB storage
- **Agent 3**: Risk classification
- **API**: FastAPI backend
- **UI**: Streamlit frontend

### 4.2 Agent 4 Integration
**Data Sources:**
- From Agent 2 (SQLite): Supplier data, purchase history, certificates
- From Agent 2 (ChromaDB): Document context (audit reports, nonconformances)

**Configuration:**
- Inherits from pipeline/config.py
- Adds Agent 4 specific settings

**API Integration:**
- New endpoints: /risk-matrix/generate, /risk-matrix/rules
- Returns filled Excel file for download

**UI Integration:**
- New Streamlit page: risk_matrix.py
- Allows user to select supplier and generate matrix

---

## 5. Data Flow Architecture

### 5.1 End-to-End Flow
1. User Request (supplier_id)
2. Data Extraction (SQLite + ChromaDB)
3. Rule Scoring (rules.yaml)
4. LLM Optimization (Optional)
5. Excel Filling (openpyxl)
6. Human Approval (ISO 13485)
7. Validation (ISO 13485)
8. Output (Filled Excel)

### 5.2 Stage Details
**Stage 1: Request Initiation**
- Input: User request with optional supplier_id
- Processing: Validate parameters, create context
- Output: Request context

**Stage 2: Data Extraction**
- Input: Request context
- Processing: Query SQLite + ChromaDB, transform data
- Output: Structured data for scoring

**Stage 3: Rule Scoring**
- Input: Structured data
- Processing: Apply scoring rules, calculate weighted averages
- Output: Scoring results with explanations

**Stage 4: LLM Optimization (Optional)**
- Input: Scoring results
- Processing: LLM suggests rule improvements
- Output: Optimized scoring results

**Stage 5: Excel Filling**
- Input: Scoring results
- Processing: Fill template, preserve formulas/formatting
- Output: Filled Excel file

**Stage 6: Human Approval**
- Input: Filled Excel file
- Processing: Present to human for approval
- Output: Approval status

**Stage 7: Validation**
- Input: Scoring results + filled Excel
- Processing: Validate compliance, data integrity
- Output: Validation report

**Stage 8: Output**
- Input: Validated filled Excel
- Processing: Return file path to user
- Output: File for download

---

## 6. Compliance Architecture

### 6.1 ISO 13485 Compliance
**Relevant Clauses:**
- 4.1.6: Computerized System Validation (CSV)
- 7.4.1: Human approval for final decisions
- 4.2.4: Control of records (audit trail)
- 7.4.3: Traceability

**Implementation:**
- Human approval gate in main.py
- Audit trail logging in validator.py
- Traceability via supplier_id and document references
- CSV documentation and testing

### 6.2 Deterministic Execution
- No randomness in scoring logic
- LLM only for optimization (not critical path)
- Versioned rules and code
- Reproducible builds

---

## 7. Technology Stack

| Technology | Purpose | Status |
|------------|---------|--------|
| Python 3.10+ | Primary language | Existing |
| openpyxl | Excel manipulation | Existing |
| SQLite | Structured data | Existing |
| ChromaDB | Vector storage | Existing |
| LM Studio | Local LLM | Existing |
| LangGraph | Orchestration | Optional |
| FastAPI | Backend | Existing |
| Streamlit | Frontend | Existing |
| PyYAML | YAML parsing | Existing |

---

*Document Version: 1.0.0 | Last Updated: November 2024*
