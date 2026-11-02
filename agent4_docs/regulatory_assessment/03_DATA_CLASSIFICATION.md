# 03: Data Classification Framework
## Supplier Qualification Pipeline - BEC Robotics

---

## Document Metadata
- **Document ID**: 03_DATA_CLASSIFICATION
- **Version**: 1.0
- **Created**: 2024
- **Author**: Senior Regulatory Affairs Consultant
- **Classification**: Internal - Confidential

---

## Table of Contents
1. [Introduction](#1-introduction)
2. [Data Classification Methodology](#2-data-classification-methodology)
3. [Personal Data Analysis](#3-personal-data-analysis)
4. [Confidential Business Information](#4-confidential-business-information)
5. [Derived and Processed Data](#5-derived-and-processed-data)
6. [Sensitivity Levels](#6-sensitivity-levels)
7. [Data Flow Classification Matrix](#7-data-flow-classification-matrix)
8. [Code Evidence](#8-code-evidence)
9. [Regulatory Implications](#9-regulatory-implications)
10. [Recommendations](#10-recommendations)

---

## 1. Introduction

### 1.1 Purpose
This document establishes a comprehensive data classification framework for the Supplier Qualification Pipeline at BEC Robotics

### 1.2 Scope
Covers all data types: original documents, extracted text, embeddings, database records, LLM prompts/outputs, logs, and audit trails.

### 1.3 System Overview
Processes supplier certificates, audit reports, nonconformance reports, purchase history, evaluation reports, and questionnaires.

---

## 2. Data Classification Methodology

### 2.1 Classification Levels

| **Level** | **Name** | **Description** | **Protection Requirements** |
|-----------|----------|-----------------|-----------------------------|
| **L1** | Public | Non-sensitive, publicly available | Minimal |
| **L2** | Internal | Business information for internal use | Standard |
| **L3** | Confidential | Sensitive business information | Enhanced |
| **L4** | Restricted | Highly sensitive, personal data, trade secrets | Maximum |

---

## 3. Personal Data Analysis

### 3.1 Definition (GDPR Art. 4(1))
Any information relating to an identified or identifiable natural person.

### 3.2 Identified Personal Data

#### Supplier Representative Data
| **Data Element** | **Source** | **Processing Stage** | **Legal Basis** |
|------------------|------------|----------------------|-----------------|
| Names | Certificates, audit reports | OCR/Extraction (Agent 1) | Legitimate interest (Art. 6(1)(f)) |
| Email addresses | Contact forms, certificates | Structured extraction | Legitimate interest |
| Phone numbers | Contact information | Structured extraction | Legitimate interest |
| Job titles | Certificates, business cards | OCR/Extraction | Legitimate interest |
| Signatures | Signed certificates | Image processing | Legitimate interest |

#### BEC Employee Data
| **Data Element** | **Source** | **Processing Stage** | **Legal Basis** |
|------------------|------------|----------------------|-----------------|
| Auditor names | Audit reports | Human review (Agent 3) | Employment contract (Art. 6(1)(b)) |
| User identifiers | System logs | All agents | Legitimate interest |
| Approval signatures | Evaluation reports | Report generation | Legitimate interest |

### 3.3 Special Categories of Personal Data
**Assessment**: The system does NOT process special category data (Art. 9):
- No health data, racial/ethnic origin, political opinions, religious beliefs, biometric data, genetic data, sexual orientation, or trade union membership

---

## 4. Confidential Business Information

### 4.1 Identified Categories

#### Supplier-Specific Confidential Information
| **Category** | **Data Elements** | **Sensitivity** | **Protection Level** |
|--------------|-------------------|-----------------|----------------------|
| Certificate Details | Certificate numbers, issue/expiry dates, certification bodies | High | L3 |
| Audit Findings | Nonconformities, observations, CAPA status | High | L3 |
| Financial Information | Pricing, payment terms, volume discounts | High | L3 |
| Performance Metrics | Delivery performance, quality scores, defect rates | Medium | L2 |
| Technical Specifications | Product specifications, manufacturing processes | High | L3 |
| Business Relationships | Supplier contracts, partnership terms | High | L3 |

#### BEC Robotics Confidential Information
| **Category** | **Data Elements** | **Sensitivity** | **Protection Level** |
|--------------|-------------------|-----------------|----------------------|
| Evaluation Criteria | Risk scoring methodology, weighting factors | High | L3 |
| Supplier Rankings | Internal supplier performance rankings | Medium | L2 |
| Quality Metrics | Internal quality scores, audit results | Medium | L2 |
| Decision Rationale | Reasoning for supplier approval/rejection | High | L3 |

### 4.2 Trade Secrets (Directive (EU) 2016/943)
May qualify as trade secrets:
- Supplier pricing algorithms and discount structures
- Internal risk scoring methodology (VA26 rules)
- Supplier performance benchmarking data
- Proprietary evaluation criteria

---

## 5. Derived and Processed Data

### 5.1 Embeddings
- **Source**: Text from documents (may contain personal/confidential data)
- **Dimensionality**: 768 dimensions (BGE-M3)
- **Reversibility**: NOT reversible to original text
- **Sensitivity**: Inherits from source
- **Protection Level**: Inherits from source (minimum L2)

### 5.2 Extracted Entities
| **Entity Type** | **Sensitivity** | **Protection Level** |
|-----------------|-----------------|----------------------|
| Supplier names | L2 |
| Person names | L4 |
| Certificate numbers | L3 |
| Product codes | L2 |
| Dates | L2 |
| Locations | L2 |

### 5.3 Aggregated Statistics
| **Statistic** | **Sensitivity** | **Protection Level** | **Reversibility** |
|---------------|-----------------|----------------------|-------------------|
| Average delivery time | L2 | L2 | Not reversible |
| Defect rate | L2 | L2 | Not reversible |
| Supplier risk score | L3 | L3 | Not reversible |

### 5.4 Classification Results
| **Classification** | **Sensitivity** | **Protection Level** |
|--------------------|-----------------|----------------------|
| Risk class (A/B/C) | L3 |
| Supplier status | L3 |
| Certificate status | L2 |
| Anomaly flags | L2 |

### 5.5 LLM Outputs
| **Output Type** | **Sensitivity** | **Protection Level** |
|-----------------|-----------------|----------------------|
| Extracted facts | Inherits from source | Inherits from source |
| Summaries | Inherits from source | Inherits from source |
| Reasoning | L3 |
| Classifications | L3 |
| Explanations | L2 |

---

## 6. Sensitivity Levels

### 6.1 Level Definitions

#### Level 1: Public (L1)
- **Definition**: Information approved for public disclosure
- **Examples**: Publicly available supplier information, general product descriptions
- **Protection**: No special protection required

#### Level 2: Internal (L2)
- **Definition**: Business information for internal use only
- **Examples**: Supplier names, general performance metrics, internal process documentation
- **Protection**: Access limited to employees and authorized contractors, standard IT security

#### Level 3: Confidential (L3)
- **Definition**: Sensitive business information requiring protection
- **Examples**: Certificate details, pricing, technical specifications, evaluation methodology
- **Protection**: Access limited to authorized personnel, encryption at rest and in transit, access logging

#### Level 4: Restricted (L4)
- **Definition**: Highly sensitive information requiring maximum protection
- **Examples**: Personal data (names, emails, phone numbers), trade secrets, financial data
- **Protection**: Strict access control (need-to-know), strong encryption, comprehensive logging, regular audits

---

## 7. Data Flow Classification Matrix

### 7.1 Stage-by-Stage Classification

| **Stage** | **Input Data** | **Output Data** | **Sensitivity Level** | **Protection Requirements** |
|-----------|----------------|-----------------|-----------------------|-----------------------------|
| 1. Document Upload | Original files | Stored documents | L2-L4 | Encryption at rest, access controls |
| 2. OCR/Extraction | Documents | Extracted text | Inherits | Same as input |
| 3. Text Cleaning | Extracted text | Cleaned text | Inherits | Same as input |
| 4. Structured Extraction | Cleaned text | Structured JSON | Inherits | Same as input |
| 5. SQLite Storage | Structured data | Database records | Inherits | Encryption at rest, access controls |
| 6. Chunking | Cleaned text | Text chunks | Inherits | Same as input |
| 7. Embedding Generation | Text chunks | Embeddings | Inherits (min L2) | Same as input |
| 8. ChromaDB Storage | Embeddings + metadata | Indexed vectors | Inherits (min L2) | Encryption at rest, access controls |
| 9. LLM Prompt Construction | Text chunks, context | Prompts | Inherits | Same as input |
| 10. LLM Inference | Prompts | LLM outputs | Inherits | Same as input |
| 11. Response Parsing | LLM outputs | Structured outputs | Inherits | Same as input |
| 12. Risk Classification | Structured data | Risk scores | L3 | Encryption, access controls |
| 13. Human Review | All outputs | Approved decisions | L3-L4 | Audit trail, approval logging |
| 14. Report Generation | All data | Evaluation reports | L3-L4 | Encryption, access controls |

### 7.2 Data Type Classification Summary

| **Data Type** | **Personal Data** | **Confidential Business** | **Sensitivity Level** | **Retention Period** |
|---------------|-------------------|---------------------------|-----------------------|----------------------|
| Original documents | Mixed | Mixed | L2-L4 | 10 years |
| Extracted text | Mixed | Mixed | Inherits | Same as source |
| Structured records | Mixed | Mixed | Inherits | Same as source |
| Embeddings | Mixed | Mixed | Inherits (min L2) | Same as source |
| Vector index | Mixed | Mixed | Inherits (min L2) | Same as source |
| LLM prompts | Mixed | Mixed | Inherits | Session duration |
| LLM outputs | Mixed | Mixed | Inherits | Session duration |
| Evaluation reports | Yes (auditor names) | Yes | L4 (personal), L3 (business) | 10 years |
| Logs | No | Yes | L2 | 1 year |
| Audit trails | Yes | Yes | L4 (personal), L3 (business) | 10 years |

---

## 8. Code Evidence

### 8.1 Personal Data Extraction
```python
# agent1_offline_parser/extractors/entity_extractor.py
class PersonEntityExtractor:
    def extract_persons(self, text: str) -> List[Person]:
        # Extracts: name, title, email, phone, company
        persons = []
        name_pattern = r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b'
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
```

### 8.2 Confidential Data Extraction
```python
# agent1_offline_parser/extractors/certificate_extractor.py
class CertificateExtractor:
    def extract_certificates(self, text: str) -> List[Certificate]:
        # Extracts: certificate_number (L3), issue_date, expiry_date, certification_body
        cert_pattern = r'(?:Certificate|Zertifikat)\s*(?:No|Nr|Number)?\.?\s*([A-Z0-9\-\s]{10,50})'
```

### 8.3 Database Schema
```python
# agent2_vectorstore/storage/sqlite_store.py
CREATE TABLE IF NOT EXISTS supplier_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id TEXT NOT NULL,
    document_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    contact_person TEXT,  # L4 - Personal data
    contact_email TEXT,    # L4 - Personal data
    certificate_number TEXT,  # L3 - Confidential
    expiry_date TEXT  # L2 - Internal
)
```

### 8.4 LLM Integration
```python
# agent1_offline_parser/llm/client.py
class LMStudioClient:
    def generate(self, prompt: str, system: str = None) -> str:
        # Local API call - no external transfer
        # Prompt may contain personal/confidential data
        response = requests.post(
            f"{self.base_url}/chat/completions",
            json={"messages": [{"role": "user", "content": prompt}]}
        )
```

---

## 9. Regulatory Implications

### 9.1 GDPR
- **Lawful Basis**: Legitimate interest (Art. 6(1)(f)) for supplier data, Employment contract (Art. 6(1)(b)) for employee data
- **Data Minimization**: Partial compliance - full document text sent to LLM
- **Storage Limitation**: Partial compliance - no automatic deletion
- **Data Subject Rights**: Not implemented
- **DPIA**: Likely required (systematic evaluation of personal data)

### 9.2 EU AI Act
- **Classification**: AI system (Art. 3(1)) - Limited risk category
- **Requirements**: Transparency obligations (Art. 52), Human oversight (Art. 14)
- **Human Oversight**: Compliant - all decisions require human approval
- **Transparency**: Not implemented - no AI disclosure to users

### 9.3 EU MDR
- **Applicability**: Does NOT directly apply (software is not a medical device)
- **Article 10(9)**: Relevant - QMS must ensure compliance
- **Supplier Control**: Partially compliant - evaluation implemented, no formal validation

### 9.4 ISO 13485:2016
- **Clause 4.1.6**: Computerized System Validation (CSV) required - NOT implemented
- **Clause 7.4**: Purchasing process - Compliant

### 9.5 Trade Secrets Directive
- **Applicability**: Applicable to pricing algorithms, evaluation methodology
- **Current Protection**: Inadequate - no encryption, no access controls

---

## 10. Recommendations

### 10.1 Immediate Actions (Before Real Data)
1. **Data Classification**: Create policy, implement labeling, train staff
2. **Personal Data Protection**: Implement minimization, redaction, encryption
3. **Access Controls**: Implement authentication, RBAC, logging
4. **Security**: Enable encryption, secure deletion, network security

### 10.2 Pre-Operational Actions (Before QMS Use)
1. **CSV**: Develop validation plan, perform risk assessment, execute tests
2. **Data Protection**: Conduct DPIA, create processing records, implement retention
3. **AI Act**: Add transparency notices, document AI system
4. **Contractual**: Review supplier contracts, create DPAs if needed

### 10.3 Production Improvements
1. **Advanced Security**: MFA, DLP, IDS, regular audits
2. **Advanced Privacy**: Pseudonymization, differential privacy, anonymization
3. **Advanced AI Governance**: Model versioning, performance monitoring, incident reporting
4. **QMS Integration**: Integrate with existing QMS, electronic signatures, advanced analytics

---

**Next Document**: [04_GDPR_ASSESSMENT.md](04_GDPR_ASSESSMENT.md)
**Previous Document**: [02_DATA_LIFECYCLE.md](02_DATA_LIFECYCLE.md)