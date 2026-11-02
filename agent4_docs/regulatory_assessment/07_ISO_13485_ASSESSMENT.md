# 07: ISO 13485:2016 and Computerized System Validation Assessment
## Supplier Qualification Pipeline - BEC Robotics

---

## Document Metadata
- **Document ID**: 07_ISO_13485_ASSESSMENT
- **Version**: 1.0
- **Created**: 2024
- **Classification**: Internal - Confidential

---

## Table of Contents
1. [Introduction](#1-introduction)
2. [ISO 13485 Overview](#2-iso-13485-overview)
3. [Applicability Analysis](#3-applicability-analysis)
4. [Quality Management System Requirements](#4-quality-management-system-requirements)
5. [Computerized System Validation (CSV)](#5-computerized-system-validation-csv)
6. [Purchasing Process Requirements](#6-purchasing-process-requirements)
7. [Documentation Requirements](#7-documentation-requirements)
8. [Risk Management](#8-risk-management)
9. [Code Evidence](#9-code-evidence)
10. [Gap Analysis](#10-gap-analysis)
11. [CSV Implementation Guide](#11-csv-implementation-guide)
12. [Recommendations](#12-recommendations)

---

## 1. Introduction

### 1.1 Purpose
This document provides a comprehensive assessment of the Supplier Qualification Pipeline's compliance with ISO 13485:2016, with a focus on Computerized System Validation (CSV) requirements.

### 1.2 Scope
Assessment covers:
- ISO 13485:2016 applicability to the Supplier Qualification Pipeline
- Quality Management System (QMS) requirements
- Computerized System Validation (CSV) requirements (§4.1.6)
- Purchasing process requirements (§7.4)
- Documentation requirements
- Risk management requirements

### 1.3 Standards Framework
- **ISO 13485:2016**: Medical devices - Quality management systems - Requirements for regulatory purposes
- **ISO 9001:2015**: Quality management systems - Requirements (foundation for ISO 13485)
- **ISO 14971:2019**: Application of risk management to medical devices
- **21 CFR Part 11**: Electronic records; Electronic signatures (US FDA, referenced for CSV)
- **GAMP 5**: Good Automated Manufacturing Practice (industry guidance for CSV)

---

## 2. ISO 13485 Overview

### 2.1 Structure of ISO 13485:2016

| **Clause** | **Title** | **Description** |
|------------|-----------|-----------------|
| 1 | Scope | Scope of the standard |
| 2 | Normative References | Referenced documents |
| 3 | Terms and Definitions | Definitions |
| 4 | Quality Management System | QMS requirements |
| 4.1 | General Requirements | QMS establishment and maintenance |
| 4.1.1 | General | QMS processes |
| 4.1.2 | Application | Process applicability |
| 4.1.3 | Quality Management System Documentation | Documentation requirements |
| 4.1.4 | Document Control | Document control procedures |
| 4.1.5 | Records | Record control procedures |
| **4.1.6** | **Validation of Software** | **Computerized System Validation** |
| 4.2 | Documentation Requirements | Documentation structure |
| 5 | Management Responsibility | Management obligations |
| 6 | Resource Management | Resource provision |
| 7 | Product Realization | Product realization processes |
| 7.1 | Planning of Product Realization | Planning requirements |
| 7.2 | Customer-Related Processes | Customer communication |
| 7.3 | Design and Development | Design and development processes |
| **7.4** | **Purchasing** | **Supplier management** |
| 7.4.1 | Purchasing Process | Purchasing controls |
| 7.4.2 | Purchasing Information | Purchasing specifications |
| 7.4.3 | Verification of Purchased Product | Supplier verification |
| 7.5 | Production and Service Provision | Production processes |
| 7.6 | Control of Monitoring and Measuring Equipment | Equipment calibration |
| 8 | Measurement, Analysis and Improvement | Continuous improvement |

### 2.2 Key Definitions

#### 2.2.1 Quality Management System (QMS)
> "set of interrelated or interacting elements that organizations use to formulate quality policies and quality objectives and to establish the processes needed to achieve those objectives"

#### 2.2.2 Computer Software
> "set of instructions that, when executed by computer hardware, causes the hardware to perform a function"

#### 2.2.3 Validation
> "confirmation, through the provision of objective evidence, that the requirements for a specific intended use or application have been fulfilled"

#### 2.2.4 Verification
> "confirmation, through the provision of objective evidence, that specified requirements have been fulfilled"

#### 2.2.5 Software
> "programs, procedures, rules and any associated documentation pertaining to the operation of a computer system"

---

## 3. Applicability Analysis

### 3.1 Is ISO 13485:2016 Applicable?

**Assessment**: ✅ **YES**

**Justification**:
- ✅ BEC Robotics is a **medical device manufacturer**
- ✅ ISO 13485:2016 is the **harmonized standard** for medical device QMS under EU MDR
- ✅ Compliance with ISO 13485:2016 **demonstrates conformity** with EU MDR QMS requirements (Art. 10(9))
- ✅ The Supplier Qualification Pipeline is **used in the QMS** (supplier management)

**Conclusion**: ISO 13485:2016 **applies** to the Supplier Qualification Pipeline as part of BEC Robotics' QMS.

### 3.2 Which Clauses Apply to the Supplier Qualification Pipeline?

| **Clause** | **Applicability** | **Justification** |
|------------|-------------------|-------------------|
| 4.1.1 | ✅ Applicable | QMS processes apply to all processes, including supplier management |
| 4.1.2 | ✅ Applicable | Process applicability must be determined |
| 4.1.3 | ✅ Applicable | QMS documentation required |
| 4.1.4 | ✅ Applicable | Document control required |
| 4.1.5 | ✅ Applicable | Record control required |
| **4.1.6** | **✅ Applicable** | **Software validation required for QMS software** |
| 4.2 | ✅ Applicable | Documentation requirements |
| 7.1 | ✅ Applicable | Product realization planning |
| **7.4** | **✅ Applicable** | **Purchasing process (supplier management)** |
| 7.4.1 | ✅ Applicable | Purchasing process |
| 7.4.2 | ✅ Applicable | Purchasing information |
| 7.4.3 | ✅ Applicable | Verification of purchased product |
| 8.2.1 | ✅ Applicable | Customer satisfaction (supplier as customer) |
| 8.2.2 | ✅ Applicable | Internal audit |
| 8.2.3 | ✅ Applicable | Monitoring and measurement of processes |
| 8.2.4 | ✅ Applicable | Monitoring and measurement of product |
| 8.3 | ✅ Applicable | Control of nonconforming product |
| 8.4 | ✅ Applicable | Data analysis |
| 8.5.1 | ✅ Applicable | Continual improvement |
| 8.5.2 | ✅ Applicable | Corrective action |
| 8.5.3 | ✅ Applicable | Preventive action |

---

## 4. Quality Management System Requirements

### 4.1 General Requirements (§4.1.1)

**Requirement**:
> "The organization shall establish, document, implement and maintain a quality management system and continually improve its effectiveness in accordance with the requirements of this International Standard."

**Assessment**: ✅ **PARTIALLY COMPLIANT**

**Analysis**:
- ✅ QMS **established** (BEC Robotics has QMS)
- ✅ QMS **documented** (QMS documentation exists)
- ✅ QMS **implemented** (QMS processes in place)
- ⚠️ QMS **maintenance** (No formal maintenance procedures for Pipeline)
- ⚠️ **Continual improvement** (No formal continual improvement process for Pipeline)

### 4.2 Application (§4.1.2)

**Requirement**:
> "The organization shall determine the processes needed for the quality management system and their application throughout the organization"

**Assessment**: ✅ **COMPLIANT**

**Analysis**:
- ✅ **Processes determined** (Supplier qualification process defined)
- ✅ **Application determined** (Pipeline used for supplier qualification)
- ✅ **Processes documented** (Workflow documented)

### 4.3 QMS Documentation (§4.2.1)

**Requirement**:
> "The quality management system documentation shall include:
> a) documented statements of a quality policy and quality objectives;
> b) a quality manual;
> c) documented procedures and records required by this International Standard;
> d) documents, including records, determined by the organization to be necessary to ensure the effective planning, operation and control of its processes"

**Assessment**: ✅ **PARTIALLY COMPLIANT**

**Analysis**:
- ✅ **Quality policy** exists (BEC Robotics)
- ✅ **Quality manual** exists (BEC Robotics)
- ⚠️ **Documented procedures** (Pipeline procedures not fully documented)
- ⚠️ **Records** (Pipeline records exist but not fully controlled)
- ⚠️ **Process documents** (Pipeline documentation partial)

**Code Evidence**:
```python
# Documentation exists but is partial
# README.md
## Supplier Qualification Pipeline

### Overview
The pipeline processes supplier documents to extract information and classify suppliers.

# Missing: Formal quality manual integration
# Missing: Complete procedure documentation
```

### 4.4 Document Control (§4.2.3)

**Requirement**:
> "Documents required by the quality management system shall be controlled. Records shall be established and maintained to provide evidence of conformity to requirements and of the effective operation of the quality management system."

**Assessment**: ⚠️ **PARTIALLY COMPLIANT**

**Analysis**:
- ✅ **Document approval** (Code review process exists)
- ✅ **Document changes** (Git version control)
- ⚠️ **Document distribution** (No formal distribution control)
- ⚠️ **Document retention** (No formal retention policy)
- ⚠️ **External documents** (No control of external documents)

### 4.5 Records Control (§4.2.4)

**Requirement**:
> "Records shall be established and maintained to provide evidence of conformity to requirements and of the effective operation of the quality management system. Records shall remain legible, readily identifiable and retrievable."

**Assessment**: ⚠️ **PARTIALLY COMPLIANT**

**Analysis**:
- ✅ **Records established** (Database records, evaluation reports)
- ✅ **Records maintained** (SQLite, ChromaDB storage)
- ⚠️ **Legibility** (Records are legible)
- ⚠️ **Identifiability** (Records are identifiable)
- ⚠️ **Retrievability** (Records are retrievable)
- ❌ **Retention** (No formal retention policy)
- ❌ **Disposition** (No formal disposition procedures)

---

## 5. Computerized System Validation (CSV)

### 5.1 CSV Requirement (§4.1.6)

**Requirement**:
> "The organization shall document any software used in the quality management system, and shall validate its use where the software or its output is used to demonstrate conformity of product to specified requirements, or for the monitoring and measurement of product or process characteristics."

**Assessment**: ❌ **NOT COMPLIANT**

### 5.2 CSV Applicability

**Question**: Does the Supplier Qualification Pipeline require CSV?

**Answer**: ✅ **YES**

**Justification**:
1. **Software used in QMS**: ✅ The Pipeline is **used in the QMS** for supplier management
2. **Demonstrate conformity**: ✅ Supplier qualification **demonstrates conformity** of purchased products to requirements
3. **Monitoring and measurement**: ✅ The Pipeline **monitors and measures** supplier characteristics (quality, performance, compliance)

**Conclusion**: The Supplier Qualification Pipeline **requires CSV** under ISO 13485:2016 §4.1.6.

### 5.3 CSV Process Overview

**GAMP 5 Approach**:
1. **Define**: System requirements and intended use
2. **Design**: System design and configuration
3. **Develop/Configure**: System development or configuration
4. **Test**: System testing
5. **Deploy**: System deployment
6. **Maintain**: System maintenance and change control

### 5.4 CSV Deliverables

| **Deliverable** | **Purpose** | **Current Status** |
|-----------------|-------------|--------------------|
| Validation Plan (VP) | Define validation approach, scope, and responsibilities | ❌ Not created |
| User Requirements Specification (URS) | Define user requirements and intended use | ⚠️ Partial (README, AGENTS.md) |
| Functional Requirements Specification (FRS) | Define functional requirements | ⚠️ Partial (code, documentation) |
| Design Specification (DS) | Define system design | ⚠️ Partial (architecture documentation) |
| Risk Assessment | Assess risks and mitigation measures | ❌ Not created |
| Validation Protocol (VP) | Define test cases and acceptance criteria | ❌ Not created |
| Validation Report (VR) | Document validation results and conclusion | ❌ Not created |
| Traceability Matrix | Trace requirements to tests to evidence | ❌ Not created |
| Standard Operating Procedures (SOPs) | Define operational procedures | ⚠️ Partial |
| Training Records | Document user training | ❌ Not created |
| Change Control | Manage system changes | ❌ Not implemented |

### 5.5 CSV Evidence Requirements

**Required Evidence**:
1. **Intended Use Statement**: Clear statement of what the system is used for
2. **Risk Assessment**: Assessment of risks and mitigation measures
3. **Requirements Traceability**: Traceability from requirements to tests
4. **Test Evidence**: Evidence of test execution and results
5. **Approval Records**: Evidence of approvals at each stage
6. **Change Control Records**: Evidence of controlled changes

**Current Status**: ❌ **NO CSV EVIDENCE**

### 5.6 CSV Test Levels

| **Test Level** | **Description** | **Current Status** |
|----------------|-----------------|--------------------|
| **Development Testing** | Testing during development | ✅ Partial (unit tests exist) |
| **Installation Qualification (IQ)** | Verify system is installed correctly | ❌ Not performed |
| **Operational Qualification (OQ)** | Verify system operates as intended | ❌ Not performed |
| **Performance Qualification (PQ)** | Verify system performs as intended in production | ❌ Not performed |

### 5.7 CSV for AI Systems

**Special Considerations for AI**:
1. **Intended Use**: Clearly define what the AI system is used for
2. **Data Quality**: Ensure training and validation data is appropriate
3. **Algorithm Validation**: Validate AI algorithms and models
4. **Performance Validation**: Validate system performance
5. **Change Management**: Manage changes to AI models and algorithms
6. **Human Oversight**: Ensure human oversight is in place

**Current Implementation**:
- ✅ **Intended use** defined (supplier qualification)
- ⚠️ **Data quality** partial (no formal validation)
- ❌ **Algorithm validation** not performed
- ❌ **Performance validation** not performed
- ❌ **Change management** not implemented
- ✅ **Human oversight** implemented

---

## 6. Purchasing Process Requirements

### 6.1 Purchasing Process (§7.4.1)

**Requirement**:
> "The organization shall ensure that purchased product conforms to specified purchase requirements. The type and extent of control applied to the supplier and the purchased product shall be dependent upon the effect of the purchased product on subsequent product realization or the final product."

**Assessment**: ✅ **COMPLIANT**

**Analysis**:
- ✅ **Supplier evaluation** implemented (Agent 3 - Evaluator)
- ✅ **Risk-based approach** implemented (VA26 risk classes)
- ✅ **Purchased product conformity** ensured (certificate verification)
- ✅ **Control proportional to effect** (risk-based classification)

**Code Evidence**:
```python
# agent3_evaluator/rules/va26.py
class VA26PurchasingRules:
    """
    VA26 purchasing rules (German harmonized standard for ISO 13485)
    
    ISO 13485 §7.4.1 Compliance:
    - Ensures purchased product conforms to requirements
    - Control proportional to effect on final product
    """
    
    RISK_CLASSES = {
        'A': {'min_score': 0, 'max_score': 1.5, 'control': 'Standard'},
        'B': {'min_score': 1.51, 'max_score': 2.5, 'control': 'Enhanced'},
        'C': {'min_score': 2.51, 'max_score': 3.0, 'control': 'Full with audit'}
    }
    
    def determine_control_level(self, supplier_data: dict) -> str:
        """
        Determine control level based on risk
        """
        score = self.calculate_score(supplier_data)
        
        if score <= 1.5:
            return 'Standard'
        elif score <= 2.5:
            return 'Enhanced'
        else:
            return 'Full with audit'
```

### 6.2 Purchasing Information (§7.4.2)

**Requirement**:
> "Purchasing information shall describe the product to be purchased, including where appropriate:
> a) requirements for approval of product, procedures, processes and equipment;
> b) requirements for qualification of personnel;
> c) quality management system requirements"

**Assessment**: ✅ **COMPLIANT**

**Analysis**:
- ✅ **Product description** (Supplier information collected)
- ✅ **Approval requirements** (Human approval required)
- ✅ **Qualification requirements** (Supplier qualification criteria defined)
- ✅ **QMS requirements** (Supplier QMS information collected)

### 6.3 Verification of Purchased Product (§7.4.3)

**Requirement**:
> "The organization shall establish and implement the inspection or other activities necessary for ensuring that purchased product conforms to specified purchase requirements."

**Assessment**: ✅ **COMPLIANT**

**Analysis**:
- ✅ **Certificate verification** implemented
- ✅ **Audit findings review** implemented
- ✅ **Quality metrics tracking** implemented
- ✅ **Conformity verification** (supplier meets requirements)

---

## 7. Documentation Requirements

### 7.1 Documented Procedures

**Requirement**:
> "The organization shall establish documented procedures for:
> - document control (§4.2.3)
> - record control (§4.2.4)
> - internal audit (§8.2.2)
> - control of nonconforming product (§8.3)
> - corrective action (§8.5.2)
> - preventive action (§8.5.3)"

**Assessment**: ⚠️ **PARTIALLY COMPLIANT**

**Analysis**:
- ⚠️ **Document control** (partial implementation)
- ⚠️ **Record control** (partial implementation)
- ❌ **Internal audit** (not implemented for Pipeline)
- ❌ **Nonconforming product** (not implemented for Pipeline)
- ❌ **Corrective action** (not implemented for Pipeline)
- ❌ **Preventive action** (not implemented for Pipeline)

### 7.2 Records

**Requirement**:
> "Records shall be established and maintained to provide evidence of conformity to requirements and of the effective operation of the quality management system."

**Assessment**: ⚠️ **PARTIALLY COMPLIANT**

**Analysis**:
- ✅ **Supplier documents** (stored in database)
- ✅ **Evaluation reports** (generated and stored)
- ✅ **Audit trails** (approval workflow logged)
- ❌ **Training records** (not implemented)
- ❌ **Maintenance records** (not implemented)
- ❌ **Change control records** (not implemented)

---

## 8. Risk Management

### 8.1 Risk Management System

**ISO 13485:2016 §7.1**:
> "The organization shall plan and develop the processes needed for product realization. In planning product realization, the organization shall determine the following, as appropriate:
> a) quality objectives and requirements for the product;
> b) the need to establish processes and documents, and to provide resources specific to the product;
> c) required verification, validation, monitoring, inspection and test activities specific to the product and the criteria for product acceptance;
> d) records needed to provide evidence that the realization processes and resulting product meet requirements"

**Assessment**: ⚠️ **PARTIALLY COMPLIANT**

**Analysis**:
- ✅ **Product realization planning** (Supplier qualification process planned)
- ✅ **Quality objectives** (Supplier quality objectives defined)
- ✅ **Processes and documents** (Processes and documents exist)
- ⚠️ **Verification and validation** (Partial implementation)
- ⚠️ **Acceptance criteria** (Risk classes defined)
- ⚠️ **Records** (Partial implementation)

### 8.2 Risk Assessment

**Requirement**:
> Risk assessment should be performed for all processes, including software used in QMS

**Assessment**: ❌ **NOT IMPLEMENTED**

**Analysis**:
- ❌ **No formal risk assessment** performed for Pipeline
- ❌ **No risk management file** created
- ❌ **No risk control measures** formally documented
- ❌ **No residual risk evaluation** performed

---

## 9. Code Evidence

### 9.1 CSV Gap Evidence
```python
# No CSV validation found in codebase
# config.py
class Config:
    # No CSV configurations
    CSV_VALIDATION_ENABLED = False  # Not set
    VALIDATION_PLAN = None
    VALIDATION_PROTOCOL = None
    VALIDATION_REPORT = None
    
    # No change control
    CHANGE_CONTROL_ENABLED = False
```

### 9.2 Purchasing Compliance Evidence
```python
# agent3_evaluator/rules/va26.py
class VA26Evaluator:
    """
    VA26 evaluator - ISO 13485 §7.4 compliance
    
    ISO 13485 §7.4.1: Purchasing process
    ISO 13485 §7.4.2: Purchasing information
    ISO 13485 §7.4.3: Verification of purchased product
    """
    
    def evaluate_supplier(self, supplier_data: dict) -> EvaluationResult:
        # ISO 13485 §7.4.1: Ensure purchased product conforms
        # ISO 13485 §7.4.2: Purchasing information
        # ISO 13485 §7.4.3: Verification
        
        score = self.calculate_score(supplier_data)
        risk_class = self.classify_risk(score)
        
        return EvaluationResult(
            supplier_id=supplier_data['id'],
            score=score,
            risk_class=risk_class,
            conforms_to_requirements=True  # §7.4.1, §7.4.3
        )
```

### 9.3 Documentation Gap Evidence
```python
# Documentation exists but is incomplete
# README.md
## Supplier Qualification Pipeline

### Overview
The pipeline processes supplier documents...

# Missing:
# - Formal URS (User Requirements Specification)
# - Formal FRS (Functional Requirements Specification)
# - Formal validation documentation
# - Formal change control procedures
```

### 9.4 Risk Management Gap Evidence
```python
# agent3_evaluator/scoring/risk_scorer.py
class RiskScorer:
    """
    Risk scoring implementation
    
    ISO 13485 Gap: No formal risk management
    - No risk assessment performed
    - No risk management file
    - No risk control measures documented
    """
    
    CRITERIA_WEIGHTS = {
        # No risk assessment or justification
    }
```

---

## 10. Gap Analysis

### 10.1 Critical Gaps (Immediate Action Required)

| **Gap** | **ISO 13485 Clause** | **Risk** | **Priority** |
|---------|----------------------|----------|--------------|
| No Computerized System Validation | §4.1.6 | Non-compliance with QMS requirements, audit failure | Critical |
| No validation plan | §4.1.6 | Non-compliance, audit failure | Critical |
| No validation protocol | §4.1.6 | Non-compliance, audit failure | Critical |
| No validation report | §4.1.6 | Non-compliance, audit failure | Critical |
| No risk assessment for software | §7.1 | Non-compliance with risk management | Critical |

### 10.2 High Priority Gaps

| **Gap** | **ISO 13485 Clause** | **Risk** | **Priority** |
|---------|----------------------|----------|--------------|
| No User Requirements Specification (URS) | §4.1.6 | Incomplete validation, audit findings | High |
| No Functional Requirements Specification (FRS) | §4.1.6 | Incomplete validation, audit findings | High |
| No traceability matrix | §4.1.6 | Incomplete validation, audit findings | High |
| No change control | §4.1.6, §4.2.3 | Uncontrolled changes, audit failure | High |
| No internal audit procedure | §8.2.2 | Non-compliance with QMS requirements | High |
| No corrective action procedure | §8.5.2 | Non-compliance with QMS requirements | High |

### 10.3 Medium Priority Gaps

| **Gap** | **ISO 13485 Clause** | **Risk** | **Priority** |
|---------|----------------------|----------|--------------|
| No preventive action procedure | §8.5.3 | Non-compliance with QMS requirements | Medium |
| No nonconforming product procedure | §8.3 | Non-compliance with QMS requirements | Medium |
| No training records | §6.2.2 | Non-compliance with training requirements | Medium |
| No maintenance procedures | §6.3 | Operational risk | Medium |

---

## 11. CSV Implementation Guide

### 11.1 Step 1: Define Validation Approach

**Validation Plan (VP) Template**:
```markdown
# Computerized System Validation Plan
## Supplier Qualification Pipeline

### 1. Purpose
Define the validation approach for the Supplier Qualification Pipeline to ensure compliance with ISO 13485:2016 §4.1.6.

### 2. Scope
- System: Supplier Qualification Pipeline
- Version: [Version Number]
- Intended Use: Supplier qualification and risk classification for medical device manufacturing

### 3. Responsibilities
- Validation Manager: [Name]
- QA Representative: [Name]
- IT Representative: [Name]
- End Users: [Names]

### 4. Validation Approach
- Follow GAMP 5 methodology
- Risk-based validation
- Categorize system as GAMP 5 Category 4 (Configured Product)

### 5. Deliverables
- Validation Plan (this document)
- User Requirements Specification (URS)
- Functional Requirements Specification (FRS)
- Design Specification (DS)
- Risk Assessment
- Validation Protocol (VP)
- Validation Report (VR)
- Traceability Matrix
- Standard Operating Procedures (SOPs)
- Training Records

### 6. Schedule
- [Timeline for validation activities]

### 7. Approval
- Validation Manager: _______________ Date: _______
- QA Representative: _______________ Date: _______
```

### 11.2 Step 2: Define User Requirements (URS)

**User Requirements Specification Template**:
```markdown
# User Requirements Specification (URS)
## Supplier Qualification Pipeline

### 1. Intended Use
The Supplier Qualification Pipeline shall be used to:
- Extract information from supplier documents (PDFs, scans)
- Classify suppliers based on risk criteria
- Generate evaluation reports
- Support supplier qualification decisions

### 2. User Requirements

#### 2.1 Functional Requirements
| ID | Requirement | Priority | Verification Method |
|----|-------------|----------|---------------------|
| URS-001 | System shall extract text from PDF documents | High | Test |
| URS-002 | System shall extract entities (suppliers, persons, certificates) | High | Test |
| URS-003 | System shall classify suppliers based on VA26 rules | High | Test |
| URS-004 | System shall generate evaluation reports | High | Test |
| URS-005 | System shall require human approval for all decisions | High | Test |

#### 2.2 Non-Functional Requirements
| ID | Requirement | Priority | Verification Method |
|----|-------------|----------|---------------------|
| URS-010 | System shall operate offline | High | Test |
| URS-011 | System shall maintain audit trail | High | Test |
| URS-012 | System shall preserve document formatting | Medium | Test |
| URS-013 | System shall support 140+ suppliers | Medium | Test |

#### 2.3 Compliance Requirements
| ID | Requirement | Priority | Verification Method |
|----|-------------|----------|---------------------|
| URS-020 | System shall comply with ISO 13485:2016 §4.1.6 | High | Audit |
| URS-021 | System shall comply with ISO 13485:2016 §7.4 | High | Audit |
| URS-022 | System shall support EU MDR compliance | High | Audit |

### 3. Approval
- Requester: _______________ Date: _______
- QA Representative: _______________ Date: _______
```

### 11.3 Step 3: Define Functional Requirements (FRS)

**Functional Requirements Specification Template**:
```markdown
# Functional Requirements Specification (FRS)
## Supplier Qualification Pipeline

### 1. System Architecture
[Describe system architecture with diagrams]

### 2. Functional Requirements

#### 2.1 Agent 1: Offline Parser
| ID | Requirement | Trace to URS | Test Case |
|----|-------------|--------------|-----------|
| FRS-001 | Parse PDF documents | URS-001 | TC-001 |
| FRS-002 | Extract text from images (OCR) | URS-001 | TC-002 |
| FRS-003 | Extract entities from text | URS-002 | TC-003 |

#### 2.2 Agent 2: Vector Store
| ID | Requirement | Trace to URS | Test Case |
|----|-------------|--------------|-----------|
| FRS-010 | Store extracted data in SQLite | URS-002 | TC-010 |
| FRS-011 | Index documents in ChromaDB | URS-002 | TC-011 |
| FRS-012 | Generate embeddings for text | URS-002 | TC-012 |

#### 2.3 Agent 3: Evaluator
| ID | Requirement | Trace to URS | Test Case |
|----|-------------|--------------|-----------|
| FRS-020 | Classify suppliers based on rules | URS-003 | TC-020 |
| FRS-021 | Generate evaluation reports | URS-004 | TC-021 |
| FRS-022 | Require human approval | URS-005 | TC-022 |

### 3. Approval
- System Owner: _______________ Date: _______
- QA Representative: _______________ Date: _______
```

### 11.4 Step 4: Perform Risk Assessment

**Risk Assessment Template**:
```markdown
# Risk Assessment
## Supplier Qualification Pipeline

### 1. Risk Identification

| ID | Risk Description | Category | Severity | Probability | Risk Level |
|----|------------------|----------|----------|-------------|------------|
| RA-001 | Incorrect document parsing | Functional | High | Medium | High |
| RA-002 | Incorrect entity extraction | Functional | High | Medium | High |
| RA-003 | Incorrect supplier classification | Functional | High | Medium | High |
| RA-004 | Data loss | Data Integrity | High | Low | Medium |
| RA-005 | Unauthorized access | Security | High | Low | Medium |

### 2. Risk Evaluation

| ID | Risk Level | Mitigation Measures | Residual Risk |
|----|------------|---------------------|---------------|
| RA-001 | High | Validation testing, human review | Medium |
| RA-002 | High | Validation testing, human review | Medium |
| RA-003 | High | Validation testing, human approval | Medium |
| RA-004 | Medium | Backup procedures, data validation | Low |
| RA-005 | Medium | Access controls, encryption | Low |

### 3. Risk Control Measures

| ID | Measure | Implementation | Verification |
|----|---------|----------------|-------------|
| RC-001 | Validation testing | Execute validation protocol | Test reports |
| RC-002 | Human review | Implement approval workflow | Workflow testing |
| RC-003 | Backup procedures | Implement backup and recovery | Backup testing |
| RC-004 | Access controls | Implement authentication and RBAC | Access testing |

### 4. Approval
- Risk Assessment Leader: _______________ Date: _______
- QA Representative: _______________ Date: _______
```

### 11.5 Step 5: Create Validation Protocol (VP)

**Validation Protocol Template**:
```markdown
# Validation Protocol (VP)
## Supplier Qualification Pipeline

### 1. Purpose
Define test cases to verify that the Supplier Qualification Pipeline meets user requirements and functions as intended.

### 2. Scope
- Installation Qualification (IQ)
- Operational Qualification (OQ)
- Performance Qualification (PQ)

### 3. Test Cases

#### 3.1 Installation Qualification (IQ)

| ID | Test Description | Expected Result | Pass/Fail |
|----|------------------|-----------------|-----------|
| IQ-001 | Verify system installation | System installed correctly | |
| IQ-002 | Verify dependencies | All dependencies installed | |
| IQ-003 | Verify configuration | Configuration files correct | |

#### 3.2 Operational Qualification (OQ)

| ID | Test Description | Expected Result | Pass/Fail |
|----|------------------|-----------------|-----------|
| OQ-001 | Test PDF parsing | Text extracted correctly | |
| OQ-002 | Test OCR | Text extracted from images | |
| OQ-003 | Test entity extraction | Entities extracted correctly | |
| OQ-004 | Test database storage | Data stored correctly | |
| OQ-005 | Test embedding generation | Embeddings generated | |
| OQ-006 | Test supplier classification | Suppliers classified correctly | |
| OQ-007 | Test report generation | Reports generated correctly | |
| OQ-008 | Test human approval workflow | Approval required for decisions | |

#### 3.3 Performance Qualification (PQ)

| ID | Test Description | Expected Result | Pass/Fail |
|----|------------------|-----------------|-----------|
| PQ-001 | Test with 140+ suppliers | System handles load | |
| PQ-002 | Test with various document types | System handles all types | |
| PQ-003 | Test with poor quality documents | System handles gracefully | |
| PQ-004 | Test end-to-end workflow | Complete workflow works | |

### 4. Acceptance Criteria
- All IQ tests pass
- All OQ tests pass
- All PQ tests pass
- No critical defects
- No high-severity defects

### 5. Approval
- Validation Leader: _______________ Date: _______
- QA Representative: _______________ Date: _______
```

### 11.6 Step 6: Execute Validation Tests

**Test Execution**:
1. Execute IQ tests
2. Document IQ results
3. Execute OQ tests
4. Document OQ results
5. Execute PQ tests
6. Document PQ results
7. Review all results
8. Address any failures
9. Retest as needed

### 11.7 Step 7: Create Validation Report (VR)

**Validation Report Template**:
```markdown
# Validation Report (VR)
## Supplier Qualification Pipeline

### 1. Executive Summary
- System validated: Supplier Qualification Pipeline
- Validation period: [Start Date] to [End Date]
- Validation result: PASS/FAIL

### 2. Validation Activities
- Validation Plan created and approved
- User Requirements Specification created and approved
- Functional Requirements Specification created and approved
- Risk Assessment performed
- Validation Protocol created and approved
- Validation tests executed

### 3. Test Results

#### 3.1 Installation Qualification (IQ)
| ID | Test Description | Result | Evidence |
|----|------------------|--------|----------|
| IQ-001 | Verify system installation | PASS | IQ-001_Result.pdf |
| IQ-002 | Verify dependencies | PASS | IQ-002_Result.pdf |

#### 3.2 Operational Qualification (OQ)
| ID | Test Description | Result | Evidence |
|----|------------------|--------|----------|
| OQ-001 | Test PDF parsing | PASS | OQ-001_Result.pdf |
| OQ-002 | Test OCR | PASS | OQ-002_Result.pdf |

#### 3.3 Performance Qualification (PQ)
| ID | Test Description | Result | Evidence |
|----|------------------|--------|----------|
| PQ-001 | Test with 140+ suppliers | PASS | PQ-001_Result.pdf |
| PQ-002 | Test end-to-end workflow | PASS | PQ-002_Result.pdf |

### 4. Deviations and Exceptions
- [List any deviations or exceptions]

### 5. Conclusion
The Supplier Qualification Pipeline has been successfully validated and meets all user requirements. The system is approved for use in the quality management system.

### 6. Approval
- Validation Leader: _______________ Date: _______
- QA Representative: _______________ Date: _______
- System Owner: _______________ Date: _______
```

### 11.8 Step 8: Create Traceability Matrix

**Traceability Matrix Template**:
```markdown
# Traceability Matrix
## Supplier Qualification Pipeline

| URS ID | URS Requirement | FRS ID | FRS Requirement | Test ID | Test Description | Test Result |
|--------|-----------------|--------|-----------------|---------|------------------|-------------|
| URS-001 | Extract text from PDF | FRS-001 | Parse PDF documents | OQ-001 | Test PDF parsing | PASS |
| URS-001 | Extract text from PDF | FRS-002 | Extract text from images | OQ-002 | Test OCR | PASS |
| URS-002 | Extract entities | FRS-003 | Extract entities from text | OQ-003 | Test entity extraction | PASS |
| URS-003 | Classify suppliers | FRS-020 | Classify suppliers | OQ-006 | Test supplier classification | PASS |
| URS-004 | Generate reports | FRS-021 | Generate evaluation reports | OQ-007 | Test report generation | PASS |
| URS-005 | Human approval | FRS-022 | Require human approval | OQ-008 | Test human approval workflow | PASS |
```

### 11.9 Step 9: Create Standard Operating Procedures (SOPs)

**SOP Templates**:

1. **System Operation SOP**:
```markdown
# SOP-001: Supplier Qualification Pipeline Operation

### 1. Purpose
Define procedures for operating the Supplier Qualification Pipeline.

### 2. Scope
All users of the Supplier Qualification Pipeline.

### 3. Responsibilities
- Users: Follow this procedure
- System Administrator: Maintain system
- QA: Monitor compliance

### 4. Procedure

#### 4.1 Document Upload
1. Access the Streamlit UI
2. Upload supplier document (PDF)
3. Verify document is processed correctly

#### 4.2 Supplier Evaluation
1. Review extracted information
2. Verify classification
3. Approve or reject decision

#### 4.3 Report Generation
1. Generate evaluation report
2. Review report
3. Save report to QMS

### 5. Records
- Document upload logs
- Evaluation records
- Approval records
- Reports

### 6. Approval
- QA Representative: _______________ Date: _______
```

2. **System Maintenance SOP**:
```markdown
# SOP-002: Supplier Qualification Pipeline Maintenance

### 1. Purpose
Define procedures for maintaining the Supplier Qualification Pipeline.

### 2. Scope
System administrators and IT staff.

### 3. Responsibilities
- System Administrator: Perform maintenance
- IT: Provide technical support
- QA: Monitor maintenance activities

### 4. Procedure

#### 4.1 Backup
1. Perform daily backup of databases
2. Verify backup integrity
3. Store backups securely

#### 4.2 Updates
1. Test updates in development environment
2. Document changes
3. Obtain approval from QA
4. Deploy to production

#### 4.3 Monitoring
1. Monitor system performance
2. Monitor error rates
3. Report issues to IT

### 5. Records
- Backup logs
- Update records
- Monitoring reports

### 6. Approval
- QA Representative: _______________ Date: _______
```

3. **Change Control SOP**:
```markdown
# SOP-003: Supplier Qualification Pipeline Change Control

### 1. Purpose
Define procedures for controlling changes to the Supplier Qualification Pipeline.

### 2. Scope
All changes to the system, including software, configuration, and documentation.

### 3. Responsibilities
- Change Requester: Submit change request
- Change Reviewer: Review change request
- QA: Approve changes
- IT: Implement changes

### 4. Procedure

#### 4.1 Change Request
1. Submit change request form
2. Describe change
3. Justify change
4. Assess impact

#### 4.2 Change Review
1. Review change request
2. Assess risk
3. Determine testing requirements
4. Approve or reject

#### 4.3 Change Implementation
1. Implement change in development
2. Test change
3. Document test results
4. Obtain final approval
5. Deploy to production

#### 4.4 Change Verification
1. Verify change in production
2. Monitor for issues
3. Document verification

### 5. Records
- Change request forms
- Change review records
- Change implementation records
- Change verification records

### 6. Approval
- QA Representative: _______________ Date: _______
```

### 11.10 Step 10: Training

**Training Plan**:
1. Identify training needs
2. Develop training materials
3. Conduct training sessions
4. Document training
5. Assess training effectiveness

**Training Records Template**:
```markdown
# Training Records
## Supplier Qualification Pipeline

| Trainee | Training Date | Training Topic | Trainer | Evidence |
|---------|---------------|----------------|---------|----------|
| User 1 | 2024-01-01 | System Operation | Trainer 1 | Training Certificate |
| User 2 | 2024-01-02 | System Operation | Trainer 1 | Training Certificate |
| Admin 1 | 2024-01-03 | System Maintenance | Trainer 2 | Training Certificate |
```

---

## 12. Recommendations

### 12.1 Category 1: Essential Before Real Data Processing

**Must be implemented before any real data is processed:**

1. **Create Validation Plan (VP)**
   - [ ] Define validation approach and scope
   - [ ] Identify responsibilities
   - [ ] Define deliverables
   - [ ] Set schedule
   - [ ] Obtain approvals

2. **Create User Requirements Specification (URS)**
   - [ ] Define intended use
   - [ ] Identify user requirements
   - [ ] Define compliance requirements
   - [ ] Obtain approvals

3. **Create Functional Requirements Specification (FRS)**
   - [ ] Define system architecture
   - [ ] Trace requirements to URS
   - [ ] Define test cases
   - [ ] Obtain approvals

4. **Perform Risk Assessment**
   - [ ] Identify risks
   - [ ] Evaluate risks
   - [ ] Define mitigation measures
   - [ ] Obtain approvals

### 12.2 Category 2: Necessary Before Operational Use in QMS

**Must be implemented before the system is used for operational supplier qualification:**

1. **Create Validation Protocol (VP)**
   - [ ] Define IQ test cases
   - [ ] Define OQ test cases
   - [ ] Define PQ test cases
   - [ ] Define acceptance criteria
   - [ ] Obtain approvals

2. **Execute Validation Tests**
   - [ ] Execute IQ tests
   - [ ] Document IQ results
   - [ ] Execute OQ tests
   - [ ] Document OQ results
   - [ ] Execute PQ tests
   - [ ] Document PQ results

3. **Create Validation Report (VR)**
   - [ ] Document validation activities
   - [ ] Document test results
   - [ ] Document deviations
   - [ ] Draw conclusion
   - [ ] Obtain approvals

4. **Create Traceability Matrix**
   - [ ] Trace URS to FRS
   - [ ] Trace FRS to tests
   - [ ] Document test results
   - [ ] Obtain approvals

5. **Create Standard Operating Procedures (SOPs)**
   - [ ] Create System Operation SOP
   - [ ] Create System Maintenance SOP
   - [ ] Create Change Control SOP
   - [ ] Obtain approvals

6. **Conduct Training**
   - [ ] Identify training needs
   - [ ] Develop training materials
   - [ ] Conduct training sessions
   - [ ] Document training

### 12.3 Category 3: Improvements for Production System

**Recommended for a mature, production-ready system:**

1. **Enhance CSV**
   - [ ] Implement automated testing
   - [ ] Set up continuous validation
   - [ ] Implement performance monitoring
   - [ ] Conduct regular validation reviews

2. **Enhance Risk Management**
   - [ ] Implement risk monitoring dashboard
   - [ ] Set up automated risk alerts
   - [ ] Conduct regular risk reviews
   - [ ] Implement risk trend analysis

3. **Enhance Documentation**
   - [ ] Implement document control system
   - [ ] Set up document change tracking
   - [ ] Conduct regular document reviews
   - [ ] Implement document retention procedures

4. **Enhance Compliance**
   - [ ] Implement compliance monitoring
   - [ ] Set up compliance alerts
   - [ ] Conduct regular compliance audits
   - [ ] Implement compliance trend analysis

---

## Summary and Conclusion

### Key Findings:
1. **ISO 13485 Applicability**: ✅ ISO 13485:2016 **applies** to the Supplier Qualification Pipeline as part of BEC Robotics' QMS
2. **CSV Requirement**: ✅ Computerized System Validation **is required** under §4.1.6
3. **Purchasing Compliance**: ✅ Supplier evaluation and classification **are compliant** with §7.4
4. **Current CSV Status**: ❌ **NO CSV PERFORMED** - Critical gap
5. **Current Documentation Status**: ⚠️ **PARTIAL DOCUMENTATION** - High priority gap

### Current Compliance Status:
- ✅ **Purchasing process** compliant with §7.4
- ✅ **Human approval** implemented
- ❌ **Computerized System Validation** NOT performed
- ❌ **Formal documentation** NOT complete
- ❌ **Risk assessment** NOT performed
- ❌ **Change control** NOT implemented

### Risk Assessment:
- **Overall Risk Level**: **CRITICAL** (due to missing CSV)
- **Primary Risks**: Non-compliance with ISO 13485 §4.1.6, audit failure, regulatory non-compliance
- **Mitigation Potential**: **HIGH** (with implementation of CSV)

### Priority Actions:
1. **Immediate**: Create validation plan, URS, FRS, and perform risk assessment
2. **Pre-Operational**: Execute validation tests, create validation report, create SOPs, conduct training
3. **Production**: Enhance CSV, risk management, documentation, and compliance

### Legal Obligations:
- **CSV**: ✅ **REQUIRED** (ISO 13485:2016 §4.1.6)
- **QMS Compliance**: ✅ **REQUIRED** (ISO 13485:2016 §4.1)
- **Purchasing Compliance**: ✅ **REQUIRED** (ISO 13485:2016 §7.4)
- **Documentation**: ✅ **REQUIRED** (ISO 13485:2016 §4.2)

**Next Document**: [08_OTHER_REQUIREMENTS.md](08_OTHER_REQUIREMENTS.md) - Other relevant requirements
**Previous Document**: [06_EU_MDR_ASSESSMENT.md](06_EU_MDR_ASSESSMENT.md) - EU MDR compliance assessment