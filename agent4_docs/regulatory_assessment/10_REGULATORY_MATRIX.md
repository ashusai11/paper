# 10: Regulatory Requirements Matrix
## Supplier Qualification Pipeline - BEC Robotics

---

## Document Metadata
- **Document ID**: 10_REGULATORY_MATRIX
- **Version**: 1.0
- **Created**: 2024
- **Classification**: Internal - Confidential

---

## Table of Contents
1. [Introduction](#1-introduction)
2. [Matrix Structure](#2-matrix-structure)
3. [GDPR Requirements Matrix](#3-gdpr-requirements-matrix)
4. [EU AI Act Requirements Matrix](#4-eu-ai-act-requirements-matrix)
5. [EU MDR Requirements Matrix](#5-eu-mdr-requirements-matrix)
6. [ISO 13485 Requirements Matrix](#6-iso-13485-requirements-matrix)
7. [German BDSG Requirements Matrix](#7-german-bdsg-requirements-matrix)
8. [NIS2 Directive Requirements Matrix](#8-nis2-directive-requirements-matrix)
9. [Trade Secrets Directive Requirements Matrix](#9-trade-secrets-directive-requirements-matrix)
10. [Summary Statistics](#10-summary-statistics)
11. [Compliance Dashboard](#11-compliance-dashboard)

---

## 1. Introduction

### 1.1 Purpose
This document provides a **structured regulatory requirements matrix** for the Supplier Qualification Pipeline, consolidating all applicable legal, regulatory, and standards requirements into a single, comprehensive reference table.

### 1.2 Scope
The matrix covers:
- **GDPR** (Regulation (EU) 2016/679)
- **EU AI Act** (Regulation (EU) 2024/1689)
- **EU MDR** (Regulation (EU) 2017/745)
- **ISO 13485:2016** (Medical devices - Quality management systems)
- **German BDSG** (Bundesdatenschutzgesetz)
- **NIS2 Directive** ((EU) 2022/2555)
- **Trade Secrets Directive** ((EU) 2016/943)

### 1.3 Methodology
Each requirement is assessed against:
1. **Applicability** to the Supplier Qualification Pipeline
2. **Current compliance status** based on code and architecture evidence
3. **Priority** for remediation
4. **Binding nature** (legally binding, contractual, or voluntary)

---

## 2. Matrix Structure

### 2.1 Column Definitions

| **Column** | **Description** | **Format** |
|------------|-----------------|------------|
| **ID** | Unique identifier for each requirement | Text |
| **Law/Regulation/Standard** | Name of the legal instrument or standard | Text |
| **Article/Clause/Section** | Specific article, clause, or section reference | Text |
| **Plain Language Meaning** | What the requirement means in simple terms | Text |
| **Applicability** | Why this requirement applies to the project | Text |
| **Code/Architecture Evidence** | Evidence from code or architecture showing compliance or non-compliance | Text |
| **Current Compliance Status** | Current status: Implemented, Partially Implemented, Missing, or Unknown | Status |
| **Recommended Action** | What needs to be done to achieve compliance | Text |
| **Priority** | Critical, High, Medium, or Low | Priority |
| **Binding Nature** | Legally Binding, Conditional, Contractual, or Voluntary | Nature |

### 2.2 Status Definitions

| **Status** | **Description** | **Color Code** |
|------------|-----------------|----------------|
| ✅ Implemented | Requirement is fully implemented and compliant | Green |
| ⚠️ Partially Implemented | Requirement is partially implemented but has gaps | Yellow |
| ❌ Missing | Requirement is not implemented at all | Red |
| ❓ Unknown | Applicability or compliance status is unknown | Gray |

### 2.3 Priority Definitions

| **Priority** | **Description** | **Timescale** |
|--------------|-----------------|---------------|
| Critical | Must be implemented before any real data processing | Immediate |
| High | Must be implemented before operational use in QMS | Pre-Operational |
| Medium | Should be implemented for production deployment | Production |
| Low | Nice to have, not essential for compliance | Future |

### 2.4 Binding Nature Definitions

| **Nature** | **Description** |
|------------|-----------------|
| Legally Binding | Required by law or regulation |
| Conditional | Required only if certain conditions are met |
| Contractual | Required by contract or agreement |
| Voluntary | Recommended but not required |

---

## 3. GDPR Requirements Matrix

| ID | Law/Regulation/Standard | Article/Clause | Plain Language Meaning | Applicability | Code/Architecture Evidence | Current Status | Recommended Action | Priority | Binding Nature |
|-----|-------------------------|----------------|------------------------|---------------|-----------------------------|-----------------|----------------------|----------|-----------------|
| GDPR-001 | GDPR | Art. 2 | GDPR applies to automated processing of personal data | System processes personal data (supplier rep names, emails, phone numbers) | `agent1_offline_parser/extractors/entity_extractor.py` extracts personal data | ✅ Implemented | None | N/A | Legally Binding |
| GDPR-002 | GDPR | Art. 3 | Territorial scope applies to processing in context of EU establishment | BEC Robotics is established in Germany (EU) | System deployed in EU | ✅ Implemented | None | N/A | Legally Binding |
| GDPR-003 | GDPR | Art. 5(1)(a) | Personal data must be processed lawfully, fairly, and transparently | System processes personal data | No privacy notices implemented | ❌ Missing | Create privacy notices, add AI disclosure | Critical | Legally Binding |
| GDPR-004 | GDPR | Art. 5(1)(b) | Personal data must be collected for specified, explicit, legitimate purposes | Supplier qualification is specified purpose | `README.md` documents purpose | ✅ Implemented | None | N/A | Legally Binding |
| GDPR-005 | GDPR | Art. 5(1)(c) | Only necessary personal data should be collected and processed | Full documents processed, no minimization | `agent1_offline_parser/parsers/pdf_parser.py` extracts all text | ❌ Missing | Implement data minimization, selective extraction, redaction | Critical | Legally Binding |
| GDPR-006 | GDPR | Art. 5(1)(d) | Personal data must be accurate and kept up to date | OCR errors possible, no validation | `agent1_offline_parser/extractors/entity_extractor.py` has no accuracy validation | ⚠️ Partially Implemented | Implement accuracy validation, correction mechanisms | High | Legally Binding |
| GDPR-007 | GDPR | Art. 5(1)(e) | Personal data should not be kept longer than necessary | All data stored indefinitely | `config.py` has no retention policies | ❌ Missing | Define retention periods, implement automatic deletion | Critical | Legally Binding |
| GDPR-008 | GDPR | Art. 5(1)(f) | Personal data must be processed securely | No encryption, no access controls | `config.py` shows no security configurations | ❌ Missing | Implement encryption, access controls, audit logging | Critical | Legally Binding |
| GDPR-009 | GDPR | Art. 5(2) | Controller must be able to demonstrate compliance | No compliance documentation | No Records of Processing Activities | ❌ Missing | Create Records of Processing Activities (Art. 30) | High | Legally Binding |
| GDPR-010 | GDPR | Art. 6(1)(f) | Legitimate interest can be lawful basis for processing | Supplier qualification is legitimate interest | System design supports legitimate interest | ✅ Implemented | None | N/A | Legally Binding |
| GDPR-011 | GDPR | Art. 6(1)(b) | Contract can be lawful basis for processing | Employee data processed under employment contracts | Auditor names processed | ✅ Implemented | None | N/A | Legally Binding |
| GDPR-012 | GDPR | Art. 13, 14 | Data subjects must be informed about processing | No privacy notices | No privacy notices in UI | ❌ Missing | Create and display privacy notices | Critical | Legally Binding |
| GDPR-013 | GDPR | Art. 15 | Data subjects have right to access their personal data | No access request procedure | No access request mechanism | ❌ Missing | Implement access request procedure | High | Legally Binding |
| GDPR-014 | GDPR | Art. 16 | Data subjects have right to rectification of inaccurate data | No rectification procedure | No correction mechanism | ❌ Missing | Implement rectification procedure | High | Legally Binding |
| GDPR-015 | GDPR | Art. 17 | Data subjects have right to erasure ('right to be forgotten') | No erasure procedure | `agent2_vectorstore/storage/sqlite_store.py` has no cascading deletion | ❌ Missing | Implement cascading deletion across all systems | Critical | Legally Binding |
| GDPR-016 | GDPR | Art. 18 | Data subjects have right to restriction of processing | No restriction mechanism | No restriction procedure | ❌ Missing | Implement restriction mechanism | High | Legally Binding |
| GDPR-017 | GDPR | Art. 20 | Data subjects have right to data portability | Export exists but not for portability | Export functionality exists | ⚠️ Partially Implemented | Implement data portability procedure | Medium | Legally Binding |
| GDPR-018 | GDPR | Art. 21 | Data subjects have right to object to processing | No objection procedure | No objection mechanism | ❌ Missing | Implement objection procedure | High | Legally Binding |
| GDPR-019 | GDPR | Art. 22 | Data subjects have right not to be subject to solely automated decisions | Human in the loop implemented | `agent3_evaluator/workflows/approval_workflow.py` requires human approval | ✅ Implemented | None | N/A | Legally Binding |
| GDPR-020 | GDPR | Art. 24 | Controller must implement appropriate technical and organizational measures | No measures implemented | No security or organizational measures | ❌ Missing | Implement technical and organizational measures | Critical | Legally Binding |
| GDPR-021 | GDPR | Art. 25 | Data protection by design and by default | No privacy by design | No default privacy measures | ❌ Missing | Implement privacy by design and default | High | Legally Binding |
| GDPR-022 | GDPR | Art. 28 | Data Processing Agreement required for processors | No external processors currently used | Only LM Studio local | ✅ Implemented | None (for current config) | N/A | Legally Binding |
| GDPR-023 | GDPR | Art. 30 | Records of processing activities must be maintained | No records maintained | No processing records | ❌ Missing | Create and maintain Records of Processing Activities | High | Legally Binding |
| GDPR-024 | GDPR | Art. 32 | Security of processing must be ensured | No security measures | No encryption, access controls | ❌ Missing | Implement security measures (encryption, access controls, etc.) | Critical | Legally Binding |
| GDPR-025 | GDPR | Art. 33 | Data breaches must be notified to supervisory authority within 72 hours | No breach notification procedure | No incident reporting | ❌ Missing | Implement breach notification procedure | High | Legally Binding |
| GDPR-026 | GDPR | Art. 34 | Data subjects must be notified of high-risk breaches | No breach notification to data subjects | No incident reporting | ❌ Missing | Implement data subject breach notification | High | Legally Binding |
| GDPR-027 | GDPR | Art. 35 | Data Protection Impact Assessment required for high-risk processing | No DPIA conducted | No DPIA documentation | ❌ Missing | Conduct DPIA before operational deployment | High | Legally Binding |
| GDPR-028 | GDPR | Art. 37 | Data Protection Officer must be appointed if required | No DPO appointed | No DPO designated | ⚠️ Partially Implemented | Assess if DPO required, appoint if needed | High | Legally Binding |

---

## 4. EU AI Act Requirements Matrix

| ID | Law/Regulation/Standard | Article/Clause | Plain Language Meaning | Applicability | Code/Architecture Evidence | Current Status | Recommended Action | Priority | Binding Nature |
|-----|-------------------------|----------------|------------------------|---------------|-----------------------------|-----------------|----------------------|----------|-----------------|
| AI-001 | EU AI Act | Art. 3(1) | AI system definition: machine-based system with autonomy, adaptability, inference | System uses LLM with LangGraph workflow | `agent3_evaluator/main.py` shows AI system architecture | ✅ Implemented | None | N/A | Legally Binding |
| AI-002 | EU AI Act | Annex III | High-risk AI systems listed | System does not fall under any high-risk category | System is for supplier qualification, not medical device | ✅ Implemented | None | N/A | Legally Binding |
| AI-003 | EU AI Act | Art. 52(1) | Transparency: users must be informed they are interacting with AI | No AI disclosure in UI | `streamlit_app.py` has no AI disclosure | ❌ Missing | Add AI disclosure to all user interfaces | Critical | Legally Binding |
| AI-004 | EU AI Act | Art. 52(2) | Deepfake disclosure required | Not applicable (no image/audio/video manipulation) | System processes text only | ✅ Implemented | None | N/A | Legally Binding |
| AI-005 | EU AI Act | Art. 14 | Human oversight required for AI systems | Human approval implemented for all decisions | `agent3_evaluator/workflows/approval_workflow.py` requires human approval | ✅ Implemented | None | N/A | Legally Binding |
| AI-006 | EU AI Act | Art. 9 | Risk management system required for providers | BEC Robotics is deployer, not provider | System is deployed, not provided | ✅ Implemented | None | N/A | Legally Binding |
| AI-007 | EU AI Act | Art. 10 | Data and data governance required | No formal data governance | No data governance policy | ❌ Missing | Implement data governance procedures | High | Legally Binding |
| AI-008 | EU AI Act | Art. 11 | Technical documentation required for providers | BEC Robotics is deployer, not provider | System is deployed, not provided | ✅ Implemented | None (for deployers) | N/A | Legally Binding |
| AI-009 | EU AI Act | Art. 12 | Record-keeping required | No formal records | No validation records | ❌ Missing | Implement record-keeping for AI operations | Medium | Legally Binding |
| AI-010 | EU AI Act | Art. 13 | Transparency to enable interpretation | No user instructions | No AI system documentation | ❌ Missing | Create user instructions explaining AI capabilities | High | Legally Binding |
| AI-011 | EU AI Act | Art. 15 | Accuracy, robustness, cybersecurity required | No formal validation | No accuracy validation | ❌ Missing | Implement accuracy validation and testing | High | Legally Binding |
| AI-012 | EU AI Act | Art. 29 | Deployer obligations: use according to instructions, ensure human oversight | Human oversight implemented, instructions not documented | Approval workflow exists, no instructions | ⚠️ Partially Implemented | Document instructions for use | Medium | Legally Binding |
| AI-013 | EU AI Act | Art. 29 | Deployer obligations: monitor operation | No monitoring procedures | No monitoring implemented | ❌ Missing | Implement monitoring procedures | Medium | Legally Binding |
| AI-014 | EU AI Act | Art. 29 | Deployer obligations: keep logs | Partial logging | Some system logs exist | ⚠️ Partially Implemented | Implement comprehensive logging | Medium | Legally Binding |
| AI-015 | EU AI Act | Art. 29 | Deployer obligations: retain logs | No retention policy | No log retention policy | ❌ Missing | Define and implement log retention policy | Medium | Legally Binding |

---

## 5. EU MDR Requirements Matrix

| ID | Law/Regulation/Standard | Article/Clause | Plain Language Meaning | Applicability | Code/Architecture Evidence | Current Status | Recommended Action | Priority | Binding Nature |
|-----|-------------------------|----------------|------------------------|---------------|-----------------------------|-----------------|----------------------|----------|-----------------|
| MDR-001 | EU MDR | Art. 2(1) | Medical device definition | System is NOT a medical device | No medical purpose, no diagnosis/treatment | ✅ Implemented | None | N/A | Legally Binding |
| MDR-002 | EU MDR | Art. 2(2) | IVD medical device definition | System is NOT an IVD medical device | No in vitro diagnostic purpose | ✅ Implemented | None | N/A | Legally Binding |
| MDR-003 | EU MDR | Art. 2(30) | Manufacturer definition | BEC Robotics is a manufacturer | BEC designs/manufactures medical devices | ✅ Implemented | None | N/A | Legally Binding |
| MDR-004 | EU MDR | Art. 10(8) | Documentation and traceability requirements | Supplier information must be documented and traceable | `agent2_vectorstore/storage/sqlite_store.py` stores supplier data | ✅ Implemented | None | N/A | Legally Binding |
| MDR-005 | EU MDR | Art. 10(9) | Quality Management System required | QMS must ensure compliance with MDR | System is part of QMS | ✅ Implemented | Perform CSV to validate system for QMS use | Critical | Legally Binding |
| MDR-006 | EU MDR | Art. 10(4) | Risk management system required | Manufacturer must establish risk management system | No formal risk management system | ❌ Missing | Implement risk management system | High | Legally Binding |
| MDR-007 | EU MDR | Art. 10(2) | Technical documentation required | Technical documentation must support conformity assessment | Evaluation reports generated | ⚠️ Partially Implemented | Integrate supplier evaluations with technical files | Medium | Legally Binding |

---

## 6. ISO 13485 Requirements Matrix

| ID | Law/Regulation/Standard | Article/Clause | Plain Language Meaning | Applicability | Code/Architecture Evidence | Current Status | Recommended Action | Priority | Binding Nature |
|-----|-------------------------|----------------|------------------------|---------------|-----------------------------|-----------------|----------------------|----------|-----------------|
| ISO-001 | ISO 13485:2016 | §1 | Scope | ISO 13485 applies to medical device QMS | BEC Robotics is medical device manufacturer | ✅ Implemented | None | N/A | Contractual |
| ISO-002 | ISO 13485:2016 | §4.1.1 | QMS establishment and maintenance | QMS must be established and maintained | BEC Robotics has QMS | ✅ Implemented | None | N/A | Contractual |
| ISO-003 | ISO 13485:2016 | §4.1.2 | Process applicability | Processes needed for QMS must be determined | Supplier qualification process defined | ✅ Implemented | None | N/A | Contractual |
| ISO-004 | ISO 13485:2016 | §4.1.3 | QMS documentation | QMS must be documented | Partial documentation exists | ⚠️ Partially Implemented | Complete QMS documentation for Pipeline | Medium | Contractual |
| ISO-005 | ISO 13485:2016 | §4.1.4 | Document control | Documents must be controlled | No formal document control | ❌ Missing | Implement document control procedures | High | Contractual |
| ISO-006 | ISO 13485:2016 | §4.1.5 | Records control | Records must be controlled | Partial record control | ⚠️ Partially Implemented | Implement record control procedures | High | Contractual |
| ISO-007 | ISO 13485:2016 | **§4.1.6** | **Computerized System Validation** | **Software used in QMS must be validated** | **No CSV performed** | ❌ Missing | **Perform CSV (Critical Gap)** | **Critical** | Contractual |
| ISO-008 | ISO 13485:2016 | §4.2.1 | QMS documentation structure | QMS documentation must include quality manual, procedures, records | Partial documentation | ⚠️ Partially Implemented | Complete QMS documentation | Medium | Contractual |
| ISO-009 | ISO 13485:2016 | §4.2.3 | Document control procedures | Document control procedures must be established | No formal procedures | ❌ Missing | Implement document control procedures | High | Contractual |
| ISO-010 | ISO 13485:2016 | §4.2.4 | Records control procedures | Records control procedures must be established | No formal procedures | ❌ Missing | Implement records control procedures | High | Contractual |
| ISO-011 | ISO 13485:2016 | **§7.4.1** | **Purchasing process** | **Supplier evaluation and control required** | **Supplier evaluation implemented** | ✅ Implemented | None | N/A | Contractual |
| ISO-012 | ISO 13485:2016 | §7.4.1 | Purchasing process - control proportional to effect | Control must be proportional to supplier effect on product | VA26 risk classes implemented | ✅ Implemented | None | N/A | Contractual |
| ISO-013 | ISO 13485:2016 | §7.4.1 | Purchasing process - evaluation and re-evaluation | Suppliers must be evaluated and re-evaluated | Evaluation implemented, re-evaluation partial | ⚠️ Partially Implemented | Implement supplier re-evaluation | High | Contractual |
| ISO-014 | ISO 13485:2016 | §7.4.2 | Purchasing information | Purchasing information must describe product and requirements | Supplier information collected | ✅ Implemented | None | N/A | Contractual |
| ISO-015 | ISO 13485:2016 | §7.4.3 | Verification of purchased product | Purchased product must be verified | Certificate verification implemented | ✅ Implemented | None | N/A | Contractual |
| ISO-016 | ISO 13485:2016 | §7.1 | Planning of product realization | Product realization processes must be planned | Supplier qualification process planned | ✅ Implemented | None | N/A | Contractual |
| ISO-017 | ISO 13485:2016 | §8.2.2 | Internal audit | Internal audits must be conducted | No internal audit procedure for Pipeline | ❌ Missing | Implement internal audit procedure | Medium | Contractual |
| ISO-018 | ISO 13485:2016 | §8.2.3 | Monitoring and measurement of processes | Processes must be monitored and measured | No formal monitoring | ❌ Missing | Implement process monitoring | Medium | Contractual |
| ISO-019 | ISO 13485:2016 | §8.5.2 | Corrective action | Corrective action procedures must be established | No corrective action procedure | ❌ Missing | Implement corrective action procedure | Medium | Contractual |
| ISO-020 | ISO 13485:2016 | §8.5.3 | Preventive action | Preventive action procedures must be established | No preventive action procedure | ❌ Missing | Implement preventive action procedure | Medium | Contractual |

---

## 7. German BDSG Requirements Matrix

| ID | Law/Regulation/Standard | Article/Clause | Plain Language Meaning | Applicability | Code/Architecture Evidence | Current Status | Recommended Action | Priority | Binding Nature |
|-----|-------------------------|----------------|------------------------|---------------|-----------------------------|-----------------|----------------------|----------|-----------------|
| BDSG-001 | BDSG | §1 | Scope - applies to processing of personal data in Germany | BEC Robotics is in Germany, processes personal data | System deployed in Germany | ✅ Implemented | None | N/A | Legally Binding |
| BDSG-002 | BDSG | §26 | Processing for employment purposes | Employee data processed for employment | Auditor names processed | ✅ Implemented | None | N/A | Legally Binding |
| BDSG-003 | BDSG | §30 | Data Protection Officer appointment | DPO required for regular and systematic monitoring | System performs regular monitoring of supplier data | ⚠️ Partially Implemented | Assess if DPO required, appoint if needed | High | Legally Binding |

---

## 8. NIS2 Directive Requirements Matrix

| ID | Law/Regulation/Standard | Article/Clause | Plain Language Meaning | Applicability | Code/Architecture Evidence | Current Status | Recommended Action | Priority | Binding Nature |
|-----|-------------------------|----------------|------------------------|---------------|-----------------------------|-----------------|----------------------|----------|-----------------|
| NIS2-001 | NIS2 Directive | Art. 3 | Scope - applies to medium and large entities in important sectors | BEC Robotics is medical device manufacturer (important sector), size unknown | System used by BEC Robotics | ⚠️ Conditional | Confirm BEC Robotics size, assess applicability | High | Conditional |
| NIS2-002 | NIS2 Directive | Art. 20 | Cybersecurity risk management | Appropriate technical, operational, and organizational measures required | No risk management implemented | ❌ Missing | Implement cybersecurity risk management | Critical | Conditional |
| NIS2-003 | NIS2 Directive | Art. 21 | Information security measures | Security measures must be implemented | No security measures implemented | ❌ Missing | Implement information security measures | Critical | Conditional |
| NIS2-004 | NIS2 Directive | Art. 22 | Supply chain security | Supply chain security measures must be implemented | No supply chain security measures | ❌ Missing | Implement supply chain security measures | Critical | Conditional |
| NIS2-005 | NIS2 Directive | Art. 23 | Incident reporting | Incidents must be reported to authorities | No incident reporting procedures | ❌ Missing | Implement incident reporting procedures | Critical | Conditional |
| NIS2-006 | NIS2 Directive | Art. 24 | Business continuity | Business continuity measures must be implemented | No business continuity plan | ❌ Missing | Implement business continuity measures | High | Conditional |

---

## 9. Trade Secrets Directive Requirements Matrix

| ID | Law/Regulation/Standard | Article/Clause | Plain Language Meaning | Applicability | Code/Architecture Evidence | Current Status | Recommended Action | Priority | Binding Nature |
|-----|-------------------------|----------------|------------------------|---------------|-----------------------------|-----------------|----------------------|----------|-----------------|
| TS-001 | Trade Secrets Directive | Art. 2(1) | Trade secret definition: secret, commercially valuable, reasonable steps | Supplier pricing, evaluation methodology may qualify | Confidential data processed | ⚠️ Conditional | Assess if information qualifies as trade secrets | Medium | Legally Binding |
| TS-002 | Trade Secrets Directive | Art. 2(1)(a) | Information must be secret | Information is not generally known | Supplier pricing, methodology not public | ✅ Implemented | None | N/A | Legally Binding |
| TS-003 | Trade Secrets Directive | Art. 2(1)(b) | Information must have commercial value | Supplier pricing, methodology have value | Confidential data has commercial value | ✅ Implemented | None | N/A | Legally Binding |
| TS-004 | Trade Secrets Directive | **Art. 2(1)(c)** | **Information must be subject to reasonable steps to keep it secret** | **No reasonable steps implemented** | **No access controls, encryption, or confidentiality measures** | ❌ Missing | **Implement reasonable steps (access controls, encryption, marking)** | **Critical** | Legally Binding |
| TS-005 | Trade Secrets Directive | Art. 4-12 | Legal remedies for misappropriation | Remedies available only if reasonable steps taken | No reasonable steps | ❌ Missing | Implement reasonable steps to enable legal protection | Critical | Legally Binding |

---

## 10. Summary Statistics

### 10.1 By Regulation/Standard

| **Regulation/Standard** | **Total Requirements** | **Implemented** | **Partially Implemented** | **Missing** | **Unknown** | **Compliance Rate** |
|-------------------------|------------------------|-----------------|---------------------------|-------------|--------------|---------------------|
| GDPR | 28 | 7 | 2 | 19 | 0 | 25% |
| EU AI Act | 15 | 4 | 2 | 9 | 0 | 27% |
| EU MDR | 7 | 5 | 1 | 1 | 0 | 71% |
| ISO 13485 | 20 | 8 | 4 | 8 | 0 | 40% |
| BDSG | 3 | 2 | 1 | 0 | 0 | 67% |
| NIS2 | 6 | 0 | 0 | 6 | 0 | 0% |
| Trade Secrets Directive | 5 | 2 | 0 | 3 | 0 | 40% |
| **TOTAL** | **84** | **28** | **9** | **46** | **0** | **33%** |

### 10.2 By Compliance Status

| **Status** | **Count** | **Percentage** |
|------------|-----------|----------------|
| ✅ Implemented | 28 | 33% |
| ⚠️ Partially Implemented | 9 | 11% |
| ❌ Missing | 46 | 55% |
| ❓ Unknown | 0 | 0% |
| **TOTAL** | **83** | **100%** |

**Note**: One requirement (GDPR-001) is counted as implemented but is a scope requirement, not an operational requirement.

### 10.3 By Priority

| **Priority** | **Count** | **Percentage** |
|--------------|-----------|----------------|
| Critical | 20 | 24% |
| High | 30 | 36% |
| Medium | 25 | 30% |
| Low | 0 | 0% |
| **TOTAL** | **75** | **100%** |

**Note**: Only actionable requirements (those with "Missing" or "Partially Implemented" status) are counted.

### 10.4 By Binding Nature

| **Binding Nature** | **Count** | **Percentage** |
|---------------------|-----------|----------------|
| Legally Binding | 60 | 71% |
| Conditional | 12 | 14% |
| Contractual | 12 | 14% |
| Voluntary | 0 | 0% |
| **TOTAL** | **84** | **100%** |

---

## 11. Compliance Dashboard

### 11.1 Critical Gaps (Immediate Action Required)

| **ID** | **Requirement** | **Regulation** | **Risk** | **Priority** |
|--------|----------------|----------------|----------|--------------|
| ISO-007 | Computerized System Validation | ISO 13485:2016 §4.1.6 | Non-compliance with QMS requirements, audit failure | Critical |
| TS-004 | Reasonable steps to protect trade secrets | Trade Secrets Directive Art. 2(1)(c) | Loss of legal protection for trade secrets | Critical |
| GDPR-003 | Lawfulness, fairness, and transparency | GDPR Art. 5(1)(a) | Transparency violation, user rights | Critical |
| GDPR-005 | Data minimization | GDPR Art. 5(1)(c) | Excessive data processing | Critical |
| GDPR-007 | Storage limitation | GDPR Art. 5(1)(e) | Indefinite data retention | Critical |
| GDPR-008 | Integrity and confidentiality | GDPR Art. 5(1)(f) | Security vulnerabilities | Critical |
| GDPR-015 | Right to erasure | GDPR Art. 17 | Non-compliance with data subject rights | Critical |
| GDPR-020 | Appropriate technical and organizational measures | GDPR Art. 24 | Non-compliance with security requirements | Critical |
| GDPR-024 | Security of processing | GDPR Art. 32 | Security vulnerabilities | Critical |
| AI-003 | Transparency obligations | EU AI Act Art. 52(1) | Non-compliance with transparency requirements | Critical |
| NIS2-002 | Cybersecurity risk management | NIS2 Art. 20 | Non-compliance with cybersecurity requirements | Critical |
| NIS2-003 | Information security measures | NIS2 Art. 21 | Non-compliance with security requirements | Critical |
| NIS2-004 | Supply chain security | NIS2 Art. 22 | Non-compliance with supply chain security | Critical |
| NIS2-005 | Incident reporting | NIS2 Art. 23 | Non-compliance with incident reporting | Critical |

### 11.2 High Priority Gaps

| **ID** | **Requirement** | **Regulation** | **Risk** | **Priority** |
|--------|----------------|----------------|----------|--------------|
| GDPR-006 | Accuracy | GDPR Art. 5(1)(d) | Inaccurate data | High |
| GDPR-009 | Accountability | GDPR Art. 5(2) | Non-compliance with accountability | High |
| GDPR-012 | Information to data subjects | GDPR Art. 13, 14 | Non-compliance with transparency | High |
| GDPR-013 | Right of access | GDPR Art. 15 | Non-compliance with data subject rights | High |
| GDPR-014 | Right to rectification | GDPR Art. 16 | Non-compliance with data subject rights | High |
| GDPR-016 | Right to restriction | GDPR Art. 18 | Non-compliance with data subject rights | High |
| GDPR-018 | Right to object | GDPR Art. 21 | Non-compliance with data subject rights | High |
| GDPR-023 | Records of processing activities | GDPR Art. 30 | Non-compliance with documentation | High |
| GDPR-025 | Breach notification to authority | GDPR Art. 33 | Non-compliance with breach notification | High |
| GDPR-026 | Breach notification to data subjects | GDPR Art. 34 | Non-compliance with breach notification | High |
| GDPR-027 | Data Protection Impact Assessment | GDPR Art. 35 | Non-compliance with DPIA requirement | High |
| GDPR-028 | Data Protection Officer | GDPR Art. 37 | Non-compliance with DPO requirement | High |
| AI-007 | Data and data governance | EU AI Act Art. 10 | Non-compliance with data governance | High |
| AI-010 | Transparency to enable interpretation | EU AI Act Art. 13 | Non-compliance with transparency | High |
| AI-011 | Accuracy, robustness, cybersecurity | EU AI Act Art. 15 | Non-compliance with quality requirements | High |
| AI-015 | Log retention | EU AI Act Art. 29 | Non-compliance with record-keeping | High |
| MDR-006 | Risk management system | EU MDR Art. 10(4) | Non-compliance with risk management | High |
| ISO-005 | Document control | ISO 13485:2016 §4.1.4 | Non-compliance with QMS documentation | High |
| ISO-006 | Records control | ISO 13485:2016 §4.1.5 | Non-compliance with QMS records | High |
| ISO-013 | Supplier evaluation and re-evaluation | ISO 13485:2016 §7.4.1 | Non-compliance with purchasing controls | High |
| BDSG-003 | Data Protection Officer | BDSG §30 | Non-compliance with DPO requirement | High |
| NIS2-006 | Business continuity | NIS2 Art. 24 | Non-compliance with business continuity | High |

### 11.3 Medium Priority Gaps

| **ID** | **Requirement** | **Regulation** | **Risk** | **Priority** |
|--------|----------------|----------------|----------|--------------|
| GDPR-017 | Right to data portability | GDPR Art. 20 | Reduced data subject rights | Medium |
| AI-008 | Technical documentation | EU AI Act Art. 11 | Audit risk | Medium |
| AI-009 | Record-keeping | EU AI Act Art. 12 | Audit risk | Medium |
| AI-012 | Deployer obligations - use according to instructions | EU AI Act Art. 29 | Operational risk | Medium |
| AI-013 | Deployer obligations - monitor operation | EU AI Act Art. 29 | Operational risk | Medium |
| AI-014 | Deployer obligations - keep logs | EU AI Act Art. 29 | Audit risk | Medium |
| MDR-007 | Technical documentation | EU MDR Art. 10(2) | Documentation gaps | Medium |
| ISO-004 | QMS documentation | ISO 13485:2016 §4.1.3 | Documentation gaps | Medium |
| ISO-008 | QMS documentation structure | ISO 13485:2016 §4.2.1 | Documentation gaps | Medium |
| ISO-017 | Internal audit | ISO 13485:2016 §8.2.2 | Audit risk | Medium |
| ISO-018 | Monitoring and measurement of processes | ISO 13485:2016 §8.2.3 | Operational risk | Medium |
| ISO-019 | Corrective action | ISO 13485:2016 §8.5.2 | Operational risk | Medium |
| ISO-020 | Preventive action | ISO 13485:2016 §8.5.3 | Operational risk | Medium |

---

**Next Document**: [11_IMPLEMENTATION_GAPS.md](11_IMPLEMENTATION_GAPS.md) - Identified implementation and compliance gaps
**Previous Document**: [09_LOCAL_vs_EXTERNAL_LLM.md](09_LOCAL_vs_EXTERNAL_LLM.md) - Local vs external LLM comparison