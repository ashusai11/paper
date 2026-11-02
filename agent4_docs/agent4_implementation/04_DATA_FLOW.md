# Data Flow: Agent 4 Excel Template Autofill System

## 1. Overview

This document explains the **complete data journey** through Agent 4, from user request to final output.

---

## 2. End-to-End Flow

```
User Request -> Orchestrator -> Data Extractor -> Rule Scorer -> Excel Filler -> Human Approval -> Validator -> Output
                                      -> LLM Client (Optional)
```

---

## 3. Stage-by-Stage Breakdown

### Stage 1: Request Initiation
- **Input:** User request with optional supplier_id
- **Processing:** Validate parameters, create request context, log
- **Output:** Request context (request_id, timestamp, user)
- **Component:** main.py
- **Risks:** Invalid input, unauthorized access

### Stage 2: Data Extraction
- **Input:** Request context
- **Processing:** Query SQLite + ChromaDB, transform data
- **Output:** Structured data for scoring
- **Component:** data_extractor.py
- **Risks:** Data inconsistency, missing data

### Stage 3: Rule Scoring
- **Input:** Structured data
- **Processing:** Load rules, apply scoring, compute weighted averages
- **Output:** Scoring results with explanations
- **Component:** scorer.py
- **Risks:** Incorrect scoring logic

### Stage 4: LLM Optimization (Optional)
- **Input:** Scoring results
- **Processing:** Analyze patterns, suggest optimizations
- **Output:** Optimized scoring results
- **Component:** llm/rule_generator.py
- **Risks:** Invalid suggestions, non-determinism

### Stage 5: Excel Filling
- **Input:** Scoring results
- **Processing:** Load template, identify formulas, map data, update cells
- **Output:** Filled Excel file path
- **Component:** excel_filler.py
- **Risks:** Formula overwrites, formatting loss

### Stage 6: Human Approval
- **Input:** Filled Excel file, scoring results
- **Processing:** Present results, request approval, log decision
- **Output:** Approval status
- **Component:** main.py, validator.py
- **Risks:** Bypassing approval (compliance violation)

### Stage 7: Validation
- **Input:** Scoring results, filled Excel file
- **Processing:** Validate completeness, scoring, compliance, output
- **Output:** Validation report
- **Component:** validator.py
- **Risks:** Validation errors

### Stage 8: Output
- **Input:** Validated filled Excel file
- **Processing:** Return file path, log completion
- **Output:** File path for download
- **Component:** main.py
- **Risks:** File access issues

---

## 4. Data Classification

| Data Type | Sensitivity | Location | Retention |
|-----------|-------------|----------|-----------|
| Original Documents | High | File system | Per policy |
| Structured Data | High | SQLite | Per policy |
| Embeddings | Medium | ChromaDB | Per policy |
| Scoring Results | Medium | In-memory | Session |
| Filled Excel | Medium | File system | Per policy |
| Audit Logs | High | File system | Per policy |
| Rules | Medium | File system | Permanent |

---

## 5. Key Data Transformations

### From SQLite/ChromaDB to Scoring Format
```python
# Input from databases
suppliers = [
    {
        'id': 'SUP-001',
        'legal_name': 'Test Supplier',
        'quality_score': 95.5,
        'delivery_score': 85.0,
        # ... other fields
    }
]

# Output for scoring
{
    'abc_bew': [
        {
            'supplier_id': 'SUP-001',
            'legal_name': 'Test Supplier',
            'produktqualitaet': 95.5,
            'reklamation': 85.0,
            # ... mapped fields
        }
    ]
}
```

### From Scoring to Excel
```python
# Input scoring results
{
    'supplier_id': 'SUP-001',
    'scores': {
        'produktqualitaet': 1,
        'reklamation': 2,
        # ...
    },
    'result_class': 'A'
}

# Output Excel cells
{
    'A2': 'Test Supplier',
    'B2': 1,  # Produktqualitaet
    'C2': 2,  # Reklamation
    # ...
    'I2': 'A'  # Ergebnis
}
```

---

## 6. Summary

- **8 stages** of data processing
- **Multiple data types** involved
- **Compliance built in** at multiple stages
- **Risks identified and mitigated**
- **Audit trail** maintained throughout

---

*Document Version: 1.0.0 | Last Updated: November 2024*
