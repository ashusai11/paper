# Code Structure: Agent 4 Implementation

## 1. Directory Structure

```
agent4_risk_matrix/
├── __init__.py                    # Package initialization
├── main.py                        # CLI entry point and orchestrator
│
├── config/
│   ├── __init__.py
│   ├── config.py                  # Configuration management
│   ├── loader.py                  # Rules loader
│   └── rules.yaml                 # Scoring rules (YAML format)
│
├── execution/
│   ├── __init__.py
│   ├── data_extractor.py           # Data extraction from SQLite + ChromaDB
│   ├── scorer.py                   # Rule execution engine
│   ├── excel_filler.py             # Excel template filling with openpyxl
│   └── validator.py                # ISO 13485 validation
│
├── llm/
│   ├── __init__.py
│   ├── client.py                   # LM Studio client
│   ├── rule_generator.py           # LLM rule generation and optimization
│   └── anomaly_detector.py         # LLM anomaly detection
│
├── orchestrator/
│   ├── __init__.py
│   ├── graph.py                    # LangGraph workflow (optional)
│   └── loader.py                   # Rules loader with caching
│
├── templates/
│   └── Lieferantenbewertung_2025.xlsx  # Excel template
│
└── tests/
    ├── __init__.py
    ├── test_data_extractor.py
    ├── test_scorer.py
    ├── test_excel_filler.py
    ├── test_validator.py
    ├── test_llm.py
    └── test_integration.py
```

---

## 2. Module Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                        DEPENDENCY GRAPH                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  main.py                                                         │
│  ├── config.config.Config                                         │
│  ├── execution.data_extractor.DataExtractor                        │
│  ├── execution.scorer.RuleScorer                                 │
│  ├── execution.excel_filler.ExcelFiller                          │
│  ├── execution.validator.Validator                               │
│  └── llm.client.LLMClient                                        │
│                                                                   │
│  execution.data_extractor.DataExtractor                           │
│  ├── pipeline.agent2_vectorstore.storage.sqlite_store.SQLiteStore  │
│  └── pipeline.agent2_vectorstore.storage.chroma_store.ChromaStore │
│                                                                   │
│  execution.scorer.RuleScorer                                      │
│  └── config.loader.RulesLoader                                    │
│                                                                   │
│  execution.excel_filler.ExcelFiller                              │
│  └── openpyxl.Workbook                                            │
│                                                                   │
│  llm.client.LLMClient                                             │
│  ├── requests.Session                                             │
│  └── config.config.Config                                         │
│                                                                   │
│  llm.rule_generator.RuleGenerator                                  │
│  └── llm.client.LLMClient                                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Design Patterns

### 3.1 Used Patterns

| Pattern | Usage | Example |
|---------|-------|---------|
| **Singleton** | Configuration management | `Config()` |
| **Factory** | Object creation | `DataExtractor(config)` |
| **Strategy** | Scoring algorithms | `RuleScorer` |
| **Template Method** | Excel filling | `ExcelFiller._fill_*()` |
| **Decorator** | Validation | `Validator` |
| **Observer** | Event handling | Audit logging |

### 3.2 Configuration Pattern

**Centralized Configuration:**
```python
# config/config.py
from dataclasses import dataclass
from pipeline.config import config as pipeline_config

@dataclass
class Config:
    # Database paths
    database_path: str = pipeline_config.DATABASE_PATH
    chroma_path: str = pipeline_config.CHROMA_PATH
    
    # LM Studio
    lm_studio_url: str = pipeline_config.LM_STUDIO_URL
    lm_studio_model: str = pipeline_config.LM_STUDIO_MODEL
    lm_studio_timeout: int = 120
    lm_studio_max_retries: int = 3
    
    # Template
    template_path: str = pipeline_config.TEMPLATE_PATH
    output_dir: str = pipeline_config.OUTPUT_DIR
    
    # Agent 4 settings
    rules_path: str = "agent4_risk_matrix/config/rules.yaml"
    audit_log_path: str = "logs/agent4_audit.log"
    use_llm: bool = True
    use_llm_optimization: bool = True
    human_approval_required: bool = True
    
    # Performance
    batch_size: int = 50
    max_suppliers: int = 200
```

---

## 4. Configuration Management

### 4.1 Config Class

**Purpose:** Centralized configuration for Agent 4

**Features:**
- Inherits from pipeline config
- Adds Agent 4 specific settings
- Type hints for all values
- Default values for optional settings
- Environment variable support

**Usage:**
```python
from agent4_risk_matrix.config.config import Config

config = Config()
print(config.database_path)
print(config.lm_studio_url)
```

### 4.2 Rules Loader

**Purpose:** Load and validate scoring rules from YAML file

**Features:**
- Loads rules from YAML file
- Validates rule structure
- Provides default rules if file not found
- Caches loaded rules

**Usage:**
```python
from agent4_risk_matrix.config.loader import RulesLoader

loader = RulesLoader(config)
rules = loader.get_rules()
```

---

## 5. Error Handling

### 5.1 Custom Exceptions

```python
# In agent4_risk_matrix/__init__.py

class Agent4Error(Exception):
    """Base exception for Agent 4"""
    pass

class ValidationError(Agent4Error):
    """Validation failed"""
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

class ApprovalError(Agent4Error):
    """Human approval required"""
    pass

class RuleGenerationError(Agent4Error):
    """LLM rule generation failed"""
    pass

class DataExtractionError(Agent4Error):
    """Data extraction failed"""
    pass
```

### 5.2 Error Handling in Components

**Data Extractor:**
```python
# In execution/data_extractor.py

def extract(self, supplier_id: str = None) -> dict:
    try:
        # Extract data
        data = self._extract_data(supplier_id)
        
        # Transform data
        transformed = self._transform_data(data)
        
        return transformed
        
    except Exception as e:
        raise DataExtractionError(f"Failed to extract data: {e}") from e
```

**Rule Scorer:**
```python
# In execution/scorer.py

def score(self, data: dict) -> dict:
    try:
        # Validate input
        if not data or 'abc_bew' not in data:
            raise ValidationError("Invalid input data")
        
        # Score suppliers
        results = self._score_all_suppliers(data)
        
        return results
        
    except Exception as e:
        raise Agent4Error(f"Scoring failed: {e}") from e
```

---

## 6. Logging

### 6.1 Logging Configuration

```python
# In agent4_risk_matrix/__init__.py

import logging
from logging.handlers import RotatingFileHandler

# Configure logger
logger = logging.getLogger('agent4')
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_format)

# File handler
file_handler = RotatingFileHandler(
    'logs/agent4.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.DEBUG)
file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)

# Add handlers
logger.addHandler(console_handler)
logger.addHandler(file_handler)
```

### 6.2 Logging in Components

**Main Orchestrator:**
```python
# In main.py

def generate(self, supplier_id: str = None) -> str:
    request_id = uuid.uuid4().hex
    logger.info(f"Request {request_id}: Starting risk matrix generation")
    
    try:
        # ... processing ...
        
        logger.info(f"Request {request_id}: Risk matrix generation complete")
        return output_path
        
    except Exception as e:
        logger.error(f"Request {request_id}: Failed - {e}")
        raise
```

**Validator:**
```python
# In execution/validator.py

def validate(self, results: dict, output_path: str) -> bool:
    logger.info("Starting validation")
    
    try:
        # ... validation ...
        
        logger.info("Validation passed")
        return True
        
    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
        raise
```

---

## 7. Testing Structure

### 7.1 Test Organization

```
tests/
├── __init__.py
├── conftest.py                  # Pytest fixtures
├── test_data_extractor.py        # Data extraction tests
├── test_scorer.py                # Scoring tests
├── test_excel_filler.py          # Excel filling tests
├── test_validator.py             # Validation tests
├── test_llm.py                   # LLM integration tests
└── test_integration.py           # End-to-end tests
```

### 7.2 Test Fixtures

```python
# In tests/conftest.py

import pytest
from agent4_risk_matrix.config.config import Config
from agent4_risk_matrix.execution.data_extractor import DataExtractor
from agent4_risk_matrix.execution.scorer import RuleScorer

@pytest.fixture
def config():
    return Config()

@pytest.fixture
def data_extractor(config):
    return DataExtractor(config)

@pytest.fixture
def rule_scorer(config):
    return RuleScorer(config)

@pytest.fixture
def sample_supplier_data():
    return {
        'suppliers': [
            {
                'id': 'SUP-001',
                'legal_name': 'Test Supplier',
                'quality_score': 95,
                'delivery_score': 85,
                'service_score': 90
            }
        ]
    }
```

### 7.3 Example Tests

**Data Extractor Test:**
```python
# In tests/test_data_extractor.py

def test_extract_single_supplier(data_extractor, sample_supplier_data):
    # Mock SQLite store
    mock_sqlite = MagicMock()
    mock_sqlite.get_supplier.return_value = sample_supplier_data['suppliers']
    data_extractor.sqlite_store = mock_sqlite
    
    # Test extraction
    result = data_extractor.extract('SUP-001')
    
    # Assertions
    assert 'abc_bew' in result
    assert len(result['abc_bew']) == 1
    assert result['abc_bew'][0]['legal_name'] == 'Test Supplier'
```

**Scorer Test:**
```python
# In tests/test_scorer.py

def test_score_supplier(rule_scorer):
    supplier_data = {
        'supplier_id': 'SUP-001',
        'quality_score': 95,
        'delivery_score': 85,
        'service_score': 90
    }
    
    result = rule_scorer._score_supplier(supplier_data)
    
    # Assertions
    assert 'scores' in result
    assert 'weighted_score' in result
    assert 'result_class' in result
    assert result['result_class'] in ['A', 'B', 'C']
```

---

## 8. Performance Considerations

### 8.1 Caching

**Rules Caching:**
```python
# In config/loader.py

class RulesLoader:
    def __init__(self, config: Config):
        self.config = config
        self._rules = None
        self._last_load_time = None
    
    def get_rules(self) -> dict:
        # Check if rules need to be reloaded
        if self._rules is None or self._should_reload():
            self._rules = self._load_rules()
            self._last_load_time = datetime.now()
        
        return self._rules
    
    def _should_reload(self) -> bool:
        # Reload if file has changed
        file_mtime = os.path.getmtime(self.config.rules_path)
        last_load = self._last_load_time.timestamp() if self._last_load_time else 0
        return file_mtime > last_load
```

### 8.2 Batch Processing

**Supplier Batch Processing:**
```python
# In execution/data_extractor.py

def extract(self, supplier_id: str = None) -> dict:
    if supplier_id:
        # Single supplier
        return self._extract_single(supplier_id)
    else:
        # All suppliers - process in batches
        return self._extract_all()

def _extract_all(self) -> dict:
    """Extract all suppliers in batches"""
    all_data = {
        'abc_bew': [],
        'zert_status': [],
        'krit_lieferante': [],
        'metadata': {}
    }
    
    # Get all supplier IDs
    supplier_ids = self.sqlite_store.get_all_supplier_ids()
    
    # Process in batches
    for i in range(0, len(supplier_ids), self.config.batch_size):
        batch_ids = supplier_ids[i:i + self.config.batch_size]
        batch_data = self._extract_batch(batch_ids)
        
        # Merge batch data
        all_data['abc_bew'].extend(batch_data['abc_bew'])
        all_data['zert_status'].extend(batch_data['zert_status'])
        all_data['krit_lieferante'].extend(batch_data['krit_lieferante'])
    
    all_data['metadata'] = {
        'timestamp': datetime.now().isoformat(),
        'supplier_count': len(supplier_ids)
    }
    
    return all_data
```

---

## 9. Security Considerations

### 9.1 Input Validation

**Supplier ID Validation:**
```python
# In main.py

def _validate_supplier_id(self, supplier_id: str) -> bool:
    """Validate supplier ID format"""
    # Check format: SUP-XXX where XXX is alphanumeric
    pattern = r'^SUP-[A-Za-z0-9]+$'
    return re.match(pattern, supplier_id) is not None
```

**Data Validation:**
```python
# In execution/validator.py

def _validate_data_completeness(self, results: dict) -> bool:
    """Check that all required data is present"""
    required_fields = ['Lieferant', '1_Produktqualität', '2_Reklamation', 
                      '3_Liefertreue', '4_Termine', '5_Service', '6_Preis']
    
    for entry in results['abc_bew']:
        for field in required_fields:
            if field not in entry:
                return False
    
    return True
```

### 9.2 File Handling

**Template File Validation:**
```python
# In execution/excel_filler.py

def __init__(self, config: Config):
    self.config = config
    self.template_path = config.template_path
    
    # Validate template file
    self._validate_template()
    
    # Identify formula cells
    self.formula_cells = self._identify_formula_cells()

def _validate_template(self):
    """Validate that template file exists and is valid"""
    if not os.path.exists(self.template_path):
        raise FileNotFoundError(f"Template file not found: {self.template_path}")
    
    try:
        workbook = openpyxl.load_workbook(self.template_path, read_only=True)
        
        # Check required sheets
        required_sheets = ['ABC-Bew', 'Zert-Satus', 'krit Lieferante', 'Versionsverw']
        for sheet in required_sheets:
            if sheet not in workbook.sheetnames:
                raise ValueError(f"Missing required sheet: {sheet}")
        
    except Exception as e:
        raise ValueError(f"Invalid template file: {e}")
```

---

## 10. Summary

This code structure provides:
- **Clear organization** - Modular design with separation of concerns
- **Maintainability** - Well-documented, tested code
- **Extensibility** - Easy to add new features
- **Robustness** - Comprehensive error handling and logging
- **Performance** - Caching and batch processing
- **Security** - Input validation and file handling
- **Compliance** - Meets ISO 13485 requirements

**Next Steps:**
1. Review [04_DATA_FLOW.md](./04_DATA_FLOW.md) for data movement details
2. Review [06_FILE_EXPLANATIONS.md](./06_FILE_EXPLANATIONS.md) for detailed file breakdown
3. Review [07_FLOW_DIAGRAM.md](./07_FLOW_DIAGRAM.md) for visual workflow

---

*Document Version: 1.0.0 | Last Updated: November 2024 | Author: AI Assistant*
