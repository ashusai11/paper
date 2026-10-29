# **Agent 4: Integration with Existing Pipeline**

---

## **Document Information**
- **Version**: 1.0
- **Author**: Vibe Code (Mistral AI)
- **Date**: 2025
- **Purpose**: Detailed integration plan between Agent 4 and existing pipeline (Agents 1-3)
- **Focus**: Database, configuration, API, and UI integration

---

## **Table of Contents**
1. [Executive Summary](#executive-summary)
2. [Existing Pipeline Overview](#existing-pipeline-overview)
3. [Agent 4 Integration Architecture](#agent-4-integration-architecture)
4. [Database Integration](#database-integration)
5. [Configuration Integration](#configuration-integration)
6. [LLM Integration](#llm-integration)
7. [API Integration](#api-integration)
8. [UI Integration](#ui-integration)
9. [Data Flow Integration](#data-flow-integration)
10. [Code Integration](#code-integration)
11. [Testing Integration](#testing-integration)
12. [Deployment Integration](#deployment-integration)

---

## **Executive Summary**

Agent 4 **does not operate in isolation** - it **integrates deeply** with the existing pipeline to:
- **Reuse** existing infrastructure (SQLite, ChromaDB, LM Studio)
- **Leverage** existing data (suppliers, audit findings, purchase history)
- **Extend** existing functionality (new API endpoints, UI pages)
- **Maintain** consistency (same configuration, same patterns)

This document details **how Agent 4 connects to and extends the existing pipeline**.

---

## **Existing Pipeline Overview**

### **Pipeline Structure**

```
pipeline/
├── config.py                  # Central configuration
├── requirements.txt           # Dependencies
├── main.py                    # Main entry point
│
├── agent1_offline_parser/     # Agent 1: Offline Parser
│   ├── parser.py              # Document parsing
│   └── ...
│
├── agent2_vectorstore/        # Agent 2: Vector Store
│   ├── storage/
│   │   └── sqlite_store.py     # SQLite database operations
│   ├── tabular/
│   │   └── registry.py         # Tabular ingestion configuration
│   └── ...
│
├── agent3_evaluator/          # Agent 3: VA26 Evaluator
│   ├── intake/
│   │   └── risk_classifier.py  # Risk classification
│   ├── rules/
│   │   └── va26.py             # VA26 rules
│   └── ...
│
├── api/                       # FastAPI backend
│   └── main.py
│
└── ui/                        # Streamlit frontend
    └── app.py
```

### **Existing Components**

| Component | Purpose | Used by Agent 4? |
|-----------|---------|------------------|
| **SQLite Database** | System of record for structured data | ✅ Yes |
| **ChromaDB** | Vector index for document search | ✅ Yes |
| **LM Studio** | Local LLM for AI capabilities | ✅ Yes |
| **config.py** | Central configuration | ✅ Yes |
| **FastAPI** | Backend API | ✅ Yes (extend) |
| **Streamlit** | Frontend UI | ✅ Yes (extend) |
| **VA26 Rules** | Medical device regulation rules | ⚠️ Reference |

### **Existing Data Tables**

Agent 4 uses data from these existing tables:

| Table | Source | Description | Used For |
|-------|--------|-------------|----------|
| `suppliers` | Agent 1/2 | Basic supplier information | Supplier details |
| `certificate_register` | Agent 1/2 | Certificate information | Certificate status |
| `audit_findings` | Agent 1/2 | Audit results | Quality scoring |
| `purchase_history` | Agent 1/2 | Purchase records | Delivery reliability, price analysis |
| `risk_matrix` | Agent 3 | Existing risk data | Reference/validation |

---

## **Agent 4 Integration Architecture**

### **High-Level Integration**

```
┌─────────────────────────────────────────────────────────────────┐
│                    INTEGRATED PIPELINE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    SHARED INFRASTRUCTURE                        │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐   │ │
│  │  │   SQLite         │  │   ChromaDB       │  │  LM Studio   │   │ │
│  │  │   Database       │  │   (Vector Index) │  │  (Local LLM) │   │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────┘   │ │
│  │                                                                 │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │                    config.py                                 │ │ │
│  │  │  - Database paths                                          │ │ │
│  │  │  - LLM settings                                             │ │ │
│  │  │  - Pipeline configuration                                   │ │ │
│  │  └─────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│              ┌───────────────────────┬───────────────────────┐     │
│              │                       │                       │     │
│              ▼                       ▼                       ▼     │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐   │
│  │  Agent 1:        │    │  Agent 2:        │    │  Agent 3:   │   │
│  │  Offline Parser  │    │  Vector Store    │    │  VA26       │   │
│  │                  │    │                  │    │  Evaluator  │   │
│  └─────────────────┘    └─────────────────┘    └─────────────┘   │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    AGENT 4: RISK MATRIX                        │ │
│  │  - Data Extractor (uses SQLite from Agent 2)                  │ │
│  │  - Rule Scorer (references VA26 rules from Agent 3)          │ │
│  │  - Excel Filler (generates output)                            │ │
│  │  - Validator (ISO 13485 compliance)                           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                       │
│              ┌───────────────────────┬───────────────────────┐     │
│              │                       │                       │     │
│              ▼                       ▼                       ▼     │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐   │
│  │  API            │    │  UI              │    │  Outputs     │   │
│  │  (FastAPI)       │    │  (Streamlit)     │    │  (Excel     │   │
│  │  - New endpoints │    │  - New pages    │    │   files)    │   │
│  └─────────────────┘    └─────────────────┘    └─────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## **Database Integration**

### **SQLite Integration**

**Agent 4 uses the same SQLite database as Agents 1-2.**

**Connection Setup**:
```python
# In agent4_risk_matrix/config/__init__.py

from pipeline.config import Config as PipelineConfig

class Config:
    def __init__(self):
        # Inherit from existing pipeline
        pipeline_config = PipelineConfig()
        self.sqlite_path = Path(pipeline_config.SQLITE_DB_PATH)
        
        # Verify database exists
        if not self.sqlite_path.exists():
            raise FileNotFoundError(
                f"SQLite database not found at {self.sqlite_path}. "
                "Please ensure Agent 2 has been run first."
            )
```

**Table Access**:
```python
# In agent4_risk_matrix/data/extractor.py

class DataExtractor:
    def __init__(self):
        self.config = Config()
        self.conn = sqlite3.connect(self.config.sqlite_path)
        
    def _get_supplier_info(self, supplier_id: str) -> dict:
        query = """
            SELECT * FROM suppliers 
            WHERE supplier_id = ?
        """
        cursor = self.conn.cursor()
        cursor.execute(query, (supplier_id,))
        return dict(cursor.fetchone())
```

### **ChromaDB Integration**

**Agent 4 can optionally use ChromaDB for semantic search.**

**Use Cases**:
- Finding similar suppliers
- Searching audit findings by context
- Retrieving relevant documents

**Implementation**:
```python
# In agent4_risk_matrix/data/extractor.py

from pipeline.agent2_vectorstore.storage.chroma_store import ChromaDBStore

class DataExtractor:
    def __init__(self):
        self.config = Config()
        self.chroma_store = ChromaDBStore(self.config.chroma_db_path)
        
    def search_similar_suppliers(self, supplier_id: str, limit: int = 5) -> list:
        """Find suppliers similar to the given one."""
        query = f"Supplier {supplier_id} characteristics"
        results = self.chroma_store.query(query, limit=limit)
        return results
```

### **Data Model Alignment**

Agent 4's data models **align with existing pipeline models**:

| Agent 4 Model | Existing Pipeline Model | Alignment |
|---------------|-------------------------|-----------|
| `CertificateModel` | `Certificate` (Agent 2) | Compatible |
| `AuditFindingModel` | `AuditFinding` (Agent 2) | Compatible |
| `PurchaseHistoryModel` | `Purchase` (Agent 2) | Compatible |
| `SupplierData` | `Supplier` (Agent 2) | Compatible |

---

## **Configuration Integration**

### **Central Configuration**

Agent 4 **inherits configuration from `pipeline/config.py`**:

```python
# pipeline/config.py (existing)

class Config:
    # Database
    SQLITE_DB_PATH = "/workspace/pipeline/data/sqlite_store.db"
    CHROMA_DB_PATH = "/workspace/pipeline/data/chroma_db"
    
    # LLM
    LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
    LM_STUDIO_MODEL = "mistralai/mistral-medium-latest"
    
    # Other settings...
```

```python
# agent4_risk_matrix/config/__init__.py (new)

from pipeline.config import Config as PipelineConfig

class Config:
    def __init__(self):
        # Inherit from pipeline config
        pipeline_config = PipelineConfig()
        
        # Database paths
        self.sqlite_path = Path(pipeline_config.SQLITE_DB_PATH)
        self.chroma_db_path = Path(pipeline_config.CHROMA_DB_PATH)
        
        # LLM settings
        self.llm_base_url = pipeline_config.LM_STUDIO_BASE_URL
        self.llm_model = pipeline_config.LM_STUDIO_MODEL
        
        # Agent 4 specific paths
        self.base_dir = Path(__file__).parent.parent
        self.template_path = self.base_dir / 'templates' / 'Lieferantenbewertung_2025.xlsx'
        self.output_dir = self.base_dir / 'outputs'
        self.rules_yaml_path = self.base_dir / 'config' / 'rules.yaml'
```

### **Environment Variables**

Agent 4 **respects the same environment variables** as the existing pipeline:

```bash
# Existing pipeline uses these:
export SQLITE_DB_PATH="/path/to/sqlite.db"
export CHROMA_DB_PATH="/path/to/chroma"
export LM_STUDIO_BASE_URL="http://localhost:1234/v1"
export LM_STUDIO_MODEL="mistralai/mistral-medium-latest"

# Agent 4 will use the same variables
```

---

## **LLM Integration**

### **Shared LLM Client**

Agent 4 **reuses the same LM Studio configuration** as the existing pipeline:

```python
# agent4_risk_matrix/llm/client.py

import httpx
from ..config import Config

class LLMClient:
    def __init__(self):
        self.config = Config()
        self.client = httpx.Client(
            base_url=self.config.llm_base_url,
            timeout=30.0
        )
        self.model = self.config.llm_model
        
    def generate(self, prompt: str, system_prompt: str = None) -> str:
        """Generate text using LM Studio."""
        payload = {
            "model": self.model,
            "messages": []
        }
        
        if system_prompt:
            payload["messages"].append({"role": "system", "content": system_prompt})
        
        payload["messages"].append({"role": "user", "content": prompt})
        
        response = self.client.post("/chat/completions", json=payload)
        return response.json()["choices"][0]["message"]["content"]
```

### **VA26 Rules Reference**

Agent 4 can **reference VA26 rules from Agent 3** for consistency:

```python
# agent4_risk_matrix/execution/scorer.py

from pipeline.agent3_evaluator.rules.va26 import VA26Rules

class RuleScorer:
    def __init__(self, rules: dict):
        self.rules = rules
        self.va26_rules = VA26Rules()  # Reference existing rules
        
    def score_supplier(self, supplier_data):
        # Use Agent 4 rules primarily
        score = self._calculate_from_rules(supplier_data)
        
        # Optionally reference VA26 for validation
        va26_class = self.va26_rules.classify_supplier(supplier_data)
        
        return {
            'score': score,
            'va26_reference': va26_class
        }
```

---

## **API Integration**

### **New API Endpoints**

Agent 4 **extends the existing FastAPI backend** with new endpoints:

```python
# pipeline/api/main.py (existing - to be extended)

from fastapi import FastAPI, HTTPException
from agent4_risk_matrix.main import generate_risk_matrix, generate_rules
from agent4_risk_matrix.config import Config

app = FastAPI()

# Existing endpoints...

# New Agent 4 endpoints
@app.post("/risk-matrix/generate")
async def generate_risk_matrix_api(supplier_id: str = None):
    """Generate risk matrix for a specific supplier."""
    try:
        result = generate_risk_matrix(supplier_id=supplier_id)
        return {
            "status": "success",
            "output_path": result['output_path'],
            "scoring_result": result['scoring_result'].dict()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/risk-matrix/generate-all")
async def generate_all_risk_matrices():
    """Generate risk matrices for all suppliers."""
    try:
        results = generate_risk_matrix(all_suppliers=True)
        return {
            "status": "success",
            "count": len(results),
            "results": [r['scoring_result'].dict() for r in results]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/risk-matrix/rules")
async def get_rules():
    """Get current scoring rules."""
    config = Config()
    rules = config.load_rules()
    return {"rules": rules}


@app.put("/risk-matrix/rules")
async def update_rules(new_rules: dict):
    """Update scoring rules (requires admin)."""
    # In production, add authentication
    config = Config()
    
    # Validate rules
    validator = RuleValidator()
    if not validator.validate_rules(new_rules):
        raise HTTPException(status_code=400, detail="Invalid rules")
    
    # Save to file
    with open(config.rules_yaml_path, 'w') as f:
        yaml.dump(new_rules, f)
    
    return {"status": "success", "message": "Rules updated"}


@app.get("/risk-matrix/history")
async def get_history(limit: int = 10):
    """Get history of generated risk matrices."""
    output_dir = Config().output_dir
    files = sorted(output_dir.glob("*.xlsx"), reverse=True)[:limit]
    
    return {
        "history": [
            {
                "filename": f.name,
                "generated_at": f.stat().st_mtime,
                "size": f.stat().st_size
            }
            for f in files
        ]
    }


@app.post("/risk-matrix/export")
async def export_risk_matrix(supplier_ids: List[str] = None):
    """Export risk matrices for specified suppliers."""
    try:
        results = []
        for supplier_id in supplier_ids:
            result = generate_risk_matrix(supplier_id=supplier_id)
            results.append(result)
        
        # Create zip file
        zip_path = Config().output_dir / f"risk_matrices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for result in results:
                zf.write(result['output_path'], result['output_path'].name)
        
        return {
            "status": "success",
            "zip_path": str(zip_path)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### **API Integration Points**

| Integration Point | Description |
|-------------------|-------------|
| **Shared FastAPI App** | All endpoints in one FastAPI app |
| **Shared Configuration** | Same config.py for all agents |
| **Shared Models** | Pydantic models can be reused |
| **Shared Dependencies** | Same requirements.txt |
| **Authentication** | Can reuse existing auth middleware |
| **Error Handling** | Consistent error responses |

---

## **UI Integration**

### **New Streamlit Pages**

Agent 4 **extends the existing Streamlit UI** with new pages:

```python
# pipeline/ui/app.py (existing - to be extended)

import streamlit as st
from agent4_risk_matrix.main import generate_risk_matrix
from agent4_risk_matrix.config import Config

# Existing pages...

# New Agent 4 pages
def risk_matrix_page():
    """Risk Matrix Generation Page."""
    st.title("📊 Supplier Risk Matrix")
    
    # Sidebar
    st.sidebar.title("Options")
    
    # Supplier selection
    supplier_id = st.selectbox(
        "Select Supplier",
        options=get_all_supplier_ids(),
        index=0
    )
    
    # Generate button
    if st.button("Generate Risk Matrix"):
        with st.spinner("Generating risk matrix..."):
            try:
                result = generate_risk_matrix(supplier_id=supplier_id)
                
                # Display results
                st.success("✅ Risk matrix generated successfully!")
                
                # Show scoring result
                st.subheader("Scoring Result")
                scoring_result = result['scoring_result']
                st.json(scoring_result.dict())
                
                # Download button
                st.download_button(
                    label="Download Excel",
                    data=open(result['output_path'], 'rb').read(),
                    file_name=result['output_path'].name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")


def risk_matrix_batch_page():
    """Batch Risk Matrix Generation Page."""
    st.title("📦 Batch Risk Matrix Generation")
    
    # Supplier selection (multi-select)
    supplier_ids = st.multiselect(
        "Select Suppliers",
        options=get_all_supplier_ids(),
        default=[]
    )
    
    # Generate all option
    all_suppliers = st.checkbox("Select All Suppliers")
    if all_suppliers:
        supplier_ids = get_all_supplier_ids()
    
    # Generate button
    if st.button(f"Generate {len(supplier_ids)} Risk Matrices"):
        if not supplier_ids:
            st.warning("Please select at least one supplier")
            return
            
        with st.spinner(f"Generating {len(supplier_ids)} risk matrices..."):
            progress_bar = st.progress(0)
            results = []
            
            for i, supplier_id in enumerate(supplier_ids):
                try:
                    result = generate_risk_matrix(supplier_id=supplier_id)
                    results.append(result)
                    progress_bar.progress((i + 1) / len(supplier_ids))
                except Exception as e:
                    st.error(f"Error processing {supplier_id}: {str(e)}")
            
            # Create zip file
            zip_path = Config().output_dir / f"risk_matrices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                for result in results:
                    zf.write(result['output_path'], result['output_path'].name)
            
            st.success(f"✅ Generated {len(results)} risk matrices!")
            
            # Download button
            st.download_button(
                label="Download All (ZIP)",
                data=open(zip_path, 'rb').read(),
                file_name=zip_path.name,
                mime="application/zip"
            )


def risk_matrix_rules_page():
    """Risk Matrix Rules Management Page."""
    st.title("⚙️ Risk Matrix Rules")
    
    config = Config()
    rules = config.load_rules()
    
    # Display current rules
    st.subheader("Current Rules")
    st.json(rules)
    
    # Edit rules (admin only)
    if st.checkbox("Edit Rules"):
        st.warning("⚠️ Editing rules requires admin privileges")
        
        new_rules_yaml = st.text_area(
            "Rules YAML",
            value=yaml.dump(rules),
            height=400
        )
        
        if st.button("Save Rules"):
            try:
                new_rules = yaml.safe_load(new_rules_yaml)
                validator = RuleValidator()
                if validator.validate_rules(new_rules):
                    with open(config.rules_yaml_path, 'w') as f:
                        f.write(new_rules_yaml)
                    st.success("✅ Rules saved successfully!")
                    st.experimental_rerun()
                else:
                    st.error("❌ Invalid rules")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")


def risk_matrix_analytics_page():
    """Risk Matrix Analytics Dashboard."""
    st.title("📈 Risk Matrix Analytics")
    
    # Generate for all suppliers
    if st.button("Analyze All Suppliers"):
        with st.spinner("Analyzing all suppliers..."):
            results = generate_risk_matrix(all_suppliers=True)
            
            # Create analytics
            analytics = create_analytics(results)
            
            # Display summary
            st.subheader("Summary")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Suppliers", len(results))
            col2.metric("Class A", sum(1 for r in results if r['scoring_result'].result_class == 'A'))
            col3.metric("Class B", sum(1 for r in results if r['scoring_result'].result_class == 'B'))
            
            # Display chart
            st.subheader("Risk Distribution")
            chart_data = {
                'Class A': sum(1 for r in results if r['scoring_result'].result_class == 'A'),
                'Class B': sum(1 for r in results if r['scoring_result'].result_class == 'B'),
                'Class C': sum(1 for r in results if r['scoring_result'].result_class == 'C')
            }
            st.bar_chart(chart_data)


# Add pages to navigation
PAGES = {
    "Risk Matrix": risk_matrix_page,
    "Batch Generation": risk_matrix_batch_page,
    "Rules Management": risk_matrix_rules_page,
    "Analytics": risk_matrix_analytics_page
}

# Main app
st.sidebar.title("Navigation")
selection = st.sidebar.radio("Go to", list(PAGES.keys()))
PAGES[selection]()
```

### **UI Integration Points**

| Integration Point | Description |
|-------------------|-------------|
| **Shared Streamlit App** | All pages in one app |
| **Shared Theme** | Same styling and layout |
| **Shared Components** | Reuse helper functions |
| **Shared State** | Can use st.session_state |
| **Navigation** | Add to existing sidebar |

---

## **Data Flow Integration**

### **End-to-End Data Flow**

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   USER INTERACTION   │────▶│   API/UI             │────▶│   AGENT 4            │
│  - Streamlit page    │     │  - FastAPI endpoint  │     │  - Workflow         │
│  - API request       │     │  - CLI command       │     │    execution        │
└─────────────────────┘     └─────────────────────┘     └──────────┬──────────┘
                                                                  │
                                                                  ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   EXISTING          │◀────│   AGENT 4            │     │   AGENT 4            │
│   PIPELINE           │     │   DATA EXTRACTION    │────▶│   SCORING            │
│  - Agent 1 (Parser)  │     │  - SQLite queries    │     │  - Apply rules      │
│  - Agent 2 (Vector  │     │  - ChromaDB queries  │     │  - Calculate scores  │
│    Store)           │     │  - Data aggregation  │     │  - Result classes   │
│  - Agent 3 (VA26)    │     └─────────────────────┘     └──────────┬──────────┘
└─────────────────────┘                                          │
                                                                   ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   EXISTING          │     │   AGENT 4            │     │   AGENT 4            │
│   PIPELINE           │     │   VALIDATION         │────▶│   EXCEL FILLING      │
│  - VA26 Rules        │     │  - ISO 13485 checks  │     │  - Load template    │
│  - Compliance        │     │  - Data quality      │     │  - Write data       │
│    checks            │     │  - Audit trail       │     │  - Preserve formulas │
└─────────────────────┘     └─────────────────────┘     └──────────┬──────────┘
                                                                   │
                                                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OUTPUTS                                             │
│  - Filled Excel files (outputs/)                                    │
│  - Logs (agent4_risk_matrix.log)                                    │
│  - Audit trail (for compliance)                                    │
│  - API responses                                                     │
└─────────────────────────────────────────────────────────────────┘
```

### **Data Dependencies**

Agent 4 **depends on** data from:

| Data Source | Agent | Tables | Used For |
|-------------|-------|--------|----------|
| Suppliers | 1, 2 | `suppliers` | Basic supplier info |
| Certificates | 1, 2 | `certificate_register` | Certificate status |
| Audit Findings | 1, 2 | `audit_findings` | Quality scoring |
| Purchase History | 1, 2 | `purchase_history` | Delivery, price analysis |
| VA26 Rules | 3 | N/A | Reference for consistency |

Agent 4 **produces** data for:

| Data Output | Format | Used By |
|-------------|--------|---------|
| Filled Excel | XLSX | Users, compliance |
| Scoring Results | JSON | API, UI, analytics |
| Validation Results | JSON | API, UI |
| Audit Trail | Logs | Compliance |

---

## **Code Integration**

### **Import Structure**

Agent 4 **imports from the existing pipeline**:

```python
# In agent4_risk_matrix/config/__init__.py
from pipeline.config import Config as PipelineConfig

# In agent4_risk_matrix/data/extractor.py
from pipeline.agent2_vectorstore.storage.sqlite_store import SQLiteStore
from pipeline.agent2_vectorstore.storage.chroma_store import ChromaDBStore

# In agent4_risk_matrix/execution/scorer.py
from pipeline.agent3_evaluator.rules.va26 import VA26Rules

# In agent4_risk_matrix/llm/client.py
from pipeline.config import Config as PipelineConfig
```

### **Shared Utilities**

Agent 4 can **reuse existing utilities** from the pipeline:

```python
# Example: Reuse logging configuration
from pipeline.utils.logging import setup_logging
setup_logging()

# Example: Reuse database connection pooling
from pipeline.utils.database import get_db_connection
conn = get_db_connection()

# Example: Reuse error handling
from pipeline.utils.errors import handle_error
try:
    # ... code ...
except Exception as e:
    handle_error(e, context="Agent 4")
```

### **Code Organization**

```
pipeline/
├── config.py                          # Shared configuration
├── utils/                             # Shared utilities
│   ├── logging.py
│   ├── database.py
│   └── errors.py
│
├── agent1_offline_parser/             # Existing
├── agent2_vectorstore/                # Existing
├── agent3_evaluator/                  # Existing
│
├── agent4_risk_matrix/                # NEW
│   ├── __init__.py
│   ├── main.py
│   ├── config/
│   ├── data/
│   ├── execution/
│   ├── llm/
│   ├── orchestrator/
│   ├── templates/
│   └── outputs/
│
├── api/                               # Extended
│   └── main.py                        # + new endpoints
│
└── ui/                                # Extended
    └── app.py                         # + new pages
```

---

## **Testing Integration**

### **Shared Test Infrastructure**

Agent 4 **uses the same test infrastructure** as the existing pipeline:

```python
# In agent4_risk_matrix/tests/conftest.py

import pytest
from pipeline.tests.conftest import *  # Import existing fixtures

@pytest.fixture
def sample_supplier_data():
    """Sample supplier data for testing."""
    return AggregatedSupplierData(
        supplier_id="TEST001",
        legal_name="Test Supplier",
        quality_score=95.0,
        complaint_rate=0.01,
        on_time_delivery_rate=0.98
    )

@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary output directory."""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    return output_dir
```

### **Test Integration Points**

| Test Type | Integration |
|-----------|-------------|
| Unit Tests | Reuse existing test patterns |
| Integration Tests | Test Agent 4 with existing pipeline |
| End-to-End Tests | Test full workflow from API/UI |
| Compliance Tests | Test ISO 13485 requirements |

---

## **Deployment Integration**

### **Shared Dependencies**

Agent 4 **adds to the existing `requirements.txt`**:

```text
# Existing requirements (from pipeline/requirements.txt)
openpyxl>=3.0.0
pandas>=1.0.0
pyyaml>=5.0.0
sqlite3>=3.0.0
fastapi>=0.68.0
streamlit>=1.0.0
httpx>=0.20.0

# New requirements for Agent 4
xlsxtpl>=0.2.0
Jinja2>=3.0.0
langgraph>=0.0.10
```

### **Docker Integration**

If using Docker, Agent 4 **extends the existing Dockerfile**:

```dockerfile
# Existing Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install existing dependencies
COPY pipeline/requirements.txt .
RUN pip install -r requirements.txt

# Copy existing pipeline
COPY pipeline/ ./pipeline/

# Install Agent 4 dependencies
COPY pipeline/agent4_risk_matrix/requirements.txt .
RUN pip install -r agent4_risk_matrix/requirements.txt

# Copy Agent 4
COPY pipeline/agent4_risk_matrix/ ./pipeline/agent4_risk_matrix/

# Set up templates
COPY templates/ ./pipeline/agent4_risk_matrix/templates/

# Run
CMD ["uvicorn", "pipeline.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### **CI/CD Integration**

Agent 4 **integrates with existing CI/CD**:

```yaml
# .github/workflows/test.yml

name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r pipeline/requirements.txt
          pip install -r pipeline/agent4_risk_matrix/requirements.txt
      
      - name: Run existing tests
        run: |
          cd pipeline
          python -m pytest agent1_offline_parser/tests/
          python -m pytest agent2_vectorstore/tests/
          python -m pytest agent3_evaluator/tests/
      
      - name: Run Agent 4 tests
        run: |
          cd pipeline
          python -m pytest agent4_risk_matrix/tests/
```

---

## **Summary**

Agent 4 **deeply integrates** with the existing pipeline through:

### **1. Database Integration**
- ✅ Reuses SQLite database from Agent 2
- ✅ Reuses ChromaDB from Agent 2
- ✅ Uses same data tables and models

### **2. Configuration Integration**
- ✅ Inherits from `pipeline/config.py`
- ✅ Uses same environment variables
- ✅ Respects existing paths and settings

### **3. LLM Integration**
- ✅ Reuses LM Studio configuration
- ✅ Can reference VA26 rules from Agent 3

### **4. API Integration**
- ✅ Extends existing FastAPI backend
- ✅ Adds new endpoints for risk matrix operations
- ✅ Reuses authentication and error handling

### **5. UI Integration**
- ✅ Extends existing Streamlit frontend
- ✅ Adds new pages for risk matrix generation
- ✅ Reuses theme and components

### **6. Data Flow Integration**
- ✅ Consumes data from Agents 1-2
- ✅ Produces outputs for users and compliance
- ✅ Maintains audit trails

### **7. Code Integration**
- ✅ Imports from existing pipeline modules
- ✅ Reuses utilities and helpers
- ✅ Follows existing patterns

### **8. Testing Integration**
- ✅ Uses same test infrastructure
- ✅ Adds Agent 4-specific tests
- ✅ Integrates with CI/CD

### **9. Deployment Integration**
- ✅ Adds to existing dependencies
- ✅ Extends Dockerfile
- ✅ Integrates with CI/CD

---

## **Integration Checklist**

- [ ] SQLite database connection working
- [ ] ChromaDB connection working
- [ ] LM Studio integration working
- [ ] Configuration inheritance working
- [ ] API endpoints added and working
- [ ] UI pages added and working
- [ ] Data extraction from existing tables working
- [ ] Scoring with existing data working
- [ ] Excel filling working
- [ ] Validation working
- [ ] Audit trail working
- [ ] Tests passing
- [ ] CI/CD integration complete

---

*Document Version: 1.0 | Author: Vibe Code (Mistral AI)*
