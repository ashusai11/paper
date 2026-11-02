# Flow Diagrams: Agent 4 Implementation

## 1. Overview

This document provides **visual flow diagrams** for Agent 4 using Mermaid syntax. These diagrams illustrate:
- System architecture
- Data flow
- Component interactions
- Workflow sequences
- State transitions

---

## 2. System Architecture Diagram

```mermaid
graph TD
    subgraph Agent4[Agent 4: Risk Matrix Generator]
        Orchestrator[Orchestrator\nmain.py]
        DataExtractor[Data Extractor\ndata_extractor.py]
        RuleScorer[Rule Scorer\nscorer.py]
        ExcelFiller[Excel Filler\nexcel_filler.py]
        Validator[Validator\nvalidator.py]
        LLMClient[LLM Client\nllm/client.py]
    end
    
    subgraph Existing[Existing Pipeline]
        SQLite[(SQLite Store\nAgent 2)]
        ChromaDB[(ChromaDB Store\nAgent 2)]
        LMStudio[(LM Studio)]
        Template[(Excel Template)]
    end
    
    subgraph Output[Output]
        FilledExcel[(Filled Excel)]
        AuditLogs[(Audit Logs)]
        User[User]
    end
    
    User -->|Request| Orchestrator
    Orchestrator -->|Extract| DataExtractor
    Orchestrator -->|Score| RuleScorer
    Orchestrator -->|Fill| ExcelFiller
    Orchestrator -->|Validate| Validator
    Orchestrator -->|Optimize| LLMClient
    
    DataExtractor -->|Query| SQLite
    DataExtractor -->|Query| ChromaDB
    
    RuleScorer -->|Load| RulesYAML[rules.yaml]
    
    ExcelFiller -->|Load| Template
    ExcelFiller -->|Save| FilledExcel
    
    Validator -->|Write| AuditLogs
    
    LLMClient -->|Connect| LMStudio
    
    FilledExcel -->|Download| User
    
    style Agent4 fill:#9f9,stroke:#333
    style Existing fill:#ff9,stroke:#333
    style Output fill:#9ff,stroke:#333
```

---

## 3. Data Flow Diagram

```mermaid
flowchart TD
    subgraph Input[Input Layer]
        A[User Request] -->|supplier_id| B[API/UI]
        C[Excel Template] --> D[Template Loader]
    end
    
    subgraph Processing[Processing Layer]
        B --> E[Orchestrator]
        D --> E
        E --> F[Data Extractor]
        F --> G[SQLite DB]
        F --> H[ChromaDB]
        G -->|Supplier Data| F
        H -->|Documents| F
        F -->|Structured Data| E
        E --> I[Rule Scorer]
        I --> J[Rules Loader]
        J -->|rules.yaml| I
        I -->|Scoring Results| E
        E --> K[LLM Client]
        K --> L[LM Studio]
        L -->|Intelligence| K
        K -->|Optimized Rules| E
        E --> M[Excel Filler]
        M -->|Filled Data| N[Human Approval]
        N -->|Approved| M
        M --> O[Validator]
        O -->|Validated| P[Output]
    end
    
    subgraph Output[Output Layer]
        P --> Q[Filled Excel]
        P --> R[Audit Logs]
        Q --> S[User]
    end
    
    style Input fill:#f9f,stroke:#333
    style Processing fill:#bbf,stroke:#333
    style Output fill:#9ff,stroke:#333
```

---

## 4. Workflow Sequence Diagram

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Orchestrator
    participant DataExtractor
    participant SQLite
    participant ChromaDB
    participant RuleScorer
    participant LLMClient
    participant ExcelFiller
    participant Validator
    participant Human
    
    User->>API: Generate Request (supplier_id)
    API->>Orchestrator: create()
    
    Orchestrator->>DataExtractor: extract(supplier_id)
    DataExtractor->>SQLite: get_suppliers()
    SQLite-->>DataExtractor: suppliers
    DataExtractor->>ChromaDB: query()
    ChromaDB-->>DataExtractor: documents
    DataExtractor-->>Orchestrator: structured_data
    
    Orchestrator->>RuleScorer: score(data)
    RuleScorer->>RuleScorer: load_rules()
    RuleScorer-->>Orchestrator: scoring_results
    
    alt LLM Optimization Enabled
        Orchestrator->>LLMClient: analyze(results)
        LLMClient->>LMStudio: generate()
        LMStudio-->>LLMClient: suggestions
        LLMClient-->>Orchestrator: optimized_results
    end
    
    Orchestrator->>ExcelFiller: fill(results)
    ExcelFiller->>ExcelFiller: load_template()
    ExcelFiller->>ExcelFiller: identify_formulas()
    ExcelFiller->>ExcelFiller: fill_sheets()
    ExcelFiller-->>Orchestrator: output_path
    
    Orchestrator->>Human: request_approval()
    Human-->>Orchestrator: approval_granted
    
    Orchestrator->>Validator: validate(results, output_path)
    Validator->>Validator: check_completeness()
    Validator->>Validator: check_scoring()
    Validator->>Validator: check_compliance()
    Validator->>Validator: check_output()
    Validator-->>Orchestrator: validation_report
    
    Orchestrator-->>API: output_path
    API-->>User: Filled Excel File
```

---

## 5. Component Interaction Diagram

```mermaid
graph TD
    Orchestrator[Orchestrator\nmain.py] --> DataExtractor
    Orchestrator --> RuleScorer
    Orchestrator --> ExcelFiller
    Orchestrator --> Validator
    Orchestrator --> LLMClient
    
    DataExtractor --> SQLiteStore
    DataExtractor --> ChromaStore
    
    RuleScorer --> RulesLoader
    RulesLoader --> RulesYAML
    
    ExcelFiller --> Template
    ExcelFiller --> Output
    
    Validator --> AuditLogs
    
    LLMClient --> LMStudio
    LLMClient --> RuleGenerator
    
    style Orchestrator fill:#9f9,stroke:#333,stroke-width:2px
    style DataExtractor fill:#9f9,stroke:#333
    style RuleScorer fill:#9f9,stroke:#333
    style ExcelFiller fill:#9f9,stroke:#333
    style Validator fill:#9f9,stroke:#333
    style LLMClient fill:#9f9,stroke:#333
    style SQLiteStore fill:#ff9,stroke:#333
    style ChromaStore fill:#ff9,stroke:#333
    style RulesYAML fill:#ff9,stroke:#333
    style Template fill:#ff9,stroke:#333
    style Output fill:#9ff,stroke:#333
    style AuditLogs fill:#ff9,stroke:#333
    style LMStudio fill:#ff9,stroke:#333
    style RuleGenerator fill:#9f9,stroke:#333
```

---

## 6. Excel Filling Process Diagram

```mermaid
flowchart TD
    A[Start] --> B[Load Template]
    B --> C[Identify Formula Cells]
    C --> D[Get Scoring Results]
    D --> E[Fill ABC-Bew Sheet]
    E --> F[Fill Zert-Satus Sheet]
    F --> G[Fill krit Lieferante Sheet]
    G --> H[Fill Versionsverw Sheet]
    H --> I[Save Filled Template]
    I --> J[End]
    
    subgraph SheetFilling[Sheet Filling Details]
        E --> E1[For each supplier]
        E1 --> E2[Map data to cells]
        E2 --> E3[Check if formula cell]
        E3 -->|No| E4[Update cell value]
        E3 -->|Yes| E5[Skip cell]
        E4 --> E2
        E5 --> E2
    end
    
    style SheetFilling fill:#f9f,stroke:#333,stroke-dasharray: 5 5
```

---

## 7. Data Transformation Diagram

```mermaid
flowchart LR
    subgraph Raw[Raw Data]
        S1[SQLite:\nSuppliers\nPurchase History\nCertificates]
        S2[ChromaDB:\nAudit Reports\nNonconformances\nQuestionnaires]
    end
    
    subgraph Transform[Transformation]
        T1[DataExtractor:\nQuery\nFilter\nJoin]
        T2[Calculate Metrics:\nQuality Score\nDelivery Score\nService Score]
        T3[Map to Scoring Format]
    end
    
    subgraph Scoring[Scoring Data]
        S3[Structured Data:\nABC-Bew\nZert-Satus\nkrit Lieferante]
    end
    
    Raw -->|Extract| Transform
    Transform -->|Transform| Scoring
    
    style Raw fill:#ff9,stroke:#333
    style Transform fill:#bbf,stroke:#333
    style Scoring fill:#9f9,stroke:#333
```

---

## 8. Scoring Process Diagram

```mermaid
flowchart TD
    A[Start] --> B[Load Rules]
    B --> C[For each supplier]
    C --> D[For each criterion]
    D --> E[Get metric value]
    E --> F[Apply calculation method]
    F --> G[Determine score 1-3]
    G --> D
    D -->|All criteria scored| H[Calculate weighted average]
    H --> I[Determine result class A/B/C]
    I --> J[Generate explanations]
    J --> C
    C -->|All suppliers scored| K[End]
    
    subgraph Calculation[Calculation Methods]
        F --> F1[Threshold-based]
        F --> F2[Weighted Average]
        F --> F3[Custom]
    end
    
    style Calculation fill:#f9f,stroke:#333,stroke-dasharray: 5 5
```

---

## 9. Validation Process Diagram

```mermaid
flowchart TD
    A[Start] --> B[Check Data Completeness]
    B --> C[Check Scoring Validity]
    C --> D[Check ISO 13485 Compliance]
    D --> E[Check Output Integrity]
    E --> F[Generate Report]
    F --> G[Log to Audit Trail]
    G --> H[All Passed?]
    H -->|Yes| I[Success]
    H -->|No| J[Raise ValidationError]
    
    subgraph Checks[Validation Checks]
        B --> B1[Required fields present]
        C --> C1[Scores valid 1-3]
        C --> C2[Weighted score 1-3]
        C --> C3[Result class matches]
        D --> D1[Human approval gate]
        D --> D2[Deterministic execution]
        D --> D3[Traceability]
        E --> E1[File exists]
        E --> E2[All sheets present]
        E --> E3[Formulas preserved]
    end
    
    style Checks fill:#f9f,stroke:#333,stroke-dasharray: 5 5
```

---

## 10. LLM Integration Diagram

```mermaid
flowchart TD
    A[Start] --> B[User Request]
    B --> C[Orchestrator decides:\nUse LLM?]
    C -->|No| D[Skip LLM]
    C -->|Yes| E[LLMClient.generate()]
    E --> F[Send prompt to LM Studio]
    F --> G[Receive response]
    G --> H[Parse response]
    H --> I[Validate suggestions]
    I --> J[Apply approved changes]
    J --> K[Return optimized results]
    
    subgraph LLM[LLM Operations]
        E --> E1[Rule Generation]
        E --> E2[Rule Optimization]
        E --> E3[Anomaly Detection]
        E --> E4[Explanation Generation]
    end
    
    style LLM fill:#f9f,stroke:#333,stroke-dasharray: 5 5
```

---

## 11. ISO 13485 Compliance Diagram

```mermaid
flowchart TD
    subgraph Compliance[ISO 13485 Compliance]
        CSV[4.1.6 CSV:\nRequirements\nRisk Assessment\nTesting\nDocumentation]
        
        Human[7.4.1 Human Approval:\nFinal decisions\nApproval gate\nAudit trail]
        
        Records[4.2.4 Records:\nAll actions logged\nTimestamp\nUser\nChanges]
        
        Trace[7.4.3 Traceability:\nSupplier ID\nDocument IDs\nSource references]
    end
    
    subgraph Implementation[Agent 4 Implementation]
        I1[Requirements in\nrules.yaml]
        I2[Human approval in\nmain.py]
        I3[Audit logging in\nvalidator.py]
        I4[Traceability in\ndata_extractor.py]
    end
    
    Compliance -->|Implemented by| Implementation
    
    style Compliance fill:#9f9,stroke:#333
    style Implementation fill:#ff9,stroke:#333
```

---

## 12. Error Handling Diagram

```mermaid
flowchart TD
    A[Start] --> B[Try operation]
    B --> C{Success?}
    C -->|Yes| D[Continue]
    C -->|No| E[Catch exception]
    E --> F[Log error]
    F --> G[Determine error type]
    G --> H1[DataExtractionError]
    G --> H2[ValidationError]
    G --> H3[ApprovalError]
    G --> H4[LLMError]
    G --> H5[Agent4Error]
    H1 --> I[Retry or fail]
    H2 --> I
    H3 --> I
    H4 --> I
    H5 --> I
    I --> J[Return error to user]
```

---

## 13. Integration with Existing Pipeline Diagram

```mermaid
graph LR
    subgraph Pipeline[Existing Pipeline]
        A1[Agent 1:\nPDF/OCR Processing]
        A2[Agent 2:\nSQLite + ChromaDB]
        A3[Agent 3:\nRisk Classification]
        A4[API:\nFastAPI]
        A5[UI:\nStreamlit]
    end
    
    subgraph Agent4[Agent 4: New]
        B1[DataExtractor:\nUses Agent 2 stores]
        B2[RuleScorer:\nUses rules.yaml]
        B3[ExcelFiller:\nUses openpyxl]
        B4[Validator:\nISO 13485 compliance]
    end
    
    subgraph Output[Output]
        C1[Filled Excel]
        C2[API Endpoints]
        C3[UI Page]
    end
    
    A2 -->|Data| B1
    B1 --> B2
    B2 --> B3
    B3 --> B4
    B4 --> C1
    B4 --> C2
    B4 --> C3
    C2 --> A4
    C3 --> A5
    
    style Pipeline fill:#ff9,stroke:#333
    style Agent4 fill:#9f9,stroke:#333
    style Output fill:#9ff,stroke:#333
```

---

## 14. State Transition Diagram

```mermaid
stateDiagram-v2
    [*] --> Idle: Initialization
    Idle --> Extracting: Request received
    Extracting --> Scoring: Data extracted
    Scoring --> Optimizing: LLM enabled
    Optimizing --> Filling: Optimization complete
    Scoring --> Filling: LLM disabled
    Filling --> Approving: Excel filled
    Approving --> Validating: Approval granted
    Validating --> Complete: Validation passed
    Complete --> [*]: Output returned
    
    Approving --> Rejected: Approval denied
    Rejected --> [*]: Error returned
    
    Validating --> Failed: Validation failed
    Failed --> [*]: Error returned
    
    note right of Idle
        System ready for
        new requests
    end note
    
    note right of Complete
        Output file
        available for
        download
    end note
```

---

## 15. Class Diagram

```mermaid
classDiagram
    class RiskMatrixGenerator {
        +Config config
        +DataExtractor data_extractor
        +RuleScorer rule_scorer
        +ExcelFiller excel_filler
        +Validator validator
        +LLMClient llm_client
        +AuditLogger audit_logger
        +generate(supplier_id) str
        +_optimize_with_llm(results) dict
        +_human_approval(results, output_path) bool
    }
    
    class DataExtractor {
        +Config config
        +SQLiteStore sqlite_store
        +ChromaStore chroma_store
        +extract(supplier_id) dict
        +_get_document_context(suppliers) list
        +_transform_data(raw_data) dict
    }
    
    class RuleScorer {
        +Config config
        +RulesLoader rules_loader
        +dict rules
        +score(data) dict
        +_score_supplier(supplier_data) dict
        +_calculate_criterion_score(supplier_data, criterion, config) tuple
    }
    
    class ExcelFiller {
        +Config config
        +str template_path
        +dict formula_cells
        +fill(data) str
        +_identify_formula_cells() dict
        +_fill_abc_bew(workbook, data)
        +_fill_zert_status(workbook, data)
        +_fill_krit_lieferante(workbook, data)
        +_fill_versionsverw(workbook, data)
    }
    
    class Validator {
        +Config config
        +list audit_log
        +validate(results, output_path) bool
        +_validate_data_completeness(results) bool
        +_validate_scoring(results) bool
        +_validate_iso_13485(results) bool
        +_validate_output(output_path) bool
    }
    
    class LLMClient {
        +Config config
        +str base_url
        +str model
        +generate(prompt, system, temperature, max_tokens) str
        +analyze(data, analysis_type) dict
    }
    
    RiskMatrixGenerator --> DataExtractor : uses
    RiskMatrixGenerator --> RuleScorer : uses
    RiskMatrixGenerator --> ExcelFiller : uses
    RiskMatrixGenerator --> Validator : uses
    RiskMatrixGenerator --> LLMClient : uses
    
    DataExtractor --> SQLiteStore : uses
    DataExtractor --> ChromaStore : uses
    
    RuleScorer --> RulesLoader : uses
    
    ExcelFiller --> Workbook : uses
```

---

## Summary

This document provides **15 different diagrams** covering:
1. System architecture
2. Data flow
3. Workflow sequence
4. Component interactions
5. Excel filling process
6. Data transformation
7. Scoring process
8. Validation process
9. LLM integration
10. ISO 13485 compliance
11. Error handling
12. Pipeline integration
13. State transitions
14. Class relationships

**All diagrams use Mermaid syntax** which can be:
- Rendered in Markdown viewers (GitHub, VS Code, etc.)
- Copied to Mermaid Live Editor for interactive viewing
- Exported to PNG/SVG using Mermaid tools

**Next Steps:**
1. Review [08_ORCHESTRATION_LAYER.md](./08_ORCHESTRATION_LAYER.md) for LangGraph + LLM details
2. Review [09_VERSION_COMPARISON.md](./09_VERSION_COMPARISON.md) for approach evolution
3. Review [10_IMPLEMENTATION_GUIDE.md](./10_IMPLEMENTATION_GUIDE.md) for setup instructions

---

*Document Version: 1.0.0 | Last Updated: November 2024 | Author: AI Assistant*
