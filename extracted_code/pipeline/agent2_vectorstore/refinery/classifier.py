"""
Document Classifier
===================
Rule-based document type detection for supplier documents.

Classifies documents into types like:
- quality_report: Quality audit reports, QMS documents
- certificate: ISO certificates, accreditation docs
- audit: Internal/external audit reports
- purchase_order: Purchase orders, delivery notes
- nc_report: Nonconformance reports, CAPA records
- risk_assessment: FMEA, risk analysis documents
- other: Unrecognized document types

The classifier provides an initial guess that Phase 2 (LLM extractor)
can confirm or override.

Usage:
    from refinery.classifier import classify_document
    doc_type = classify_document(markdown_text)
"""

import re

# Classification patterns (German + English)
# Order matters: more specific patterns first

_CLASSIFICATION_RULES = [
    # Certificate patterns
    {
        "doc_type": "certificate",
        "patterns": [
            r"\bzertifikat\b",
            r"\bzertifizierung\b",
            r"\bcertificate\b",
            r"\bcertification\b",
            r"\biso\s*9001\b",
            r"\biso\s*13485\b",
            r"\bce.mark\b",
            r"\bce.konformit[aä]tserkl[aä]rung\b",
            r"\bakreditierung\b",
            r"\baccreditation\b",
            r"\bregistration.certificate\b",
            r"\bvalid.until\b.*\d{4}",
            r"\bg[uü]ltig.bis\b.*\d{4}",
            r"\bcertificate.number\b",
            r"\bzertifikatsnummer\b",
        ],
        "weight": 3,  # Cert docs are distinctive
    },
    # Nonconformance / CAPA
    {
        "doc_type": "nc_report",
        "patterns": [
            r"\bnonconformance.report\b",
            r"\bnc.report\b",
            r"\bncr\b",
            r"\bcapa\b",
            r"\bcorrective.action\b",
            r"\bpreventive.action\b",
            r"\bkorrekturma[sß]nahme\b",
            r"\bvorbeugende.ma[sß]nahme\b",
            r"\babweichungsbericht\b",
            r"\breklamation\b",
            r"\bbeanstandung\b",
            r"\b8d.report\b",
            r"\broot.cause\b",
        ],
        "weight": 2,
    },
    # Risk assessment / FMEA
    {
        "doc_type": "risk_assessment",
        "patterns": [
            r"\bfmea\b",
            r"\bfmeca\b",
            r"\brisk.assessment\b",
            r"\brisikobeurteilung\b",
            r"\brisikoanalyse\b",
            r"\bhazard.analysis\b",
            r"\biso.14971\b",
            r"\bseverity.*occurrence.*detectability\b",
            r"\bschweregrad.*auftretenswahrscheinlichkeit",
            r"\brpn\b",
            r"\brisk.priority.number\b",
            r"\bgef[aä]hrdungsbeurteilung\b",
        ],
        "weight": 2,
    },
    # Audit report
    {
        "doc_type": "audit",
        "patterns": [
            r"\baudit.report\b",
            r"\bauditbericht\b",
            r"\binternal.audit\b",
            r"\binternal.audit\b",
            r"\bexterne.audit\b",
            r"\bexternal.audit\b",
            r"\baudit.finding\b",
            r"\bauditbefund\b",
            r"\bprocess.audit\b",
            r"\bproduct.audit\b",
            r"\bsystemaudit\b",
            r"\baudit.zertifikat\b",
        ],
        "weight": 2,
    },
    # Purchase order
    {
        "doc_type": "purchase_order",
        "patterns": [
            r"\bpurchase.order\b",
            r"\bbestellung\b",
            r"\bliefervertrag\b",
            r"\border.confirmation\b",
            r"\bAuftragsbest[aä]tigung\b",
            r"\binvoice\b",
            r"\brechnung\b",
            r"\bdelivery.note\b",
            r"\blieferschein\b",
            r"\bpacking.list\b",
            r"\bquantity.*price.*amount\b",
            r"\bmenge.*preis.*betrag\b",
            r"\bpo.number\b",
            r"\bbestellnummer\b",
        ],
        "weight": 2,
    },
    # Quality Assurance Agreement — required evidence for VA26 measures
    # at every risk class (1-3). Kept distinct from quality_report/certificate
    # since it's a specific legal document type Agent 3 checks for.
    {
        "doc_type": "quality_agreement",
        "patterns": [
            r"\bquality.assurance.agreement\b",
            r"\bqualit[aä]tssicherungsvereinbarung\b",
            r"\bqaa\b",
            r"\bfb29\b",
            r"\bqmd000065\b",
            r"\bquality.agreement\b",
            r"\bsupply.agreement\b.*\bquality\b",
            r"\bvereinbarung\b.*\bqualit[aä]t\b",
            r"\bminimum.contents.*qaa\b",
            r"\bcl08\b",
        ],
        "weight": 3,  # distinctive legal document, similar specificity to certificates
    },
    # Quality report (broader, lower weight to avoid false positives)
    {
        "doc_type": "quality_report",
        "patterns": [
            r"\bquality.report\b",
            r"\bqualitaetsbericht\b",
            r"\bquality.management.system\b",
            r"\bqualitaetsmanagementsystem\b",
            r"\bqms\b",
            r"\bprocess.control\b",
            r"\bprozesslenkung\b",
            r"\bcorrective.*preventive\b",
            r"\bmanagement.review\b",
            r"\bleitungsreview\b",
            r"\bkey.performance.indicator\b",
            r"\bkenngro[sß]e\b",
        ],
        "weight": 1,
    },
]


def classify_document(text: str) -> str:
    """
    Classify a document based on its text content.

    Uses weighted pattern matching across German and English terms.
    Returns the doc_type with the highest weighted score.

    Args:
        text: Full document text (markdown)

    Returns:
        Document type string (e.g., 'certificate', 'nc_report', 'quality_report', 'other')
    """
    if not text or not text.strip():
        return "other"

    text_lower = text.lower()
    scores: dict[str, float] = {}

    for rule in _CLASSIFICATION_RULES:
        doc_type = rule["doc_type"]
        weight = rule["weight"]
        score = 0.0

        for pattern in rule["patterns"]:
            matches = re.findall(pattern, text_lower)
            score += len(matches) * weight

        if score > 0:
            scores[doc_type] = scores.get(doc_type, 0) + score

    if not scores:
        return "other"

    return max(scores, key=scores.get)


def classify_document_with_confidence(text: str) -> dict:
    """
    Classify document and return confidence information.

    Returns:
        {
            "doc_type": str,
            "confidence": str,  # "high", "medium", "low"
            "all_scores": dict,  # All type scores
        }
    """
    if not text or not text.strip():
        return {"doc_type": "other", "confidence": "low", "all_scores": {}}

    text_lower = text.lower()
    scores: dict[str, float] = {}

    for rule in _CLASSIFICATION_RULES:
        doc_type = rule["doc_type"]
        weight = rule["weight"]
        score = 0.0

        for pattern in rule["patterns"]:
            matches = re.findall(pattern, text_lower)
            score += len(matches) * weight

        if score > 0:
            scores[doc_type] = scores.get(doc_type, 0) + score

    if not scores:
        return {"doc_type": "other", "confidence": "low", "all_scores": {}}

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]
    total_score = sum(scores.values())
    ratio = best_score / total_score if total_score > 0 else 0

    if ratio > 0.6:
        confidence = "high"
    elif ratio > 0.35:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "doc_type": best_type,
        "confidence": confidence,
        "all_scores": scores,
    }
