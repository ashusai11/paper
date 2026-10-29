"""
VA26 Rule Definitions
=====================
Executable rules extracted from QMD000035 Rev. 06.
Every constant here maps to a specific VA26 section reference.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

# ─────────────────────────────────────────────────────────────────
# Risk Class Definitions (VA26 §2.1.5)
# ─────────────────────────────────────────────────────────────────

class RiskClass(str, Enum):
    CLASS_1 = "1"
    CLASS_2 = "2"
    CLASS_3 = "3"

class SupplierCriticality(str, Enum):
    CRITICAL   = "critical"
    NONCRITICAL = "noncritical"

class InternalControl(str, Enum):
    HIGH = "high"
    LOW  = "low"

# ─────────────────────────────────────────────────────────────────
# VA26 §2.1.5 — Minimum Criteria per Risk Class + Supplier Type
# ─────────────────────────────────────────────────────────────────

class Measure(str, Enum):
    CONTRACTUAL_AGREEMENT   = "contractual_agreement"   # §2.1.1.1 Measure 1
    SUPPLIER_AUDIT        = "supplier_audit"        # §2.1.1.1 Measure 2
    QAA_OR_CONTRACT       = "qaa_or_contract"        # §2.1.1.1 Measure 3
    CERT_EVIDENCE         = "cert_evidence"          # §2.1.1.1 Measure 4
    VALUE_CHAIN           = "value_chain_audit"      # §2.1.1.1 Measure 5
    RISK_ANALYSIS         = "risk_analysis"          # §2.1.1.1 Measure 6
    ECONOMIC_EVAL         = "economic_evaluation"    # §2.1.1.1 Measure 7
    SAMPLE_TESTING        = "sample_testing"         # §2.1.1.1 Measure 4
    COMPLAINT_EVAL        = "complaint_evaluation"  # §2.1.1.1 Measure 4
    STAFF_QUALIFICATIONS  = "staff_qualifications"  # §2.1.1.1 Measure 8
    GTC                   = "gtc"                    # §2.1.1.1 Measure 1 (Class 2/3)
    TEST_RESULT_ANALYSIS  = "test_result_analysis"  # §2.1.1.1 Measure 4


@dataclass
class CriteriaSet:
    """A set of measures required for a specific supplier classification."""
    risk_class: RiskClass
    supplier_type: SupplierCriticality
    required: list[Measure] = field(default_factory=list)


# Per VA26 §2.1.5 risk class tables
CRITERIA_TABLE: list[CriteriaSet] = [
    # ── Class 1 ── Ready-to-sell MD, or Critical + LOW internal control
    CriteriaSet(
        risk_class=RiskClass.CLASS_1,
        supplier_type=SupplierCriticality.CRITICAL,
        required=[
            Measure.CONTRACTUAL_AGREEMENT,
            Measure.QAA_OR_CONTRACT,
            Measure.CERT_EVIDENCE,
            Measure.SAMPLE_TESTING,
            Measure.COMPLAINT_EVAL,
            Measure.ECONOMIC_EVAL,
            Measure.SUPPLIER_AUDIT,
        ],
    ),
    # ── Class 2 ── Critical + HIGH internal control
    CriteriaSet(
        risk_class=RiskClass.CLASS_2,
        supplier_type=SupplierCriticality.CRITICAL,
        required=[
            Measure.QAA_OR_CONTRACT,
            Measure.COMPLAINT_EVAL,
            Measure.ECONOMIC_EVAL,
            Measure.TEST_RESULT_ANALYSIS,
        ],
    ),
    # ── Class 2 ── Non-critical + HIGH internal control
    CriteriaSet(
        risk_class=RiskClass.CLASS_2,
        supplier_type=SupplierCriticality.NONCRITICAL,
        required=[
            Measure.GTC,
            Measure.COMPLAINT_EVAL,
            Measure.ECONOMIC_EVAL,
            Measure.TEST_RESULT_ANALYSIS,
        ],
    ),
    # ── Class 3 ── Non-critical (any internal control level)
    CriteriaSet(
        risk_class=RiskClass.CLASS_3,
        supplier_type=SupplierCriticality.NONCRITICAL,
        required=[
            Measure.GTC,
            Measure.ECONOMIC_EVAL,
        ],
    ),
]


def get_criteria_set(
    risk_class: RiskClass,
    supplier_type: SupplierCriticality,
) -> CriteriaSet | None:
    """Return the required measures for a given classification."""
    for cs in CRITERIA_TABLE:
        if cs.risk_class == risk_class and cs.supplier_type == supplier_type:
            return cs
    return None


# ─────────────────────────────────────────────────────────────────
# VA26 §2.2.2 — Economic Evaluation
# ─────────────────────────────────────────────────────────────────

@dataclass
class EconomicCriterion:
    name: str
    va26_ref: str
    weight: int
    field_key: str  # maps to purchase_history / profile_facts


# VA26 §2.2.2 — 6 criteria with weights
ECONOMIC_CRITERIA: list[EconomicCriterion] = [
    EconomicCriterion(
        name="Overall quality of product/service",
        va26_ref="§2.2.2 #1",
        weight=2,
        field_key="quality_score",
    ),
    EconomicCriterion(
        name="Frequency of complaints",
        va26_ref="§2.2.2 #2",
        weight=2,
        field_key="complaint_score",
    ),
    EconomicCriterion(
        name="Delivery reliability",
        va26_ref="§2.2.2 #3",
        weight=1,
        field_key="delivery_score",
    ),
    EconomicCriterion(
        name="Offer creation speed",
        va26_ref="§2.2.2 #4",
        weight=1,
        field_key="offer_score",
    ),
    EconomicCriterion(
        name="Prices",
        va26_ref="§2.2.2 #5",
        weight=1,
        field_key="price_score",
    ),
    EconomicCriterion(
        name="Cooperation",
        va26_ref="§2.2.2 #6",
        weight=1,
        field_key="cooperation_score",
    ),
]

ECONOMIC_WEIGHT_SUM = sum(c.weight for c in ECONOMIC_CRITERIA)  # 8


@dataclass
class EconomicClass:
    """VA26 §2.2.2 A/B/C classification."""
    letter: Literal["A", "B", "C"]
    range_label: str
    va26_ref: str = "§2.2.2"


ECONOMIC_CLASSES: list[EconomicClass] = [
    EconomicClass(letter="A", range_label="1.0 – 3.0"),
    EconomicClass(letter="B", range_label="3.1 – 5.0"),
    EconomicClass(letter="C", range_label="5.1 – 6.0"),
]


def classify_economic(weighted_score: float) -> EconomicClass:
    """
    VA26 §2.2.2: Classify weighted average into A/B/C.
    Scale: 1 (best) to 6 (worst).
    """
    if weighted_score <= 3.0:
        return ECONOMIC_CLASSES[0]  # A
    elif weighted_score <= 5.0:
        return ECONOMIC_CLASSES[1]  # B
    else:
        return ECONOMIC_CLASSES[2]  # C


# ─────────────────────────────────────────────────────────────────
# VA26 §3.2 — Monitoring Intervals
# ─────────────────────────────────────────────────────────────────

@dataclass
class MonitoringInterval:
    risk_class: RiskClass
    economic_class: str  # "A" | "B" | "C"
    months: int


MONITORING_INTERVALS: list[MonitoringInterval] = [
    # Class 1
    MonitoringInterval(RiskClass.CLASS_1, "A", 12),
    MonitoringInterval(RiskClass.CLASS_1, "B",  6),
    MonitoringInterval(RiskClass.CLASS_1, "C",  3),
    # Class 2
    MonitoringInterval(RiskClass.CLASS_2, "A", 12),
    MonitoringInterval(RiskClass.CLASS_2, "B",  6),
    MonitoringInterval(RiskClass.CLASS_2, "C",  3),
    # Class 3
    MonitoringInterval(RiskClass.CLASS_3, "A", 24),
    MonitoringInterval(RiskClass.CLASS_3, "B", 12),
    MonitoringInterval(RiskClass.CLASS_3, "C",  6),
]


def get_monitoring_interval(risk_class: RiskClass, economic_class: str) -> int:
    """Return monitoring interval in months per VA26 §6."""
    for mi in MONITORING_INTERVALS:
        if mi.risk_class == risk_class and mi.economic_class == economic_class:
            return mi.months
    return 12  # default


# ─────────────────────────────────────────────────────────────────
# VA26 §2.1.1.1 Measure 3 — QAA Requirements
# ─────────────────────────────────────────────────────────────────

# VA26 §2.1.4 — QAA mandatory for Class 1 and 2 critical suppliers
QAA_MANDATORY_FOR: list[tuple[RiskClass, SupplierCriticality]] = [
    (RiskClass.CLASS_1, SupplierCriticality.CRITICAL),
    (RiskClass.CLASS_2, SupplierCriticality.CRITICAL),
]

# For Class 2 non-critical and Class 3: GTC acceptable as fallback
GTC_ACCEPTABLE_FOR: list[tuple[RiskClass, SupplierCriticality]] = [
    (RiskClass.CLASS_2, SupplierCriticality.NONCRITICAL),
    (RiskClass.CLASS_3, SupplierCriticality.NONCRITICAL),
]


# ─────────────────────────────────────────────────────────────────
# VA26 §2.1.1.1 Measure 2 — Audit required
# ─────────────────────────────────────────────────────────────────

# Audit required for: Class 1 critical (especially for outsourced processes)
AUDIT_REQUIRED_FOR: list[tuple[RiskClass, SupplierCriticality]] = [
    (RiskClass.CLASS_1, SupplierCriticality.CRITICAL),
]
