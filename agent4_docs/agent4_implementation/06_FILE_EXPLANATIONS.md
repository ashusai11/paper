# File Explanations: Agent 4 Implementation

## Overview
This document provides detailed explanations of every Python file in Agent 4.

---

## 1. Root Level Files

### __init__.py
**Purpose:** Package initialization and common utilities

**Key Features:**
- Custom exception hierarchy (Agent4Error, ValidationError, ApprovalError, etc.)
- Centralized logging configuration
- Utility functions (get_current_user, validate_supplier_id)
- Version information

---

### main.py
**Purpose:** CLI entry point and orchestrator

**Key Classes:**
- `RiskMatrixGenerator`: Main orchestrator
- `AuditLogger`: ISO 13485 compliance logging
- `CLI`: Command-line interface

**Key Methods:**
- `generate()`: Main workflow execution
- `_optimize_with_llm()`: Optional LLM optimization
- `_human_approval()`: ISO 13485 human approval gate
- `_log_completion()`: Completion logging

**Workflow:**
1. Validate input
2. Extract data
3. Score suppliers
4. Optional LLM optimization
5. Fill Excel template
6. Human approval
7. Validate results
8. Return output

---

## 2. Configuration Files

### config/config.py
**Purpose:** Centralized configuration management

**Key Features:**
- Dataclass for type safety
- Default values for all settings
- Environment variable support
- Pipeline config integration
- Path validation

**Settings:**
- Database paths (SQLite, ChromaDB)
- LM Studio settings (URL, model, timeout)
- Template settings (path, output directory)
- Agent 4 settings (rules path, LLM usage)
- Performance settings (batch size, max suppliers)

---

### config/loader.py
**Purpose:** Load and validate scoring rules from YAML

**Key Features:**
- YAML file loading
- Rule validation
- Caching with hot-reloading
- Default rules fallback
- Rule saving with validation

---

### config/rules.yaml
**Purpose:** Scoring rules configuration

**Structure:**
- Version and total weight
- Criteria with weights, descriptions, metrics
- Threshold-based scoring
- Data source references
- Result class definitions
- Anomaly detection rules

---

## 3. Execution Files

### execution/data_extractor.py
**Purpose:** Extract and transform data from SQLite and ChromaDB

**Key Methods:**
- `extract()`: Main data extraction
- `_get_document_context()`: Get documents from ChromaDB
- `_transform_data()`: Transform to scoring format
- `_create_abc_entry()`: Create ABC-Bew entry
- `_calculate_*_score()`: Calculate individual scores

**Data Flow:**
SQLite/ChromaDB -> Raw Data -> Transformed Data -> Scoring Input

---

### execution/scorer.py
**Purpose:** Apply scoring rules to supplier data

**Key Methods:**
- `score()`: Score all suppliers
- `_score_supplier()`: Score single supplier
- `_calculate_criterion_score()`: Calculate individual criterion
- `_apply_threshold()`: Apply threshold logic
- `_get_result_class()`: Determine A/B/C class

**Scoring Logic:**
- Load rules from rules.yaml
- For each criterion, calculate score based on thresholds
- Compute weighted average
- Determine result class
- Generate explanations

---

### execution/excel_filler.py
**Purpose:** Fill Excel template using openpyxl

**Key Methods:**
- `fill()`: Main filling method
- `_identify_formula_cells()`: Detect formula cells
- `_fill_abc_bew()`: Fill ABC-Bew sheet
- `_fill_zert_status()`: Fill Zert-Satus sheet
- `_fill_krit_lieferante()`: Fill krit Lieferante sheet
- `_fill_versionsverw()`: Fill Versionsverw sheet

**Key Features:**
- Formula preservation
- Formatting preservation
- Cell-by-cell updates
- Date formatting

---

### execution/validator.py
**Purpose:** Validate results against ISO 13485

**Key Methods:**
- `validate()`: Main validation
- `_validate_data_completeness()`: Check required fields
- `_validate_scoring()`: Validate scores
- `_validate_iso_13485()`: Check compliance
- `_validate_output()`: Validate Excel file

**Validation Checks:**
- Data completeness
- Scoring validity
- ISO 13485 compliance
- Output integrity
- Audit trail maintenance

---

## 4. LLM Files

### llm/client.py
**Purpose:** Interface with LM Studio

**Key Methods:**
- `generate()`: Generate text from prompt
- `analyze()`: Analyze data using LLM
- `_generate_*_prompt()`: Generate prompts for different analyses
- `_parse_response()`: Parse LLM responses

**Features:**
- Connection management
- Error handling with retries
- Multiple analysis types
- JSON formatting

---

### llm/rule_generator.py
**Purpose:** Generate and optimize scoring rules

**Key Methods:**
- `generate_rules()`: Generate rules from data
- `optimize_rules()`: Optimize existing rules
- `_generate_*_prompt()`: Generate prompts
- `_validate_rules()`: Validate generated rules

---

## 5. Orchestrator Files

### orchestrator/graph.py
**Purpose:** LangGraph workflow (optional)

**Key Features:**
- Node-based workflow
- Conditional branching
- State management
- Resumability

---

## 6. Integration with Existing Pipeline

### From Agent 2 (SQLite Store)
```python
from pipeline.agent2_vectorstore.storage.sqlite_store import SQLiteStore

sqlite_store = SQLiteStore(config.database_path)
suppliers = sqlite_store.get_supplier(supplier_id)
```

### From Agent 2 (ChromaDB Store)
```python
from pipeline.agent2_vectorstore.storage.chroma_store import ChromaStore

chroma_store = ChromaStore(config.chroma_path)
documents = chroma_store.query(query, n_results)
```

### From Pipeline Config
```python
from pipeline.config import config as pipeline_config

database_path = pipeline_config.DATABASE_PATH
chroma_path = pipeline_config.CHROMA_PATH
```

---

## Summary

**All files work together:**
1. main.py orchestrates everything
2. data_extractor.py gets data from existing pipeline
3. scorer.py applies rules
4. excel_filler.py creates output
5. validator.py ensures compliance
6. LLM files add intelligence (optional)

**Next:** Review flow diagrams and orchestration details.

---

*Document Version: 1.0.0 | Last Updated: November 2024*
