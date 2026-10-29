# **Agent 4: Pre-Search Plan - OpenPyXL Only Implementation**

---

## **Document Information**
- **Version**: 1.0
- **Author**: Vibe Code (Mistral AI)
- **Date**: 2025
- **Purpose**: Detailed implementation plan using **openpyxl only** (no Jinja2) for Excel manipulation
- **Approach**: Pure Python with direct cell manipulation
- **Status**: Pre-search plan (before discovering xlsxtpl)

---

## **Table of Contents**

---

## **Executive Summary**

This document describes the **pre-search implementation plan** for **Agent 4: Supplier Risk Matrix Autofill System** using **only `openpyxl`** for Excel manipulation.

### **Key Characteristics**
- **No Template Engine**: Direct cell-by-cell manipulation using `openpyxl`
- **No External Dependencies**: Only Python libraries (openpyxl, pandas, pyyaml, etc.)
- **Deterministic**: Same input produces same output
- **Offline**: No internet or external services required
- **ISO 13485 Compliant**: Human approval and audit trails

---

## **System Architecture**

### **High-Level Design**

The system follows a **layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────┐
│                         AGENT 4 ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    ORCHESTRATION LAYER                         │ │
│  │  (main.py + orchestrator/)                                      │ │
│  │  - CLI entry point                                              │ │
│  │  - Workflow coordination                                         │ │
│  │  - Error handling                                                │ │
│  │  - Logging & audit trail                                         │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      EXECUTION LAYER                             │ │
│  │  (data/ + execution/)                                           │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐   │ │
│  │  │ Data        │  │ Scorer       │  │ ExcelFiller        │   │ │
│  │  │ Extractor   │  │              │  │                    │   │ │
│  │  └─────────────┘  └─────────────┘  └───────────────────┘   │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │ Validator                                                     │ │ │
│  │  └─────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                     INTELLIGENCE LAYER                          │ │
│  │  (llm/)                                                         │ │
│  │  ┌─────────────┐  ┌───────────────────┐  ┌─────────────────┐ │ │
│  │  │ LLM         │  │ RuleGenerator      │  │ AnomalyDetector  │ │ │
│  │  │ Client      │  │                    │  │                  │ │ │
│  │  └─────────────┘  └───────────────────┘  └─────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      CONFIGURATION                              │ │
│  │  (config/)                                                      │ │
│  │  - rules.yaml (scoring rules)                                   │ │
│  │  - prompts.yaml (LLM prompts)                                   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      DATA SOURCES                               │ │
│  │  - SQLite (from Agent 2)                                       │ │
│  │  - ChromaDB (from Agent 2)                                      │ │
│  │  - LM Studio (local LLM)                                       │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## **Code Structure**

### **Directory Layout**

```
pipeline/
├── agent4_risk_matrix/
│   ├── __init__.py                    # Package initialization & exports
│   │
│   ├── main.py                        # CLI entry point & main orchestrator
│   │
│   ├── config/
│   │   ├── __init__.py                # Config loader
│   │   ├── rules.yaml                 # Scoring rules (SINGLE SOURCE OF TRUTH)
│   │   └── prompts.yaml               # LLM prompts
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── models.py                  # Pydantic data models
│   │   └── extractor.py               # Data extraction from SQLite + ChromaDB
│   │
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── scorer.py                  # Rule-based scoring engine
│   │   ├── excel_filler.py            # Excel filling using openpyxl (DIRECT CELL MANIPULATION)
│   │   └── validator.py               # ISO 13485 validation
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py                  # LLM client (LM Studio integration)
│   │   ├── rule_generator.py          # LLM generates/optimizes rules
│   │   └── anomaly_detector.py        # LLM detects anomalies in data
│   │
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── workflow.py                # Main workflow logic
│   │   └── state.py                   # State management
│   │
│   ├── templates/
│   │   └── Lieferantenbewertung_2025.xlsx  # Original template (UNMODIFIED)
│   │
│   ├── outputs/
│   │   └── risk_matrix_*.xlsx        # Generated outputs
│   │
│   └── tests/
│       ├── __init__.py
│       ├── test_scorer.py
│       ├── test_excel_filler.py
│       └── test_validator.py
│
└── ... (existing pipeline)
```

---

## **Data Flow**

### **End-to-End Process**

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   USER INPUT         │────▶│   DATA EXTRACTION     │────▶│   DATA AGGREGATION   │
│  - CLI command       │     │  - SQLite queries     │     │  - Calculate metrics  │
│  - API call          │     │  - ChromaDB queries   │     │  - Build data models  │
│  - Supplier ID(s)    │     │  - Data cleaning      │     │  - AggregatedSupplier │
└─────────────────────┘     └─────────────────────┘     │    Data objects      │
                                                          └──────────┬──────────┘
                                                             │
                                                             ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   RULES LOADING      │◀────│   (OPTIONAL) LLM      │     │   SCORING             │
│  - rules.yaml        │     │   ANALYSIS           │     │  - Apply rules to     │
│  - Validation        │     │  - RuleGenerator     │     │    each supplier      │
│  - Initialize scorer  │     │  - AnomalyDetector    │     │  - Calculate scores   │
└─────────────────────┘     │  - Data insights      │     │  - Result classes    │
                             └─────────────────────┘     └──────────┬──────────┘
                                                                      │
                                                                      ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   VALIDATION         │◀────│   HUMAN APPROVAL     │◀────│   EXCEL FILLING       │
│  - Data completeness │     │  - ISO 13485 §7.4.1   │     │  - Load template      │
│  - Score ranges      │     │  - Review results     │     │  - Write cells        │
│  - Compliance checks │     │  - Approve/reject    │     │  - Preserve formulas  │
└─────────────────────┘     └─────────────────────┘     │  - Save output        │
                                                           └──────────┬──────────┘
                                                                          │
                                                                          ▼
                                                               ┌─────────────────────┐
                                                               │   OUTPUT              │
                                                               │  - Filled Excel file │
                                                               │  - Logs              │
                                                               │  - Audit trail       │
                                                               └─────────────────────┘
```

---

## **File-by-File Implementation Details**

### **1. Package Initialization (`__init__.py`)**

**Purpose**: Define package exports and version info.

```python
"""
Agent 4: Supplier Risk Matrix Autofill System
Automatically fills Lieferantenbewertung_2025.xlsx with supplier data.
"""

from .data.models import (
    SupplierData, AggregatedSupplierData, ScoringResult, 
    CertificateModel, AuditFindingModel, PurchaseHistoryModel
)
from .execution.scorer import RuleScorer
from .execution.excel_filler import ExcelFiller
from .execution.validator import RiskMatrixValidator
from .data.extractor import DataExtractor
from .llm.client import LLMClient
from .llm.rule_generator import RuleGenerator
from .llm.anomaly_detector import AnomalyDetector
from .orchestrator.workflow import RiskMatrixWorkflow
from .config import Config

__version__ = "1.0.0"
__all__ = [
    "SupplierData", "AggregatedSupplierData", "ScoringResult",
    "CertificateModel", "AuditFindingModel", "PurchaseHistoryModel",
    "RuleScorer", "ExcelFiller", "RiskMatrixValidator",
    "DataExtractor", "LLMClient", "RuleGenerator", "AnomalyDetector",
    "RiskMatrixWorkflow", "Config"
]
```

---

### **2. Main Entry Point (`main.py`)**

**Purpose**: CLI interface and workflow orchestrator.

**Key Features**:
- Argument parsing for different operations
- Workflow execution
- Error handling and logging
- Output management

```python
#!/usr/bin/env python3
"""
Agent 4: Supplier Risk Matrix Autofill System

Usage:
    python -m agent4_risk_matrix.main --supplier-id SUP123
    python -m agent4_risk_matrix.main --all-suppliers
    python -m agent4_risk_matrix.main --generate-rules
"""

import argparse
import logging
from pathlib import Path
from datetime import datetime
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent4_risk_matrix.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Agent 4: Supplier Risk Matrix Autofill System'
    )
    parser.add_argument('--supplier-id', type=str, help='Process specific supplier')
    parser.add_argument('--all-suppliers', action='store_true', help='Process all suppliers')
    parser.add_argument('--generate-rules', action='store_true', help='Generate rules using LLM')
    parser.add_argument('--output-dir', type=str, default=None, help='Custom output directory')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize workflow
    workflow = RiskMatrixWorkflow()
    
    if args.generate_rules:
        # Generate/optimize rules using LLM
        new_rules = workflow.generate_rules()
        logger.info(f"Generated new rules: {new_rules}")
        
    elif args.all_suppliers:
        # Process all suppliers
        results = workflow.execute_all()
        logger.info(f"Processed {len(results)} suppliers")
        
    elif args.supplier_id:
        # Process specific supplier
        result = workflow.execute(args.supplier_id)
        logger.info(f"Processed supplier {args.supplier_id}")
        
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
```

---

### **3. Configuration (`config/__init__.py`)**

**Purpose**: Central configuration management.

**Key Features**:
- Loads from existing pipeline config
- Manages paths to rules and templates
- Provides configuration to all components

```python
"""
Configuration management for Agent 4.
Integrates with existing pipeline configuration.
"""

from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)


class Config:
    """Central configuration for Agent 4."""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        
        # Template and output paths
        self.template_path = self.base_dir / 'templates' / 'Lieferantenbewertung_2025.xlsx'
        self.output_dir = self.base_dir / 'outputs'
        self.rules_yaml_path = self.base_dir / 'config' / 'rules.yaml'
        self.prompts_yaml_path = self.base_dir / 'config' / 'prompts.yaml'
        
        # Inherit from existing pipeline
        self._load_pipeline_config()
        
        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_pipeline_config(self):
        """Load configuration from existing pipeline."""
        try:
            from pipeline.config import Config as PipelineConfig
            pipeline_config = PipelineConfig()
            self.sqlite_path = Path(pipeline_config.SQLITE_DB_PATH)
            self.chroma_db_path = Path(pipeline_config.CHROMA_DB_PATH)
            self.llm_base_url = pipeline_config.LM_STUDIO_BASE_URL
            self.llm_model = pipeline_config.LM_STUDIO_MODEL
        except ImportError as e:
            logger.warning(f"Could not load pipeline config: {e}")
            # Fallback defaults
            self.sqlite_path = Path('/workspace/pipeline/data/sqlite_store.db')
            self.chroma_db_path = Path('/workspace/pipeline/data/chroma_db')
            self.llm_base_url = 'http://localhost:1234/v1'
            self.llm_model = 'mistralai/mistral-medium-latest'
    
    def load_rules(self) -> dict:
        """Load scoring rules from YAML."""
        with open(self.rules_yaml_path, 'r') as f:
            return yaml.safe_load(f)
    
    def load_prompts(self) -> dict:
        """Load LLM prompts from YAML."""
        with open(self.prompts_yaml_path, 'r') as f:
            return yaml.safe_load(f)


# Singleton instance
config = Config()
```

---

### **4. Data Models (`data/models.py`)**

**Purpose**: Define data structures with Pydantic for validation.

**Key Models**:

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


class ResultClass(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class CertificateModel(BaseModel):
    """Certificate information."""
    certificate_type: str
    certificate_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    issuing_body: Optional[str] = None
    
    @property
    def is_expiring_soon(self, threshold_days: int = 90) -> bool:
        if not self.expiry_date:
            return False
        days_left = (self.expiry_date - date.today()).days
        return 0 <= days_left <= threshold_days


class AuditFindingModel(BaseModel):
    """Audit finding information."""
    finding_id: str
    audit_date: date
    severity: str
    category: str
    description: str
    score: Optional[float] = None
    quality_score: Optional[float] = None
    complaint_count: Optional[int] = None
    consecutive_delays: Optional[int] = None


class PurchaseHistoryModel(BaseModel):
    """Purchase history information."""
    purchase_id: str
    order_date: date
    delivery_date: Optional[date] = None
    promised_delivery_date: date
    unit_price: float
    quantity: int
    total_value: float
    on_time: bool
    delay_days: Optional[int] = None


class AggregatedSupplierData(BaseModel):
    """Aggregated data for a supplier."""
    supplier_id: str
    legal_name: str
    short_name: Optional[str] = None
    
    # Certificates
    certificate: Optional[CertificateModel] = None
    certificates: List[CertificateModel] = Field(default_factory=list)
    
    # Audit data
    audit_findings: List[AuditFindingModel] = Field(default_factory=list)
    last_audit_date: Optional[date] = None
    
    # Purchase history
    purchase_history: List[PurchaseHistoryModel] = Field(default_factory=list)
    total_orders: int = 0
    total_value: float = 0.0
    on_time_deliveries: int = 0
    delayed_deliveries: int = 0
    
    # Calculated metrics (for scoring)
    quality_score: Optional[float] = None
    complaint_rate: Optional[float] = None
    on_time_delivery_rate: Optional[float] = None
    price_variance: Optional[float] = None
    service_score: Optional[float] = None
    development_score: Optional[float] = None
    consecutive_delays: int = 0


class CriterionScore(BaseModel):
    """Score for a single criterion."""
    criterion: str
    raw_score: Optional[float] = None
    normalized_score: float
    weight: float
    weighted_score: float
    threshold: str  # "1", "2", or "3"


class ScoringResult(BaseModel):
    """Complete scoring result for a supplier."""
    supplier_id: str
    legal_name: str
    criteria_scores: Dict[str, CriterionScore]
    weighted_sum: float
    total_weight: float
    weighted_average: float
    result_class: ResultClass
    scored_at: datetime = Field(default_factory=datetime.now)
    rules_version: str
    anomalies: List[dict] = Field(default_factory=list)
    is_critical: bool = False
    critical_reason: Optional[str] = None
```

---

### **5. Data Extractor (`data/extractor.py`)**

**Purpose**: Extract and aggregate data from SQLite and ChromaDB.

**Key Methods**:
- `extract_supplier(supplier_id)`: Extract data for one supplier
- `extract_all_suppliers()`: Extract data for all suppliers
- `_get_supplier_info()`: Get basic supplier info
- `_get_certificates()`: Get certificates from database
- `_get_audit_findings()`: Get audit findings from database
- `_get_purchase_history()`: Get purchase history from database
- `_aggregate_metrics()`: Calculate all metrics

**Implementation**:

```python
import sqlite3
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging

from .models import (
    AggregatedSupplierData, CertificateModel, 
    AuditFindingModel, PurchaseHistoryModel
)
from ..config import Config

logger = logging.getLogger(__name__)


class DataExtractor:
    """Extracts and aggregates supplier data from SQLite and ChromaDB."""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.sqlite_conn = sqlite3.connect(self.config.sqlite_path)
        self.sqlite_conn.row_factory = sqlite3.Row
    
    def close(self):
        if self.sqlite_conn:
            self.sqlite_conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def extract_all_suppliers(self) -> List[AggregatedSupplierData]:
        """Extract data for all suppliers."""
        supplier_ids = self._get_all_supplier_ids()
        return [self.extract_supplier(sid) for sid in supplier_ids]
    
    def extract_supplier(self, supplier_id: str) -> AggregatedSupplierData:
        """Extract and aggregate data for a specific supplier."""
        logger.info(f"Extracting data for supplier: {supplier_id}")
        
        supplier_info = self._get_supplier_info(supplier_id)
        certificates = self._get_certificates(supplier_id)
        audit_findings = self._get_audit_findings(supplier_id)
        purchase_history = self._get_purchase_history(supplier_id)
        
        return self._aggregate_metrics(
            supplier_info, certificates, audit_findings, purchase_history
        )
    
    def _get_all_supplier_ids(self) -> List[str]:
        """Get list of all supplier IDs from database."""
        query = "SELECT DISTINCT supplier_id FROM suppliers WHERE supplier_id IS NOT NULL"
        cursor = self.sqlite_conn.cursor()
        cursor.execute(query)
        return [row['supplier_id'] for row in cursor.fetchall()]
    
    def _get_supplier_info(self, supplier_id: str) -> Dict[str, Any]:
        """Get basic supplier information."""
        query = "SELECT * FROM suppliers WHERE supplier_id = ?"
        cursor = self.sqlite_conn.cursor()
        cursor.execute(query, (supplier_id,))
        row = cursor.fetchone()
        
        if not row:
            raise ValueError(f"Supplier not found: {supplier_id}")
        return dict(row)
    
    def _get_certificates(self, supplier_id: str) -> List[CertificateModel]:
        """Get all certificates for a supplier."""
        query = """
            SELECT * FROM certificate_register 
            WHERE supplier_id = ? 
            ORDER BY issue_date DESC
        """
        cursor = self.sqlite_conn.cursor()
        cursor.execute(query, (supplier_id,))
        
        certificates = []
        for row in cursor.fetchall():
            try:
                cert = CertificateModel(
                    certificate_type=row.get('certificate_type', 'Other'),
                    certificate_number=row.get('certificate_number'),
                    issue_date=row.get('issue_date'),
                    expiry_date=row.get('expiry_date'),
                    issuing_body=row.get('issuing_body')
                )
                certificates.append(cert)
            except Exception as e:
                logger.warning(f"Error parsing certificate: {e}")
        
        return certificates
    
    def _get_audit_findings(self, supplier_id: str) -> List[AuditFindingModel]:
        """Get all audit findings for a supplier."""
        query = """
            SELECT * FROM audit_findings 
            WHERE supplier_id = ? 
            ORDER BY audit_date DESC
        """
        cursor = self.sqlite_conn.cursor()
        cursor.execute(query, (supplier_id,))
        
        findings = []
        for row in cursor.fetchall():
            try:
                finding = AuditFindingModel(
                    finding_id=row.get('finding_id'),
                    audit_date=row.get('audit_date'),
                    severity=row.get('severity'),
                    category=row.get('category'),
                    description=row.get('description'),
                    score=row.get('score'),
                    quality_score=row.get('quality_score'),
                    complaint_count=row.get('complaint_count'),
                    consecutive_delays=row.get('consecutive_delays')
                )
                findings.append(finding)
            except Exception as e:
                logger.warning(f"Error parsing audit finding: {e}")
        
        return findings
    
    def _get_purchase_history(self, supplier_id: str) -> List[PurchaseHistoryModel]:
        """Get all purchase history for a supplier."""
        query = """
            SELECT * FROM purchase_history 
            WHERE supplier_id = ? 
            ORDER BY order_date DESC
        """
        cursor = self.sqlite_conn.cursor()
        cursor.execute(query, (supplier_id,))
        
        history = []
        for row in cursor.fetchall():
            try:
                purchase = PurchaseHistoryModel(
                    purchase_id=row.get('purchase_id'),
                    order_date=row.get('order_date'),
                    delivery_date=row.get('delivery_date'),
                    promised_delivery_date=row.get('promised_delivery_date'),
                    unit_price=row.get('unit_price'),
                    quantity=row.get('quantity'),
                    total_value=row.get('total_value'),
                    on_time=bool(row.get('on_time', True)),
                    delay_days=row.get('delay_days')
                )
                history.append(purchase)
            except Exception as e:
                logger.warning(f"Error parsing purchase history: {e}")
        
        return history
    
    def _aggregate_metrics(
        self,
        supplier_info: Dict[str, Any],
        certificates: List[CertificateModel],
        audit_findings: List[AuditFindingModel],
        purchase_history: List[PurchaseHistoryModel]
    ) -> AggregatedSupplierData:
        """Calculate all metrics from raw data."""
        # Most recent certificate
        most_recent_cert = certificates[0] if certificates else None
        
        # Calculate total complaints
        total_complaints = sum(
            f.complaint_count or 0 for f in audit_findings
        )
        
        # Calculate average quality score
        quality_scores = [f.quality_score for f in audit_findings if f.quality_score is not None]
        avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else None
        
        # Calculate average service score
        service_scores = [f.service_rating for f in audit_findings if hasattr(f, 'service_rating') and f.service_rating is not None]
        avg_service_score = sum(service_scores) / len(service_scores) if service_scores else None
        
        # Calculate delivery metrics
        total_orders = len(purchase_history)
        total_value = sum(p.total_value for p in purchase_history)
        on_time_deliveries = sum(1 for p in purchase_history if p.on_time)
        delayed_deliveries = total_orders - on_time_deliveries
        on_time_delivery_rate = on_time_deliveries / total_orders if total_orders > 0 else None
        
        # Calculate price variance (coefficient of variation)
        unit_prices = [p.unit_price for p in purchase_history]
        if unit_prices:
            mean_price = sum(unit_prices) / len(unit_prices)
            variance = sum((p - mean_price) ** 2 for p in unit_prices) / len(unit_prices)
            std_dev = variance ** 0.5
            price_variance = std_dev / mean_price if mean_price > 0 else 0
        else:
            price_variance = None
        
        # Calculate complaint rate
        complaint_rate = total_complaints / total_orders if total_orders > 0 else None
        
        # Calculate consecutive delays
        consecutive_delays = 0
        if purchase_history:
            sorted_history = sorted(purchase_history, key=lambda x: x.order_date)
            for purchase in sorted_history:
                if not purchase.on_time:
                    consecutive_delays += 1
                else:
                    consecutive_delays = 0
        
        # Get last audit date
        last_audit_date = None
        if audit_findings:
            last_audit_date = max(f.audit_date for f in audit_findings)
        
        return AggregatedSupplierData(
            supplier_id=supplier_info.get('supplier_id'),
            legal_name=supplier_info.get('legal_name'),
            short_name=supplier_info.get('short_name'),
            certificate=most_recent_cert,
            certificates=certificates,
            audit_findings=audit_findings,
            last_audit_date=last_audit_date,
            purchase_history=purchase_history,
            total_orders=total_orders,
            total_value=total_value,
            on_time_deliveries=on_time_deliveries,
            delayed_deliveries=delayed_deliveries,
            quality_score=avg_quality_score,
            complaint_rate=complaint_rate,
            on_time_delivery_rate=on_time_delivery_rate,
            price_variance=price_variance,
            service_score=avg_service_score,
            development_score=None,  # Calculated from audit findings
            consecutive_delays=consecutive_delays
        )
```

---

## **To Be Continued...**

This document will continue with the remaining files:
- `execution/scorer.py` - Rule-based scoring engine
- `execution/excel_filler.py` - Excel filling with openpyxl
- `execution/validator.py` - ISO 13485 validation
- `llm/*` - LLM integration files
- `orchestrator/*` - Workflow orchestration

Would you like me to continue with these files or would you prefer to receive the complete documentation as PDFs first?

---

*Document Version: 1.0 | Part 1 of 2 | Author: Vibe Code (Mistral AI)*
