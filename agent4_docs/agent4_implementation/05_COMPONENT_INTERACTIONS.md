# Component Interactions: Agent 4 Implementation

## 1. Overview

This document explains **how all components interact** in Agent 4, including:
- Inter-module communication
- API contracts between components
- Data flow between modules
- Error handling and recovery

---

## 2. Component Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPONENT INTERACTIONS                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                        main.py                                │  │
│  │  (Orchestrator)                                               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │  │
│  │  │DataExtractor│  │ RuleScorer  │  │ExcelFiller  │          │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │  │
│  │         │                │                 │                │  │
│  └─────────┼────────────────┼─────────────────┼────────────────┘  │
│            │                │                 │                      │
│  ┌─────────▼────────────────▼─────────────────▼────────────────┐  │
│  │                    External Dependencies                     │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │  │
│  │  │SQLite Store │  │ChromaDB     │  │LM Studio Client     │  │  │
│  │  │(Agent 2)    │  │(Agent 2)    │  │(LLM)                │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    validator.py                               │  │
│  │  (Validation)                                                  │  │
│  │  ┌─────────────────────────────────────────────────────────┐│  │
│  │  │  - Data Completeness Validation                           ││  │
│  │  │  - Scoring Validity Validation                             ││  │
│  │  │  - ISO 13485 Compliance Validation                          ││  │
│  │  │  - Output Integrity Validation                              ││  │
│  │  └─────────────────────────────────────────────────────────┘│  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Orchestrator (main.py)

### 3.1 Role
- **Primary controller** for Agent 4
- **Coordinates** all components
- **Manages** workflow execution
- **Handles** errors and logging

### 3.2 Dependencies

| Component | Purpose | Initialization |
|-----------|---------|----------------|
| DataExtractor | Extract data from databases | `DataExtractor(config)` |
| RuleScorer | Apply scoring rules | `RuleScorer(config)` |
| ExcelFiller | Fill Excel template | `ExcelFiller(config)` |
| Validator | Validate results | `Validator(config)` |
| LLMClient | LLM integration | `LLMClient(config)` |

### 3.3 Workflow

```python
# In main.py
class RiskMatrixGenerator:
    def __init__(self, config: Config):
        self.config = config
        self.data_extractor = DataExtractor(config)
        self.rule_scorer = RuleScorer(config)
        self.excel_filler = ExcelFiller(config)
        self.validator = Validator(config)
        self.llm_client = LLMClient(config)
    
    def generate(self, supplier_id: str = None) -> str:
        # 1. Extract data
        data = self.data_extractor.extract(supplier_id)
        
        # 2. Score suppliers
        results = self.rule_scorer.score(data)
        
        # 3. Optional: LLM optimization
        if self.config.use_llm_optimization:
            results = self._optimize_with_llm(results)
        
        # 4. Fill Excel template
        output_path = self.excel_filler.fill(results)
        
        # 5. Human approval
        if not self._human_approval(results):
            raise ApprovalError("Human approval required")
        
        # 6. Validate
        self.validator.validate(results, output_path)
        
        # 7. Return output
        return output_path
```

### 3.4 Data Flow

```
main.py
  │
  ├─▶ DataExtractor.extract() ───▶ Structured Data
  │
  ├─▶ RuleScorer.score() ───────▶ Scoring Results
  │
  ├─▶ LLMClient.optimize() ────▶ Optimized Results (Optional)
  │
  ├─▶ ExcelFiller.fill() ────────▶ Filled Excel File
  │
  ├─▶ Validator.validate() ─────▶ Validation Report
  │
  └─▶ Return Output Path
```

---

## 4. Data Extractor (data_extractor.py)

### 4.1 Role
- **Extracts** data from SQLite and ChromaDB
- **Transforms** data into scoring-ready format
- **Caches** intermediate results

### 4.2 Dependencies

| Component | Purpose | Source |
|-----------|---------|--------|
| SQLiteStore | Structured data | pipeline.agent2_vectorstore.storage.sqlite_store |
| ChromaStore | Vector data | pipeline.agent2_vectorstore.storage.chroma_store |

### 4.3 API Contract

**Input:**
```python
supplier_id: str = None  # Optional: None for all suppliers
```

**Output:**
```python
{
    'abc_bew': [
        {
            'supplier_id': str,
            'legal_name': str,
            'produktqualitaet': float,
            'reklamation': float,
            'liefertreue': float,
            'termine': float,
            'service': float,
            'preis': float,
            'source_documents': list[str],
            'traceability': dict
        }
    ],
    'zert_status': [
        {
            'SUP': str,
            'Name': str,
            'Zertifikat': str,
            'Zertifizierungsstelle': str,
            'gueltig_bis': str
        }
    ],
    'krit_lieferante': [
        {
            'SUP': str,
            'Name': str,
            'Kritikalität': str,
            'Begründung': str,
            'Maßnahmen': str,
            'Verantwortlich': str,
            'Termin': str,
            'Status': str,
            'Bemerkungen': str
        }
    ],
    'metadata': {
        'timestamp': str,
        'supplier_count': int,
        'document_count': int
    }
}
```

### 4.4 Interaction with External Components

```python
# In data_extractor.py
class DataExtractor:
    def __init__(self, config: Config):
        self.config = config
        # Initialize external dependencies
        self.sqlite_store = SQLiteStore(config.database_path)
        self.chroma_store = ChromaStore(config.chroma_path)
    
    def extract(self, supplier_id: str = None) -> dict:
        # 1. Get data from SQLite
        if supplier_id:
            suppliers = self.sqlite_store.get_supplier(supplier_id)
            purchase_history = self.sqlite_store.get_purchase_history(supplier_id)
            certificates = self.sqlite_store.get_certificates(supplier_id)
        else:
            suppliers = self.sqlite_store.get_all_suppliers()
            purchase_history = self.sqlite_store.get_all_purchase_history()
            certificates = self.sqlite_store.get_all_certificates()
        
        # 2. Get documents from ChromaDB
        documents = []
        for supplier in suppliers:
            docs = self.chroma_store.query(
                f"supplier:{supplier['id']}",
                n_results=10
            )
            documents.extend(docs)
        
        # 3. Transform data
        return self._transform_data({
            'suppliers': suppliers,
            'purchase_history': purchase_history,
            'certificates': certificates,
            'documents': documents
        })
```

---

## 5. Rule Scorer (scorer.py)

### 5.1 Role
- **Loads** scoring rules from rules.yaml
- **Applies** rules to supplier data
- **Calculates** weighted scores
- **Determines** result classes (A, B, C)
- **Generates** explanations

### 5.2 Dependencies

| Component | Purpose | Source |
|-----------|---------|--------|
| RulesLoader | Load rules from YAML | config.loader |

### 5.3 API Contract

**Input:**
```python
{
    'abc_bew': [
        {
            'supplier_id': str,
            'legal_name': str,
            'produktqualitaet': float,
            'reklamation': float,
            'liefertreue': float,
            'termine': float,
            'service': float,
            'preis': float,
            # ... other fields
        }
    ],
    'zert_status': [...],
    'krit_lieferante': [...],
    'metadata': {...}
}
```

**Output:**
```python
{
    'abc_bew': [
        {
            'supplier_id': str,
            'legal_name': str,
            'produktqualitaet': float,
            # ... input fields ...
            'scores': {
                'produktqualitaet': int,  # 1, 2, or 3
                'reklamation': int,
                'liefertreue': int,
                'termine': int,
                'service': int,
                'preis': int
            },
            'explanations': {
                'produktqualitaet': str,
                # ...
            },
            'weighted_score': float,
            'result_class': str,  # 'A', 'B', or 'C'
            'overall_explanation': str
        }
    ],
    'zert_status': [...],
    'krit_lieferante': [...],
    'metadata': {...}
}
```

### 5.4 Interaction with Rules Loader

```python
# In scorer.py
class RuleScorer:
    def __init__(self, config: Config):
        self.config = config
        self.rules_loader = RulesLoader(config)
        self.rules = self.rules_loader.get_rules()
    
    def score(self, data: dict) -> dict:
        # Apply rules to each supplier
        results = []
        for entry in data['abc_bew']:
            scored_entry = self._score_supplier(entry)
            results.append(scored_entry)
        
        return {
            'abc_bew': results,
            'zert_status': data['zert_status'],
            'krit_lieferante': data['krit_lieferante'],
            'metadata': data['metadata']
        }
```

---

## 6. Excel Filler (excel_filler.py)

### 6.1 Role
- **Loads** Excel template
- **Identifies** formula cells to preserve
- **Maps** data to template cells
- **Updates** only data cells
- **Preserves** all formatting
- **Saves** filled template

### 6.2 Dependencies

| Component | Purpose | Source |
|-----------|---------|--------|
| openpyxl | Excel manipulation | openpyxl |

### 6.3 API Contract

**Input:**
```python
{
    'abc_bew': [
        {
            'supplier_id': str,
            'legal_name': str,
            'scores': {
                'produktqualitaet': int,
                # ...
            },
            'weighted_score': float,
            'result_class': str
        }
    ],
    'zert_status': [...],
    'krit_lieferante': [...],
    'metadata': {...}
}
```

**Output:**
```python
'/path/to/output/Lieferantenbewertung_<timestamp>.xlsx'
```

### 6.5 Interaction with Template

```python
# In excel_filler.py
class ExcelFiller:
    def __init__(self, config: Config):
        self.config = config
        self.template_path = config.template_path
        
        # Validate template
        self._validate_template()
        
        # Identify formula cells
        self.formula_cells = self._identify_formula_cells()
    
    def fill(self, data: dict) -> str:
        # Load workbook
        workbook = openpyxl.load_workbook(self.template_path)
        
        # Fill each sheet
        self._fill_abc_bew(workbook, data)
        self._fill_zert_status(workbook, data)
        self._fill_krit_lieferante(workbook, data)
        self._fill_versionsverw(workbook, data)
        
        # Save
        output_path = self._generate_output_path()
        workbook.save(output_path)
        
        return output_path
```

---

## 7. Validator (validator.py)

### 7.1 Role
- **Validates** data completeness
- **Validates** scoring logic
- **Validates** ISO 13485 compliance
- **Validates** output integrity
- **Generates** validation reports
- **Maintains** audit trail

### 7.2 API Contract

**Input:**
```python
results: {
    'abc_bew': [...],
    'zert_status': [...],
    'krit_lieferante': [...],
    'metadata': {...}
}
output_path: str  # Path to filled Excel file
```

**Output:**
```python
# Returns True if all validations pass
True

# Raises ValidationError if any validation fails
ValidationError("Validation failed", validation_results)
```

### 7.3 Validation Checks

```python
# In validator.py
class Validator:
    def validate(self, results: dict, output_path: str) -> bool:
        validation_results = {
            'data_completeness': self._validate_data_completeness(results),
            'scoring_validity': self._validate_scoring(results),
            'iso_13485_compliance': self._validate_iso_13485(results),
            'output_integrity': self._validate_output(output_path)
        }
        
        # Log results
        self._log_validation(validation_results)
        
        # Check all passed
        all_passed = all(validation_results.values())
        
        if not all_passed:
            raise ValidationError("Validation failed", validation_results)
        
        return all_passed
```

---

## 8. LLM Client (llm/client.py)

### 8.1 Role
- **Manages** connection to LM Studio
- **Sends** prompts to LLM
- **Receives** responses from LLM
- **Handles** errors and retries
- **Manages** context and memory

### 8.2 Dependencies

| Component | Purpose | Source |
|-----------|---------|--------|
| requests | HTTP requests | requests |

### 8.3 API Contract

**Input:**
```python
prompt: str
system: str = None  # Optional system message
temperature: float = 0.0  # Default: deterministic
max_tokens: int = 2000
```

**Output:**
```python
'LLM response text'
```

### 8.4 Interaction with LM Studio

```python
# In llm/client.py
class LLMClient:
    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.lm_studio_url
        self.model = config.lm_studio_model
        self.timeout = config.lm_studio_timeout
        self.max_retries = config.lm_studio_max_retries
    
    def generate(self, prompt: str, system: str = None, 
                 temperature: float = 0.0, max_tokens: int = 2000) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system or ""},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                return response.json()['choices'][0]['message']['content']
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise LLMError(f"LLM request failed: {e}")
                time.sleep(2 ** attempt)
```

---

## 9. Error Handling

### 9.1 Error Propagation

```
main.py
  │
  ├─▶ DataExtractor.extract() ───▶ DataExtractionError
  │
  ├─▶ RuleScorer.score() ───────▶ Agent4Error
  │
  ├─▶ ExcelFiller.fill() ────────▶ Agent4Error
  │
  ├─▶ Validator.validate() ─────▶ ValidationError
  │
  └─▶ LLMClient.generate() ─────▶ LLMError
```

### 9.2 Error Handling in Orchestrator

```python
# In main.py
class RiskMatrixGenerator:
    def generate(self, supplier_id: str = None) -> str:
        try:
            # Extract data
            data = self.data_extractor.extract(supplier_id)
            
            # Score suppliers
            results = self.rule_scorer.score(data)
            
            # Fill Excel
            output_path = self.excel_filler.fill(results)
            
            # Validate
            self.validator.validate(results, output_path)
            
            return output_path
            
        except DataExtractionError as e:
            logger.error(f"Data extraction failed: {e}")
            raise Agent4Error(f"Data extraction failed: {e}") from e
            
        except ValidationError as e:
            logger.error(f"Validation failed: {e}")
            raise Agent4Error(f"Validation failed: {e}") from e
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise Agent4Error(f"Unexpected error: {e}") from e
```

---

## 10. Summary

### 10.1 Component Interaction Matrix

| From \ To | DataExtractor | RuleScorer | ExcelFiller | Validator | LLMClient |
|------------|---------------|-------------|-------------|-----------|-----------|
| main.py | ✓ | ✓ | ✓ | ✓ | ✓ |
| DataExtractor | - | Data | - | - | - |
| RuleScorer | - | - | Results | Results | - |
| ExcelFiller | - | - | - | Output | - |
| Validator | - | - | - | - | - |
| LLMClient | - | - | - | - | - |

### 10.2 Key Interactions

1. **main.py → All** - Orchestrates all components
2. **DataExtractor → SQLite/ChromaDB** - Extracts data
3. **RuleScorer → RulesLoader** - Loads rules
4. **ExcelFiller → openpyxl** - Manipulates Excel
5. **Validator → All** - Validates everything
6. **LLMClient → LM Studio** - Gets intelligence

### 10.3 Data Flow Summary

```
User Request
  │
  ▼
main.py (Orchestrator)
  │
  ├─▶ DataExtractor ──▶ SQLite/ChromaDB ──▶ Structured Data
  │
  ├─▶ RuleScorer ──▶ RulesLoader ──▶ Scoring Results
  │
  ├─▶ LLMClient ──▶ LM Studio ──▶ Optimized Results (Optional)
  │
  ├─▶ ExcelFiller ──▶ Template ──▶ Filled Excel
  │
  ├─▶ Validator ──▶ Validation Report
  │
  └─▶ Output
```

---

*Document Version: 1.0.0 | Last Updated: November 2024 | Author: AI Assistant*
