# **Agent 4: Data Flow Diagrams and Interactions**

---

## **Document Information**
- **Version**: 1.0
- **Author**: Vibe Code (Mistral AI)
- **Date**: 2025
- **Purpose**: Visual representation of data flows, interactions, and architecture
- **Format**: Text-based diagrams (Mermaid syntax) for compatibility

---

## **Table of Contents**
1. [Architecture Diagrams](#architecture-diagrams)
2. [Data Flow Diagrams](#data-flow-diagrams)
3. [Sequence Diagrams](#sequence-diagrams)
4. [Component Interaction Diagrams](#component-interaction-diagrams)
5. [State Diagrams](#state-diagrams)
6. [Class Diagrams](#class-diagrams)
7. [File Dependency Diagrams](#file-dependency-diagrams)

---

## **Architecture Diagrams**

### **1. System Architecture Overview**

```mermaid
graph TD
    %% Agent 4: Supplier Risk Matrix Autofill System - Architecture Overview
    
    subgraph UserInterface["👤 USER INTERFACE"]
        UI1[Streamlit Pages]
        UI2[API Endpoints]
        UI3[CLI Commands]
    end
    
    subgraph Orchestration["🎭 ORCHESTRATION LAYER"]
        O1[main.py]
        O2[workflow.py]
        O3[state.py]
    end
    
    subgraph Intelligence["🧠 INTELLIGENCE LAYER"]
        I1[LLM Client]
        I2[Rule Generator]
        I3[Anomaly Detector]
    end
    
    subgraph Execution["⚙️ EXECUTION LAYER"]
        E1[Data Extractor]
        E2[Rule Scorer]
        E3[Excel Filler]
        E4[Validator]
    end
    
    subgraph Configuration["⚙️ CONFIGURATION"]
        C1[rules.yaml]
        C2[prompts.yaml]
        C3[config.py]
    end
    
    subgraph DataSources["💾 DATA SOURCES"]
        D1[SQLite]
        D2[ChromaDB]
        D3[LM Studio]
    end
    
    subgraph Outputs["📤 OUTPUTS"]
        OUT1[Filled Excel]
        OUT2[Logs]
        OUT3[Audit Trail]
    end
    
    %% Connections
    UI1 --> O1
    UI2 --> O1
    UI3 --> O1
    
    O1 --> O2
    O2 --> O3
    O2 --> E1
    O2 --> I1
    
    I1 --> I2
    I1 --> I3
    I2 --> C1
    I3 --> E1
    
    E1 --> D1
    E1 --> D2
    E1 --> E2
    E2 --> C1
    E2 --> E3
    E3 --> C3
    E3 --> OUT1
    E2 --> E4
    E4 --> C1
    E4 --> OUT2
    
    C1 --> E2
    C2 --> I1
    C3 --> O1
    C3 --> E1
    C3 --> E2
    C3 --> E3
    C3 --> E4
    
    D3 --> I1
    
    style UserInterface fill:#f9f,stroke:#333
    style Orchestration fill:#bbf,stroke:#333
    style Intelligence fill:#9f9,stroke:#333
    style Execution fill:#ff9,stroke:#333
    style Configuration fill:#f99,stroke:#333
    style DataSources fill:#99f,stroke:#333
    style Outputs fill:#9ff,stroke:#333
```

---

### **2. Layered Architecture**

```mermaid
graph LR
    %% Layered Architecture
    
    subgraph L1["Layer 1: User Interface"]
        A1[Streamlit]
        A2[FastAPI]
        A3[CLI]
    end
    
    subgraph L2["Layer 2: Orchestration"]
        B1[LangGraph Workflow]
        B2[State Management]
    end
    
    subgraph L3["Layer 3: Intelligence"]
        C1[LLM Client]
        C2[Rule Generator]
        C3[Anomaly Detector]
    end
    
    subgraph L4["Layer 4: Execution"]
        D1[Data Extractor]
        D2[Rule Scorer]
        D3[Excel Filler]
        D4[Validator]
    end
    
    subgraph L5["Layer 5: Data"]
        E1[SQLite]
        E2[ChromaDB]
        E3[Configuration Files]
    end
    
    L1 --> L2
    L2 --> L3
    L3 --> L4
    L4 --> L5
    
    style L1 fill:#ff9999,stroke:#333
    style L2 fill:#99ff99,stroke:#333
    style L3 fill:#9999ff,stroke:#333
    style L4 fill:#ff99ff,stroke:#333
    style L5 fill:#ffff99,stroke:#333
```

---

### **3. Integration with Existing Pipeline**

```mermaid
graph TD
    %% Integration with Existing Pipeline
    
    subgraph Existing["🏭 EXISTING PIPELINE"]
        EA1[Agent 1: Offline Parser]
        EA2[Agent 2: Vector Store]
        EA3[Agent 3: VA26 Evaluator]
        EC[config.py]
        ED1[SQLite]
        ED2[ChromaDB]
        EL[LM Studio]
    end
    
    subgraph New["✨ AGENT 4: RISK MATRIX"]
        NA1[Data Extractor]
        NA2[Rule Scorer]
        NA3[Excel Filler]
        NA4[Validator]
        NC[rules.yaml]
    end
    
    subgraph Shared["🔄 SHARED INFRASTRUCTURE"]
        S1[SQLite Database]
        S2[ChromaDB Index]
        S3[LM Studio LLM]
        S4[Configuration]
    end
    
    %% Connections
    EA1 --> S1
    EA2 --> S1
    EA2 --> S2
    EA3 --> S3
    
    NA1 --> S1
    NA1 --> S2
    NA2 --> S3
    NA2 --> NC
    NA3 --> S4
    
    S1 --> NA1
    S2 --> NA1
    S3 --> NA2
    S4 --> NA1
    S4 --> NA2
    S4 --> NA3
    
    style Existing fill:#f0f0f0,stroke:#666
    style New fill:#e0ffff,stroke:#006
    style Shared fill:#ffffe0,stroke:#666
```

---

## **Data Flow Diagrams**

### **1. End-to-End Data Flow**

```mermaid
flowchart TD
    %% End-to-End Data Flow
    
    Start([Start]) --> Input{Input Method}
    
    Input -->|CLI| Extract[Data Extraction]
    Input -->|API| Extract
    Input -->|UI| Extract
    
    Extract --> Aggregate[Aggregate Metrics]
    Aggregate --> LoadRules[Load Rules]
    LoadRules --> Score[Score Suppliers]
    Score --> Validate[Validate Results]
    Validate --> Approval{Human Approval Required?}
    
    Approval -->|Yes| Human[Human Review]
    Approval -->|No| Fill[Fill Excel Template]
    Human --> Fill
    
    Fill --> Save[Save Output]
    Save --> Output([Output: Filled Excel])
    Save --> Log[Log to Audit Trail]
    
    style Start fill:#90EE90,stroke:#333
    style Input fill:#FFE4B5,stroke:#333
    style Extract fill:#FFB6C1,stroke:#333
    style Aggregate fill:#FFB6C1,stroke:#333
    style LoadRules fill:#DDA0DD,stroke:#333
    style Score fill:#DDA0DD,stroke:#333
    style Validate fill:#DDA0DD,stroke:#333
    style Approval fill:#FFE4B5,stroke:#333
    style Human fill:#FFD700,stroke:#333
    style Fill fill:#98FB98,stroke:#333
    style Save fill:#98FB98,stroke:#333
    style Output fill:#90EE90,stroke:#333
    style Log fill:#98FB98,stroke:#333
```

---

### **2. Data Extraction Flow**

```mermaid
flowchart TD
    %% Data Extraction Flow
    
    subgraph Sources["📊 DATA SOURCES"]
        S1[SQLite: suppliers]
        S2[SQLite: certificate_register]
        S3[SQLite: audit_findings]
        S4[SQLite: purchase_history]
        S5[ChromaDB: embeddings]
    end
    
    subgraph Extraction["🔍 EXTRACTION"]
        E1[Get Supplier IDs]
        E2[Extract Supplier Info]
        E3[Extract Certificates]
        E4[Extract Audit Findings]
        E5[Extract Purchase History]
        E6[Aggregate Metrics]
    end
    
    subgraph Output["📦 OUTPUT"]
        O1[AggregatedSupplierData]
    end
    
    Start([Start Extraction]) --> E1
    E1 --> E2
    E1 --> E3
    E1 --> E4
    E1 --> E5
    
    E2 --> S1
    E3 --> S2
    E4 --> S3
    E5 --> S4
    
    S1 --> E2
    S2 --> E3
    S3 --> E4
    S4 --> E5
    
    E2 --> E6
    E3 --> E6
    E4 --> E6
    E5 --> E6
    
    E6 --> O1
    O1 --> End([End Extraction])
    
    style Sources fill:#E6E6FA,stroke:#333
    style Extraction fill:#FFE4E1,stroke:#333
    style Output fill:#E0FFFF,stroke:#333
```

---

### **3. Scoring Flow**

```mermaid
flowchart TD
    %% Scoring Flow
    
    subgraph Input["📥 INPUT"]
        I1[AggregatedSupplierData]
        I2[rules.yaml]
    end
    
    subgraph Scoring["🎯 SCORING"]
        S1[Load Rules]
        S2[Initialize Scorer]
        S3[Calculate Criterion Scores]
        S4[Calculate Weighted Average]
        S5[Determine Result Class]
    end
    
    subgraph Criteria["📋 CRITERIA"]
        C1[Produktqualität]
        C2[Reklamation]
        C3[Liefertreue]
        C4[Preise]
        C5[Service]
        C6[Entwicklungsfähigkeit]
    end
    
    subgraph Output["📤 OUTPUT"]
        O1[ScoringResult]
    end
    
    Start([Start Scoring]) --> S1
    S1 --> S2
    S2 --> I1
    I2 --> S2
    
    S2 --> S3
    S3 --> C1
    S3 --> C2
    S3 --> C3
    S3 --> C4
    S3 --> C5
    S3 --> C6
    
    C1 --> S4
    C2 --> S4
    C3 --> S4
    C4 --> S4
    C5 --> S4
    C6 --> S4
    
    S4 --> S5
    S5 --> O1
    O1 --> End([End Scoring])
    
    style Input fill:#FFE4B5,stroke:#333
    style Scoring fill:#FFB6C1,stroke:#333
    style Criteria fill:#DDA0DD,stroke:#333
    style Output fill:#E0FFFF,stroke:#333
```

---

### **4. Excel Filling Flow**

```mermaid
flowchart TD
    %% Excel Filling Flow
    
    subgraph Input["📥 INPUT"]
        I1[ScoringResults]
        I2[Template File]
    end
    
    subgraph Filling["📝 FILLING"]
        F1[Load Template]
        F2[Write ABC-Bew Sheet]
        F3[Write Zert-Satus Sheet]
        F4[Write krit Lieferante Sheet]
        F5[Write Versionsverw Sheet]
        F6[Preserve Formulas]
    end
    
    subgraph Sheets["📄 SHEETS"]
        SH1[ABC-Bew]
        SH2[Zert-Satus]
        SH3[krit Lieferante]
        SH4[Versionsverw]
    end
    
    subgraph Output["📤 OUTPUT"]
        O1[Filled Excel File]
    end
    
    Start([Start Filling]) --> F1
    I2 --> F1
    F1 --> F2
    F1 --> F3
    F1 --> F4
    F1 --> F5
    
    F2 --> SH1
    F3 --> SH2
    F4 --> SH3
    F5 --> SH4
    
    I1 --> F2
    I1 --> F3
    I1 --> F4
    I1 --> F5
    
    F2 --> F6
    F3 --> F6
    F4 --> F6
    F5 --> F6
    
    F6 --> O1
    O1 --> End([End Filling])
    
    style Input fill:#FFE4B5,stroke:#333
    style Filling fill:#FFB6C1,stroke:#333
    style Sheets fill:#DDA0DD,stroke:#333
    style Output fill:#E0FFFF,stroke:#333
```

---

## **Sequence Diagrams**

### **1. Main Workflow Sequence**

```mermaid
sequenceDiagram
    participant User
    participant Main as main.py
    participant Workflow as RiskMatrixWorkflow
    participant Extractor as DataExtractor
    participant Scorer as RuleScorer
    participant Validator as RiskMatrixValidator
    participant Filler as ExcelFiller
    participant SQLite as SQLite Database
    participant Output as Output Files
    
    User->>Main: Run CLI command
    Main->>Workflow: Initialize
    
    User->>Main: execute(supplier_id)
    Main->>Workflow: execute(supplier_id)
    
    Workflow->>Extractor: extract_supplier(supplier_id)
    Extractor->>SQLite: Query supplier data
    SQLite-->>Extractor: Return data
    Extractor->>Extractor: Aggregate metrics
    Extractor-->>Workflow: AggregatedSupplierData
    
    Workflow->>Workflow: Load rules.yaml
    Workflow->>Scorer: Initialize with rules
    Workflow->>Scorer: score_supplier(data)
    Scorer->>Scorer: Calculate criterion scores
    Scorer->>Scorer: Calculate weighted average
    Scorer-->>Workflow: ScoringResult
    
    Workflow->>Validator: validate_result(result)
    Validator->>Validator: Check completeness
    Validator->>Validator: Check ISO 13485 compliance
    Validator-->>Workflow: ValidationResult
    
    Workflow->>Filler: fill_template(result)
    Filler->>Filler: Load template.xlsx
    Filler->>Filler: Write to ABC-Bew sheet
    Filler->>Filler: Write to Zert-Satus sheet
    Filler->>Filler: Write to krit Lieferante sheet
    Filler->>Filler: Write to Versionsverw sheet
    Filler->>Output: Save filled.xlsx
    Filler-->>Workflow: output_path
    
    Workflow-->>Main: Return results
    Main-->>User: Display results
```

---

### **2. LLM Rule Generation Sequence**

```mermaid
sequenceDiagram
    participant User
    participant Main as main.py
    participant Workflow as RiskMatrixWorkflow
    participant RuleGen as RuleGenerator
    participant LLM as LLMClient
    participant LMStudio as LM Studio
    participant RulesFile as rules.yaml
    
    User->>Main: generate-rules command
    Main->>Workflow: generate_rules()
    
    Workflow->>Extractor: extract_sample_data()
    Extractor->>SQLite: Query sample suppliers
    SQLite-->>Extractor: Return sample data
    Extractor-->>Workflow: sample_data
    
    Workflow->>RuleGen: generate_rules(sample_data)
    RuleGen->>LLM: Generate prompt
    LLM->>LMStudio: Send request
    LMStudio-->>LLM: Return rule suggestions
    LLM-->>RuleGen: rule_suggestions
    
    RuleGen->>RuleGen: Parse YAML
    RuleGen->>RuleGen: Validate rules
    RuleGen->>RulesFile: Save new rules
    RuleGen-->>Workflow: new_rules
    
    Workflow-->>Main: Return new_rules
    Main-->>User: Display new rules
```

---

### **3. Anomaly Detection Sequence**

```mermaid
sequenceDiagram
    participant Workflow as RiskMatrixWorkflow
    participant Detector as AnomalyDetector
    participant LLM as LLMClient
    participant LMStudio as LM Studio
    participant Extractor as DataExtractor
    
    Workflow->>Extractor: extract_all_suppliers()
    Extractor-->>Workflow: all_supplier_data
    
    Workflow->>Detector: detect_anomalies(all_supplier_data)
    Detector->>LLM: Analyze data prompt
    LLM->>LMStudio: Send request
    LMStudio-->>LLM: Return anomalies
    LLM-->>Detector: anomaly_list
    
    Detector->>Detector: Parse anomalies
    Detector->>Detector: Filter by severity
    Detector-->>Workflow: detected_anomalies
    
    Workflow->>Workflow: Log anomalies
    Workflow->>Workflow: Flag high-risk suppliers
```

---

## **Component Interaction Diagrams**

### **1. Orchestrator Component Interactions**

```mermaid
graph TD
    %% Orchestrator Component Interactions
    
    Workflow[RiskMatrixWorkflow] --> Extractor[DataExtractor]
    Workflow --> Scorer[RuleScorer]
    Workflow --> Filler[ExcelFiller]
    Workflow --> Validator[RiskMatrixValidator]
    Workflow --> RuleGen[RuleGenerator]
    Workflow --> Detector[AnomalyDetector]
    
    Extractor --> SQLite[SQLite Database]
    Extractor --> ChromaDB[ChromaDB]
    
    Scorer --> Rules[rules.yaml]
    
    Filler --> Template[Template File]
    Filler --> Output[Output File]
    
    Validator --> Rules
    
    RuleGen --> LLM[LLM Client]
    Detector --> LLM
    
    LLM --> LMStudio[LM Studio]
    
    style Workflow fill:#FFD700,stroke:#333
    style Extractor fill:#FFB6C1,stroke:#333
    style Scorer fill:#FFB6C1,stroke:#333
    style Filler fill:#FFB6C1,stroke:#333
    style Validator fill:#FFB6C1,stroke:#333
    style RuleGen fill:#99FF99,stroke:#333
    style Detector fill:#99FF99,stroke:#333
    style LLM fill:#99FF99,stroke:#333
    style SQLite fill:#99CCFF,stroke:#333
    style ChromaDB fill:#99CCFF,stroke:#333
    style Rules fill:#FF99CC,stroke:#333
    style Template fill:#CCFF99,stroke:#333
    style Output fill:#CCFF99,stroke:#333
```

---

### **2. Data Layer Interactions**

```mermaid
graph TD
    %% Data Layer Interactions
    
    subgraph Models["📊 DATA MODELS"]
        M1[AggregatedSupplierData]
        M2[CertificateModel]
        M3[AuditFindingModel]
        M4[PurchaseHistoryModel]
        M5[ScoringResult]
        M6[ValidationResult]
    end
    
    subgraph Extractors["🔍 EXTRACTORS"]
        E1[DataExtractor]
        E2[SQLite Queries]
        E3[ChromaDB Queries]
        E4[Aggregation Logic]
    end
    
    subgraph Sources["💾 SOURCES"]
        S1[SQLite: suppliers]
        S2[SQLite: certificate_register]
        S3[SQLite: audit_findings]
        S4[SQLite: purchase_history]
        S5[ChromaDB: embeddings]
    end
    
    E2 --> S1
    E2 --> S2
    E2 --> S3
    E2 --> S4
    E3 --> S5
    
    S1 --> E2
    S2 --> E2
    S3 --> E2
    S4 --> E2
    S5 --> E3
    
    E2 --> E1
    E3 --> E1
    E4 --> E1
    
    E1 --> M1
    E1 --> M2
    E1 --> M3
    E1 --> M4
    
    M1 --> M5
    M5 --> M6
    
    style Models fill:#E0FFFF,stroke:#333
    style Extractors fill:#FFE4E1,stroke:#333
    style Sources fill:#E6E6FA,stroke:#333
```

---

### **3. Execution Layer Interactions**

```mermaid
graph TD
    %% Execution Layer Interactions
    
    subgraph Execution["⚙️ EXECUTION"]
        EX1[RuleScorer]
        EX2[ExcelFiller]
        EX3[RiskMatrixValidator]
    end
    
    subgraph Inputs["📥 INPUTS"]
        I1[AggregatedSupplierData]
        I2[rules.yaml]
        I3[Template File]
    end
    
    subgraph Outputs["📤 OUTPUTS"]
        O1[ScoringResult]
        O2[Filled Excel]
        O3[ValidationResult]
    end
    
    I1 --> EX1
    I2 --> EX1
    EX1 --> O1
    
    I1 --> EX2
    I3 --> EX2
    EX2 --> O2
    
    I1 --> EX3
    I2 --> EX3
    EX3 --> O3
    
    O1 --> EX2
    O1 --> EX3
    
    style Execution fill:#FFB6C1,stroke:#333
    style Inputs fill:#FFE4B5,stroke:#333
    style Outputs fill:#E0FFFF,stroke:#333
```

---

## **State Diagrams**

### **1. Workflow State Machine**

```mermaid
stateDiagram-v2
    %% Workflow State Machine
    
    [*] --> Idle: Initialization
    
    state "Processing" as Processing
    state "Error Handling" as ErrorHandling
    
    Idle --> Extracting: User requests generation
    Extracting --> Aggregating: Data extracted
    Aggregating --> LoadingRules: Metrics aggregated
    LoadingRules --> Scoring: Rules loaded
    Scoring --> Validating: Scores calculated
    Validating --> Filling: Validation passed
    Filling --> Completing: Excel filled
    Completing --> Idle: Output saved
    
    Validating --> Approval: Human approval required
    Approval --> Filling: Approved
    Approval --> ErrorHandling: Rejected
    
    state ErrorHandling {
        [*] --> Logging
        Logging --> Recovering: Recoverable error
        Logging --> Failing: Unrecoverable error
        Recovering --> Extracting: Retry extraction
        Recovering --> Scoring: Retry scoring
        Failing --> Idle: Cleanup
    }
    
    Processing --> ErrorHandling: Error occurs
    
    note right of Approval
        ISO 13485 §7.4.1
        Human approval
        required for final
        decisions
    end note
```

---

### **2. Supplier Processing State**

```mermaid
stateDiagram-v2
    %% Supplier Processing State
    
    [*] --> Waiting: Supplier in queue
    
    Waiting --> Extracting: Processing starts
    Extracting --> Aggregating: Data extracted
    Aggregating --> Scoring: Metrics calculated
    Scoring --> Validating: Scores calculated
    Validating --> Completed: Validation passed
    
    Validating --> Error: Validation failed
    Extracting --> Error: Extraction failed
    Aggregating --> Error: Aggregation failed
    Scoring --> Error: Scoring failed
    
    state Error {
        [*] --> Logging
        Logging --> Retrying: Retry limit not reached
        Retrying --> Extracting: Retry extraction
        Logging --> Failed: Max retries reached
    }
    
    Completed --> [*]
    Failed --> [*]
    
    note right of Validating
        Checks:
        - Data completeness
        - Score ranges
        - ISO 13485 compliance
    end note
```

---

## **Class Diagrams**

### **1. Core Classes**

```mermaid
classDiagram
    %% Core Classes
    
    class Config {
        +sqlite_path: Path
        +chroma_db_path: Path
        +llm_base_url: str
        +llm_model: str
        +template_path: Path
        +output_dir: Path
        +rules_yaml_path: Path
        +load_rules() dict
        +load_prompts() dict
    }
    
    class RiskMatrixWorkflow {
        -config: Config
        -extractor: DataExtractor
        -scorer: RuleScorer
        -filler: ExcelFiller
        -validator: RiskMatrixValidator
        +execute(supplier_id: str) dict
        +execute_all() List[dict]
        +generate_rules() dict
    }
    
    class DataExtractor {
        -config: Config
        -sqlite_conn: sqlite3.Connection
        +extract_supplier(supplier_id: str) AggregatedSupplierData
        +extract_all_suppliers() List[AggregatedSupplierData]
        +close()
    }
    
    class RuleScorer {
        -rules: dict
        +score_supplier(supplier: AggregatedSupplierData) ScoringResult
        +score_all_suppliers(suppliers: List[AggregatedSupplierData]) List[ScoringResult]
    }
    
    class ExcelFiller {
        -template_path: Path
        -output_path: Path
        +fill_template(data: dict) Path
    }
    
    class RiskMatrixValidator {
        -rules: dict
        +validate_supplier(supplier: AggregatedSupplierData) ValidationResult
        +validate_scoring(result: ScoringResult) ValidationResult
    }
    
    Config --> RiskMatrixWorkflow
    Config --> DataExtractor
    Config --> RuleScorer
    Config --> ExcelFiller
    Config --> RiskMatrixValidator
    
    RiskMatrixWorkflow --> DataExtractor
    RiskMatrixWorkflow --> RuleScorer
    RiskMatrixWorkflow --> ExcelFiller
    RiskMatrixWorkflow --> RiskMatrixValidator
    
    DataExtractor --> AggregatedSupplierData
    RuleScorer --> ScoringResult
    ExcelFiller --> Path
    RiskMatrixValidator --> ValidationResult
```

---

### **2. Data Model Classes**

```mermaid
classDiagram
    %% Data Model Classes
    
    class AggregatedSupplierData {
        +supplier_id: str
        +legal_name: str
        +short_name: Optional[str]
        +certificate: Optional[CertificateModel]
        +certificates: List[CertificateModel]
        +audit_findings: List[AuditFindingModel]
        +purchase_history: List[PurchaseHistoryModel]
        +total_orders: int
        +total_value: float
        +quality_score: Optional[float]
        +complaint_rate: Optional[float]
        +on_time_delivery_rate: Optional[float]
        +price_variance: Optional[float]
        +service_score: Optional[float]
        +development_score: Optional[float]
        +consecutive_delays: int
    }
    
    class CertificateModel {
        +certificate_type: str
        +certificate_number: Optional[str]
        +issue_date: Optional[date]
        +expiry_date: Optional[date]
        +issuing_body: Optional[str]
        +is_expiring_soon(threshold_days: int) bool
    }
    
    class AuditFindingModel {
        +finding_id: str
        +supplier_id: str
        +audit_date: date
        +severity: str
        +category: str
        +description: str
        +score: Optional[float]
        +quality_score: Optional[float]
        +complaint_count: Optional[int]
        +consecutive_delays: Optional[int]
    }
    
    class PurchaseHistoryModel {
        +purchase_id: str
        +supplier_id: str
        +order_date: date
        +delivery_date: Optional[date]
        +promised_delivery_date: date
        +unit_price: float
        +quantity: int
        +total_value: float
        +on_time: bool
        +delay_days: Optional[int]
    }
    
    class ScoringResult {
        +supplier_id: str
        +legal_name: str
        +criteria_scores: Dict[str, CriterionScore]
        +weighted_sum: float
        +total_weight: float
        +weighted_average: float
        +result_class: ResultClass
        +scored_at: datetime
        +rules_version: str
        +anomalies: List[dict]
        +is_critical: bool
        +critical_reason: Optional[str]
    }
    
    class CriterionScore {
        +criterion: str
        +raw_score: Optional[float]
        +normalized_score: float
        +weight: float
        +weighted_score: float
        +threshold: str
    }
    
    class ValidationResult {
        +supplier_id: str
        +is_valid: bool
        +errors: List[str]
        +warnings: List[str]
        +completeness: float
        +iso_13485_compliant: bool
        +requires_human_approval: bool
    }
    
    ResultClass "1" --> "A"
    ResultClass "2" --> "B"
    ResultClass "3" --> "C"
    
    AggregatedSupplierData "1" *-- "1..*" CertificateModel
    AggregatedSupplierData "1" *-- "1..*" AuditFindingModel
    AggregatedSupplierData "1" *-- "1..*" PurchaseHistoryModel
    ScoringResult "1" *-- "1" AggregatedSupplierData
    ScoringResult "1" *-- "1..*" CriterionScore
    ScoringResult "1" *-- "0..*" ValidationResult
```

---

### **3. LLM Classes**

```mermaid
classDiagram
    %% LLM Classes
    
    class LLMClient {
        -config: Config
        -client: httpx.Client
        -model: str
        +generate(prompt: str, system_prompt: Optional[str]) str
        +chat(messages: List[dict]) str
    }
    
    class RuleGenerator {
        -llm: LLMClient
        +generate_rules(supplier_data: List[AggregatedSupplierData]) dict
        +optimize_rules(current_rules: dict, data: List[AggregatedSupplierData]) dict
        +suggest_improvements(rules: dict) List[str]
    }
    
    class AnomalyDetector {
        -llm: LLMClient
        +detect_anomalies(supplier_data: List[AggregatedSupplierData]) List[Anomaly]
        +analyze_trends(supplier_data: List[AggregatedSupplierData]) List[Trend]
        +flag_high_risk(supplier_data: AggregatedSupplierData) bool
    }
    
    class Anomaly {
        +supplier_id: str
        +anomaly_type: str
        +severity: Severity
        +details: str
        +recommendation: Optional[str]
    }
    
    Severity "1" --> "Low"
    Severity "2" --> "Medium"
    Severity "3" --> "High"
    Severity "4" --> "Critical"
    
    LLMClient --> RuleGenerator
    LLMClient --> AnomalyDetector
    RuleGenerator --> AnomalyDetector
```

---

## **File Dependency Diagrams**

### **1. Agent 4 File Dependencies**

```mermaid
graph TD
    %% File Dependencies
    
    subgraph Root["agent4_risk_matrix/"]
        A[__init__.py]
        B[main.py]
    end
    
    subgraph Config["config/"]
        C1[__init__.py]
        C2[rules.yaml]
        C3[prompts.yaml]
    end
    
    subgraph Data["data/"]
        D1[__init__.py]
        D2[models.py]
        D3[extractor.py]
    end
    
    subgraph Execution["execution/"]
        E1[__init__.py]
        E2[scorer.py]
        E3[excel_filler.py]
        E4[validator.py]
    end
    
    subgraph LLM["llm/"]
        L1[__init__.py]
        L2[client.py]
        L3[rule_generator.py]
        L4[anomaly_detector.py]
    end
    
    subgraph Orchestrator["orchestrator/"]
        O1[__init__.py]
        O2[workflow.py]
        O3[state.py]
    end
    
    %% Dependencies
    B --> A
    B --> C1
    B --> O2
    
    C1 --> pipeline_config[pipeline/config.py]
    
    A --> D2
    A --> E2
    A --> E3
    A --> E4
    A --> D3
    A --> L2
    A --> L3
    A --> L4
    A --> O2
    A --> C1
    
    D2 --> D3
    D3 --> C1
    D3 --> pipeline_sqlite[pipeline/agent2_vectorstore/storage/sqlite_store.py]
    
    E2 --> C2
    E2 --> D2
    E3 --> C1
    E4 --> C2
    
    L2 --> C1
    L3 --> L2
    L3 --> C2
    L4 --> L2
    L4 --> C2
    
    O2 --> C1
    O2 --> D3
    O2 --> E2
    O2 --> E3
    O2 --> E4
    O2 --> L3
    O2 --> L4
    
    style Root fill:#FFE4B5,stroke:#333
    style Config fill:#FF99CC,stroke:#333
    style Data fill:#99FF99,stroke:#333
    style Execution fill:#99CCFF,stroke:#333
    style LLM fill:#FFCC99,stroke:#333
    style Orchestrator fill:#CC99FF,stroke:#333
```

---

### **2. Integration Dependencies**

```mermaid
graph TD
    %% Integration Dependencies
    
    subgraph Agent4["Agent 4"]
        A4[agent4_risk_matrix/]
    end
    
    subgraph Existing["Existing Pipeline"]
        P1[pipeline/config.py]
        P2[pipeline/agent2_vectorstore/]
        P3[pipeline/agent3_evaluator/]
        P4[pipeline/api/]
        P5[pipeline/ui/]
    end
    
    subgraph External["External Dependencies"]
        E1[openpyxl]
        E2[xlsxtpl]
        E3[Jinja2]
        E4[langgraph]
        E5[pyyaml]
        E6[pandas]
        E7[httpx]
        E8[SQLite]
        E9[ChromaDB]
        E10[LM Studio]
    end
    
    %% Agent 4 Dependencies
    A4 --> P1
    A4 --> P2
    A4 --> P3
    
    A4 --> E1
    A4 --> E2
    A4 --> E3
    A4 --> E4
    A4 --> E5
    A4 --> E6
    A4 --> E7
    A4 --> E8
    A4 --> E9
    A4 --> E10
    
    %% Existing Pipeline Dependencies
    P1 --> E5
    P1 --> E8
    P1 --> E9
    P1 --> E10
    
    P2 --> E1
    P2 --> E8
    P2 --> E9
    
    P3 --> P1
    P3 --> E1
    
    P4 --> P1
    P4 --> E4
    
    P5 --> P1
    P5 --> E6
    
    style Agent4 fill:#E0FFFF,stroke:#006
    style Existing fill:#F0F0F0,stroke:#666
    style External fill:#FFFFE0,stroke:#666
```

---

## **Summary**

This document provides **comprehensive visual documentation** of Agent 4's architecture, data flows, and interactions through:

### **📊 Architecture Diagrams**
- System architecture overview
- Layered architecture
- Integration with existing pipeline

### **📈 Data Flow Diagrams**
- End-to-end data flow
- Data extraction flow
- Scoring flow
- Excel filling flow

### **📽️ Sequence Diagrams**
- Main workflow sequence
- LLM rule generation sequence
- Anomaly detection sequence

### **🔗 Component Interaction Diagrams**
- Orchestrator component interactions
- Data layer interactions
- Execution layer interactions

### **🔄 State Diagrams**
- Workflow state machine
- Supplier processing state

### **🏗️ Class Diagrams**
- Core classes
- Data model classes
- LLM classes

### **📁 File Dependency Diagrams**
- Agent 4 file dependencies
- Integration dependencies

These diagrams **complement the textual documentation** and provide a **visual understanding** of how the system works.

---

## **How to Use These Diagrams**

1. **For Understanding Architecture**: Start with the architecture diagrams
2. **For Debugging**: Use the data flow and sequence diagrams
3. **For Development**: Reference the class and component interaction diagrams
4. **For Integration**: Use the file dependency diagrams
5. **For Documentation**: Include relevant diagrams in other documents

---

## **Mermaid Syntax Reference**

All diagrams in this document use **Mermaid syntax**, which is:
- **Compatible** with many documentation tools (GitHub, GitLab, VS Code, etc.)
- **Text-based** for easy version control
- **Readable** in plain text
- **Renderable** in Markdown viewers that support Mermaid

---

*Document Version: 1.0 | Author: Vibe Code (Mistral AI)*
