# **Agent 4: Implementation Details**

---

## **Document Information**
- **Version**: 1.0
- **Author**: Vibe Code (Mistral AI)
- **Date**: 2025
- **Purpose**: Complete implementation details for all Python files in Agent 4
- **Focus**: Code structure, classes, methods, and implementation patterns

---

## **Table of Contents**
1. [Executive Summary](#executive-summary)
2. [File Structure Recap](#file-structure-recap)
3. [Configuration Files](#configuration-files)
4. [Data Layer Implementation](#data-layer-implementation)
5. [Execution Layer Implementation](#execution-layer-implementation)
6. [LLM Layer Implementation](#llm-layer-implementation)
7. [Orchestration Layer Implementation](#orchestration-layer-implementation)
8. [Main Entry Point Implementation](#main-entry-point-implementation)
9. [Error Handling and Logging](#error-handling-and-logging)
10. [Testing Implementation](#testing-implementation)

---

## **Executive Summary**

This document provides the **complete implementation details** for Agent 4, including:
- All Python files and their contents
- Class definitions and methods
- Key implementation patterns
- Integration points with existing pipeline

**Note**: This document contains the **pre-search implementation** using **openpyxl only** (no Jinja2/xlsxtpl).

---

## **File Structure Recap**

```
pipeline/agent4_risk_matrix/
├── __init__.py                    # Package initialization
├── main.py                        # CLI entry point
│
├── config/
│   ├── __init__.py                # Configuration loader
│   ├── rules.yaml                 # Scoring rules
│   └── prompts.yaml               # LLM prompts
│
├── data/
│   ├── __init__.py
│   ├── models.py                  # Data models (Pydantic)
│   └── extractor.py               # Data extraction
│
├── execution/
│   ├── __init__.py
│   ├── scorer.py                  # Scoring engine
│   ├── excel_filler.py            # Excel filling (openpyxl)
│   └── validator.py               # Validation
│
├── llm/
│   ├── __init__.py
│   ├── client.py                  # LLM client
│   ├── rule_generator.py          # Rule generation
│   └── anomaly_detector.py        # Anomaly detection
│
├── orchestrator/
│   ├── __init__.py
│   ├── workflow.py                # Main workflow
│   └── state.py                   # State management
│
├── templates/
│   └── Lieferantenbewertung_2025.xlsx
│
├── outputs/
│   └── (generated files)
│
└── tests/
    ├── __init__.py
    ├── test_scorer.py
    ├── test_excel_filler.py
    └── test_validator.py
```

---

## **Configuration Files**

### **1. `config/__init__.py`**

**Complete Implementation**:

```python
"""
Configuration management for Agent 4: Supplier Risk Matrix Autofill System.

This module provides central configuration for Agent 4, inheriting from
the existing pipeline configuration where possible.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import yaml
import logging
import os

logger = logging.getLogger(__name__)


class Config:
    """
    Central configuration class for Agent 4.
    
    Inherits database paths and LLM settings from the existing pipeline,
    while providing Agent 4-specific configuration.
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize configuration.
        
        Args:
            base_dir: Base directory for Agent 4 (defaults to this file's parent.parent)
        """
        # Determine base directory
        if base_dir is None:
            self.base_dir = Path(__file__).parent.parent
        else:
            self.base_dir = base_dir
        
        # Agent 4 specific paths
        self.template_path = self.base_dir / 'templates' / 'Lieferantenbewertung_2025.xlsx'
        self.output_dir = self.base_dir / 'outputs'
        self.rules_yaml_path = self.base_dir / 'config' / 'rules.yaml'
        self.prompts_yaml_path = self.base_dir / 'config' / 'prompts.yaml'
        
        # Load from existing pipeline
        self._load_pipeline_config()
        
        # Validate paths
        self._validate_paths()
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Agent 4 configuration initialized at {self.base_dir}")
    
    def _load_pipeline_config(self):
        """Load configuration from existing pipeline."""
        try:
            # Try to import pipeline config
            from pipeline.config import Config as PipelineConfig
            pipeline_config = PipelineConfig()
            
            # Database paths
            self.sqlite_path = Path(pipeline_config.SQLITE_DB_PATH)
            self.chroma_db_path = Path(pipeline_config.CHROMA_DB_PATH)
            
            # LLM settings
            self.llm_base_url = pipeline_config.LM_STUDIO_BASE_URL
            self.llm_model = pipeline_config.LM_STUDIO_MODEL
            
            logger.debug("Successfully loaded pipeline configuration")
            
        except ImportError as e:
            logger.warning(f"Could not load pipeline config: {e}. Using defaults.")
            # Fallback to defaults
            self.sqlite_path = Path(os.getenv('SQLITE_DB_PATH', '/workspace/pipeline/data/sqlite_store.db'))
            self.chroma_db_path = Path(os.getenv('CHROMA_DB_PATH', '/workspace/pipeline/data/chroma_db'))
            self.llm_base_url = os.getenv('LM_STUDIO_BASE_URL', 'http://localhost:1234/v1')
            self.llm_model = os.getenv('LM_STUDIO_MODEL', 'mistralai/mistral-medium-latest')
        
        except Exception as e:
            logger.error(f"Error loading pipeline config: {e}")
            raise
    
    def _validate_paths(self):
        """Validate that required paths exist."""
        # Check template exists
        if not self.template_path.exists():
            raise FileNotFoundError(
                f"Template file not found at {self.template_path}. "
                "Please ensure the template is in the correct location."
            )
        
        # Check rules file exists
        if not self.rules_yaml_path.exists():
            raise FileNotFoundError(
                f"Rules file not found at {self.rules_yaml_path}. "
                "Please create rules.yaml first."
            )
        
        # Check SQLite database exists
        if not self.sqlite_path.exists():
            raise FileNotFoundError(
                f"SQLite database not found at {self.sqlite_path}. "
                "Please ensure Agent 2 has been run first to create the database."
            )
        
        logger.debug("All required paths validated")
    
    def load_rules(self) -> Dict[str, Any]:
        """
        Load scoring rules from YAML file.
        
        Returns:
            Dictionary containing all scoring rules
            
        Raises:
            FileNotFoundError: If rules file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        try:
            with open(self.rules_yaml_path, 'r', encoding='utf-8') as f:
                rules = yaml.safe_load(f)
            
            # Validate rules structure
            self._validate_rules(rules)
            
            logger.debug(f"Loaded rules from {self.rules_yaml_path}")
            return rules
            
        except FileNotFoundError:
            logger.error(f"Rules file not found: {self.rules_yaml_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing rules YAML: {str(e)}")
            raise
    
    def _validate_rules(self, rules: Dict[str, Any]):
        """Validate rules structure."""
        required_keys = ['version', 'scoring_system', 'criteria']
        for key in required_keys:
            if key not in rules:
                raise ValueError(f"Missing required key in rules: {key}")
        
        # Validate criteria
        if not rules['criteria'] or not isinstance(rules['criteria'], dict):
            raise ValueError("Rules must contain 'criteria' dictionary")
        
        for criterion_name, criterion_config in rules['criteria'].items():
            required_criterion_keys = ['weight', 'description', 'calculation']
            for key in required_criterion_keys:
                if key not in criterion_config:
                    raise ValueError(f"Missing required key '{key}' in criterion '{criterion_name}'")
    
    def load_prompts(self) -> Dict[str, Any]:
        """
        Load LLM prompts from YAML file.
        
        Returns:
            Dictionary containing all LLM prompts
        """
        try:
            with open(self.prompts_yaml_path, 'r', encoding='utf-8') as f:
                prompts = yaml.safe_load(f)
            
            logger.debug(f"Loaded prompts from {self.prompts_yaml_path}")
            return prompts
            
        except FileNotFoundError:
            logger.error(f"Prompts file not found: {self.prompts_yaml_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing prompts YAML: {str(e)}")
            raise
    
    def get_output_path(self, supplier_id: Optional[str] = None) -> Path:
        """
        Generate output path for a specific supplier or all suppliers.
        
        Args:
            supplier_id: Optional supplier ID (if None, generates timestamp-based name)
            
        Returns:
            Path to output file
        """
        from datetime import datetime
        
        if supplier_id:
            filename = f"risk_matrix_{supplier_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        else:
            filename = f"risk_matrix_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return self.output_dir / filename


# Singleton instance
config = Config()
```

---

### **2. `config/rules.yaml`**

**Complete Implementation** (see previous document for full content):

```yaml
# =============================================================================
# Agent 4: Supplier Risk Matrix - Scoring Rules
# =============================================================================

version: "2.0"
last_updated: "2025-01-01"
changelog: "Initial version with full scoring criteria"

# -----------------------------------------------------------------------------
# SCORING SYSTEM CONFIGURATION
# -----------------------------------------------------------------------------
scoring_system: "ABC"
total_weight: 8

result_classes:
  A: {min: 0, max: 1.5}
  B: {min: 1.51, max: 2.5}
  C: {min: 2.51, max: 3.0}

# -----------------------------------------------------------------------------
# SCORING CRITERIA
# -----------------------------------------------------------------------------
criteria:
  produktqualitaet:
    weight: 2
    description: "Product quality based on audit scores and certificate types"
    data_source: ["audit_findings", "certificate_register"]
    metric: "quality_score"
    calculation:
      type: "weighted_average"
      components:
        - source: "audit_findings"
          field: "score"
          weight: 0.7
          normalization:
            type: "linear"
            min: 0
            max: 100
            target_min: 1
            target_max: 3
        - source: "certificate_register"
          field: "certificate_type"
          weight: 0.3
          mapping:
            "ISO 13485": 1.0
            "ISO 9001": 1.5
            "Other": 2.5
            "None": 3.0
    thresholds:
      "1": ">= 95"
      "2": ">= 85"
      "3": "< 85"

  reklamation:
    weight: 2
    description: "Complaint rate based on number and severity of complaints"
    data_source: ["purchase_history", "audit_findings"]
    metric: "complaint_rate"
    calculation:
      type: "formula"
      formula: "(total_complaints * severity_factor) / total_orders"
      variables:
        total_complaints:
          source: "audit_findings"
          field: "complaint_count"
          aggregation: "sum"
        severity_factor:
          source: "audit_findings"
          field: "severity"
          mapping:
            "Low": 1.0
            "Medium": 2.0
            "High": 3.0
        total_orders:
          source: "purchase_history"
          field: "order_count"
          aggregation: "sum"
      normalization:
        type: "inverse"
        min: 0
        max: 0.1
        target_min: 3
        target_max: 1
    thresholds:
      "1": "<= 0.01"
      "2": "<= 0.05"
      "3": "> 0.05"

  liefertreue:
    weight: 1
    description: "Delivery reliability based on on-time delivery rate"
    data_source: ["purchase_history"]
    metric: "on_time_delivery_rate"
    calculation:
      type: "formula"
      formula: "on_time_deliveries / total_deliveries"
      variables:
        on_time_deliveries:
          source: "purchase_history"
          field: "on_time"
          aggregation: "sum"
        total_deliveries:
          source: "purchase_history"
          field: "delivery_count"
          aggregation: "sum"
      normalization:
        type: "linear"
        min: 0
        max: 1
        target_min: 3
        target_max: 1
    thresholds:
      "1": ">= 0.95"
      "2": ">= 0.90"
      "3": "< 0.90"

  preise:
    weight: 1
    description: "Price competitiveness based on price variance"
    data_source: ["purchase_history"]
    metric: "price_variance"
    calculation:
      type: "statistical"
      method: "coefficient_of_variation"
      field: "unit_price"
      normalization:
        type: "linear"
        min: 0
        max: 0.2
        target_min: 1
        target_max: 3
    thresholds:
      "1": "<= 0.05"
      "2": "<= 0.10"
      "3": "> 0.10"

  service:
    weight: 1
    description: "Service quality based on response time and support"
    data_source: ["audit_findings", "purchase_history"]
    metric: "service_score"
    calculation:
      type: "weighted_average"
      components:
        - source: "audit_findings"
          field: "service_rating"
          weight: 0.6
          normalization:
            type: "linear"
            min: 1
            max: 5
            target_min: 3
            target_max: 1
        - source: "purchase_history"
          field: "response_time_days"
          weight: 0.4
          normalization:
            type: "inverse"
            min: 0
            max: 14
            target_min: 3
            target_max: 1
    thresholds:
      "1": ">= 4.5"
      "2": ">= 3.5"
      "3": "< 3.5"

  entwicklungsfaehigkeit:
    weight: 1
    description: "Development capability based on innovation and improvement"
    data_source: ["audit_findings"]
    metric: "development_score"
    calculation:
      type: "weighted_average"
      components:
        - source: "audit_findings"
          field: "innovation_score"
          weight: 0.5
        - source: "audit_findings"
          field: "improvement_rate"
          weight: 0.5
    thresholds:
      "1": ">= 90"
      "2": ">= 75"
      "3": "< 75"

# -----------------------------------------------------------------------------
# ANOMALY DETECTION RULES
# -----------------------------------------------------------------------------
anomaly_detection:
  expiring_certificates:
    enabled: true
    threshold_days: 90
    severity: "High"
    
  high_risk_suppliers:
    enabled: true
    threshold_score: 2.5
    severity: "Critical"
    
  consecutive_delays:
    enabled: true
    threshold_count: 3
    severity: "High"
    
  price_increase:
    enabled: true
    threshold_percent: 15
    severity: "Medium"

# -----------------------------------------------------------------------------
# CRITICAL SUPPLIER CRITERIA
# -----------------------------------------------------------------------------
critical_supplier_criteria:
  - or:
      - risk_score: ">= 2.5"
      - certificate_expiry: "< 30 days"
      - consecutive_delays: ">= 3"
      - complaint_rate: "> 0.1"

# -----------------------------------------------------------------------------
# VALIDATION RULES
# -----------------------------------------------------------------------------
validation:
  required_fields:
    - supplier_id
    - legal_name
    - certificate_type
    - last_audit_date
    
  data_quality:
    min_completeness: 0.95
    
  audit_trail:
    enabled: true
    log_all_changes: true
    require_human_approval: true

# -----------------------------------------------------------------------------
# EXCEL MAPPINGS
# -----------------------------------------------------------------------------
excel_mappings:
  abc_bew:
    sheet_name: "ABC-Bew"
    start_row: 2
    columns:
      A: "supplier_id"
      B: "produktqualitaet_score"
      C: "reklamation_score"
      D: "liefertreue_score"
      E: "preise_score"
      F: "service_score"
      G: "entwicklungsfaehigkeit_score"
      H: "weighted_score"  # Formula column - DO NOT WRITE
      I: "result_class"
    
  zert_status:
    sheet_name: "Zert-Satus"
    start_row: 2
    columns:
      A: "supplier_id"
      B: "legal_name"
      C: "certificate_type"
      D: "certificate_number"
      E: "expiry_date"
    
  krit_lieferante:
    sheet_name: "krit Lieferante"
    start_row: 2
    columns:
      A: "supplier_id"
      B: "legal_name"
      C: "risk_score"
      D: "reason"
      E: "mitigation"
      F: "responsible"
      G: "due_date"
      H: "status"
      I: "notes"
    
  versionsverw:
    sheet_name: "Versionsverw"
    start_row: 2
    columns:
      A: "version"
      B: "date"
      C: "author"
      D: "changes"
      E: "approval"
```

---

## **Due to the length of this document, I'll continue with the remaining implementation files in a follow-up response. Would you like me to:**

1. **Continue with the remaining files** (data models, extractor, scorer, excel_filler, validator, LLM files, orchestrator, main.py)
2. **Create the PDF versions** of all documents so far
3. **Focus on a specific subset** of files you're most interested in

Please let me know how you'd like to proceed!

---

*Document Version: 1.0 | Part 1 of 2 | Author: Vibe Code (Mistral AI)*
