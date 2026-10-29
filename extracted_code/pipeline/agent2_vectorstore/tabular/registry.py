"""The table registry — the contract between a spreadsheet and your SQLite tables.

Everything here is data, not code: you can edit
`<data_dir>/table_registry.json` to teach the pipeline a new sheet layout
without touching Python. If the file does not exist it is created from
`DEFAULT_REGISTRY` on first use.

Per target you define:
    kind            how rows are written ("purchase_history" | "supplier_profile"
                    | "raw_records")
    table           the SQLite table that receives the rows
    natural_key     columns that identify a row (used for idempotent re-import)
    on_existing     "update" | "skip" | "error" when the natural key already exists
    fields          canonical field -> type / required / aliases
    enum_values     free text -> canonical value (DE + EN aliases)

`routes` are optional rules that shortcut routing when the header is
ambiguous (e.g. file name "buy_history_2024.csv" -> purchase_history).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

_SUPPLIER_IDENTITY_FIELDS = {
    "legal_name": {
        "type": "text", "required": True,
        "aliases": ["legal name", "supplier name", "name", "firma",
                    "firmenname", "lieferant", "lieferant name",
                    "lieferantennname", "company", "unternehmen",
                    "legal entity", "supplier"],
    },
    "country": {
        "type": "text",
        "aliases": ["country", "land", "country code", "staatsangehoerigkeit",
                    "staat", "country of origin"],
    },
    "address": {
        "type": "text",
        "aliases": ["address", "adresse", "strasse", "straße", "street",
                    "anschrift", "strasse und hausnummer"],
    },
    "website": {
        "type": "text",
        "aliases": ["website", "url", "webseite", "homepage", "www"],
    },
    "supplier_type": {
        "type": "text",
        "aliases": ["supplier type", "type", "lieferantentyp", "typ",
                    "category", "kategorie"],
    },
    "notes": {
        "type": "text",
        "aliases": ["notes", "note", "comment", "bemerkung", "remark"],
    },
}


DEFAULT_REGISTRY: dict[str, Any] = {
    "version": 1,
    "decimal_separator": "auto",   # "auto" | "." | ","
    "dayfirst": True,              # 01.03.2024 = 1 March
    "fallback_target": "tabular_records",
    "targets": {
        "purchase_history": {
            "kind": "purchase_history",
            "table": "purchase_history",
            "priority": 10,
            "label": "Purchase history (orders / deliveries)",
            "description": (
                "Order-level records: purchase date, order reference, product, "
                "quantity, amount, currency, delivery status, quality issue."
            ),
            "natural_key": ["purchase_reference"],
            # A row is identified by reference AND date: some ERPs reuse the
            # same order number for several orders, and those are separate
            # orders, not updates of each other.
            "match_fields": ["purchase_reference", "purchase_date"],
            "on_existing": "update",
            # Files that list MANY vendors (ERP exports) attribute every row
            # to the supplier named in this field instead of to the supplier
            # the file was uploaded for. The uploaded supplier stays the
            # context (the buying company).
            "row_supplier_field": "supplier_name",
            "fields": {
                "purchase_date": {
                    "type": "date", "required": True,
                    "aliases": ["purchase date", "order date", "date", "datum",
                                "bestelldatum", "lieferdatum", "delivery date",
                                "belegdatum", "rechnungsdatum", "order date",
                                "date of delivery", "bestaetigungsdatum",
                                "order deadline", "deadline", "due date",
                                "expected delivery date", "requested date",
                                "liefertermin", "termin", "auftragsdatum"],
                },
                "purchase_reference": {
                    "type": "text", "required": True,
                    "aliases": ["purchase reference", "order number", "order no",
                                "reference", "po number", "po", "bestellnummer",
                                "bestell nr", "belegnummer", "vorgangsnummer",
                                "ref", "purchase order number", "bestellung",
                                "order reference", "order ref", "po reference",
                                "purchase order", "order id", "beleg"],
                },
                "product_or_service": {
                    "type": "text",
                    "aliases": ["product", "product or service", "article",
                                "material", "artikel", "produkt", "ware",
                                "bezeichnung", "description", "item",
                                "bezeichnung der ware", "service"],
                },
                "quantity": {
                    "type": "number",
                    "aliases": ["quantity", "qty", "menge", "anzahl", "stueck",
                                "stück", "stk", "menge in stueck"],
                },
                "amount": {
                    "type": "number",
                    "aliases": ["amount", "value", "total", "price", "summe",
                                "gesamtbetrag", "betrag", "preis",
                                "rechnungsbetrag", "warenwert", "order value",
                                "total amount", "gross amount", "bruttobetrag",
                                "gesamtpreis", "amount total", "total price",
                                "brutto"],
                },
                "currency": {
                    "type": "text",
                    "aliases": ["currency", "waehrung", "währung", "ccy",
                                "waehrung eur", "currency code"],
                },
                "delivery_status": {
                    "type": "enum",
                    "aliases": ["delivery status", "status", "lieferstatus",
                                "lieferstatus des auftrags", "delivery",
                                "fulfillment", "zahlungsstatus", "state"],
                },
                "quality_issue": {
                    "type": "bool",
                    "aliases": ["quality issue", "quality problems", "nonconformance",
                                "qualitaetsproblem", "qualitätsproblem",
                                "beanstandung", "qm issue", "reklamation", "ncr",
                                "quality complaint", "abweichung"],
                },
                "notes": {
                    "type": "text",
                    "aliases": ["notes", "note", "comment", "bemerkung",
                                "kommentar", "anmerkung", "bemerkungen",
                                "abweichungsbeschreibung"],
                },
                # --- metadata-only fields (no column in purchase_history) ---
                # They are mapped, stored in the row payload and indexed for
                # search, but they are not written into the SQL table.
                "supplier_name": {
                    "type": "text", "table_column": False,
                    "aliases": ["vendor", "supplier", "supplier name",
                                "vendor name", "lieferant", "lieferantenname",
                                "lieferant name", "partner", "lieferanten",
                                "kunde", "vendor company"],
                },
                "net_amount": {
                    "type": "number", "table_column": False,
                    "aliases": ["untaxed amount", "net amount", "subtotal",
                                "netto", "nettobetrag", "value excl vat",
                                "amount untaxed", "amount before vat"],
                },
                "buyer": {
                    "type": "text", "table_column": False,
                    "aliases": ["buyer", "einkaeufer", "einkäufer", "requester",
                                "requested by", "kaeufer", "käufer"],
                },
                "company": {
                    "type": "text", "table_column": False,
                    "aliases": ["company", "unternehmen", "gesellschaft",
                                "our company", "besteeller",
                                "besteellendes unternehmen"],
                },
                "priority": {
                    "type": "text", "table_column": False,
                    "aliases": ["priority", "prio", "prioritaet", "priorität"],
                },
                "billing_status": {
                    "type": "enum", "table_column": False,
                    "aliases": ["billing status", "invoice status",
                                "rechnungsstatus", "billing state",
                                "rechnungsstatus der bestellung"],
                },
                "order_status": {
                    "type": "enum", "table_column": False,
                    "aliases": ["order status", "po status", "auftragsstatus",
                                "status of the order", "purchase order status"],
                },
            },
            "enum_values": {
                "delivery_status": {
                    "delivered": "delivered", "complete": "delivered",
                    "komplett": "delivered", "erfuellt": "delivered",
                    "erfüllt": "delivered", "shipped": "shipped",
                    "versandt": "shipped", "dispatched": "shipped",
                    "in transit": "in_transit", "unterwegs": "in_transit",
                    "open": "open", "offen": "open", "pending": "open",
                    "late": "late", "delayed": "late", "verspaetet": "late",
                    "verspätet": "late", "returned": "returned",
                    "retour": "returned", "ruecksendung": "returned",
                    "disputed": "disputed", "reklamiert": "disputed",
                    "cancelled": "cancelled", "canceled": "cancelled",
                    "storno": "cancelled", "rejected": "rejected",
                    "draft": "draft", "purchase": "ordered",
                    "waiting for dept approval": "pending_approval",
                    "sent": "ordered", "confirmed": "ordered",
                    "to approve": "pending_approval", "done": "delivered",
                },
                "order_status": {
                    "draft": "draft", "purchase": "ordered", "sent": "ordered",
                    "confirmed": "ordered", "cancelled": "cancelled",
                    "rejected": "rejected",
                },
                "billing_status": {
                    "fully billed": "fully_billed", "billed": "fully_billed",
                    "nothing to bill": "not_billed", "not billed": "not_billed",
                    "waiting bills": "waiting_for_bill",
                    "waiting for bills": "waiting_for_bill",
                    "to bill": "to_bill",
                },
            },
        },
        "supplier_master": {
            "kind": "supplier_profile",
            "table": "company_profile",
            "priority": 10,
            "label": "Supplier master data (single supplier -> company_profile)",
            "description": (
                "One row per supplier: legal name, country, address, website, "
                "supplier type, notes. Use for a file that describes the "
                "supplier you are currently qualifying. Files that list MANY "
                "suppliers are routed to `supplier_directory` automatically."
            ),
            "natural_key": ["legal_name"],
            "on_existing": "update",
            "fields": _SUPPLIER_IDENTITY_FIELDS,
        },
        "supplier_directory": {
            "kind": "supplier_directory",
            "table": "supplier_directory",
            "priority": 5,
            "label": "Supplier directory (many suppliers -> one table)",
            "description": (
                "Master lists that contain many suppliers. One row per "
                "supplier with full provenance, kept apart from "
                "`company_profile` so a list can never overwrite the profile "
                "of the supplier under review."
            ),
            "natural_key": ["legal_name"],
            "on_existing": "update",
            "fields": _SUPPLIER_IDENTITY_FIELDS,
        },
        # ── the common entry point: any spreadsheet, not only financial ──────
        # Everything below is a registry entry — no Python per target. The
        # engine creates the table on first import (schema-on-demand).
        "risk_matrix": {
            "kind": "generic",
            "table": "risk_matrix",
            "priority": 8,
            "label": "Risk matrix / FMEA (per risk analysis)",
            "description": (
                "Process or product risks with severity, occurrence and "
                "detection. RPN and the risk level are computed in Python "
                "(never by an LLM) and the thresholds are configurable here."
            ),
            "natural_key": ["process_item", "failure_mode"],
            "match_fields": ["process_item", "failure_mode"],
            "on_existing": "update",
            "facts": [
                {
                    "category": "risk",
                    "field_name": "risk_signal",
                    "value": "{process_item} / {failure_mode} ({risk_level}, RPN {rpn})",
                    "fact_key": "process_item|failure_mode",
                    "confidence": 0.8,
                }
            ],
            "fields": {
                "process_item": {
                    "type": "text", "required": True,
                    "aliases": ["process item", "item", "process", "activity",
                                "prozessschritt", "process step", "bauteil",
                                "function", "funktion", "item / process",
                                "process item / function", "application"],
                },
                "failure_mode": {
                    "type": "text", "required": True,
                    "aliases": ["failure mode", "fehlerart", "failure",
                                "mode of failure", "fehlermodus", "risiko",
                                "risk", "potential failure", "moeglicher fehler",
                                "failure mode / effect"],
                },
                "severity": {
                    "type": "score", "required": True, "min": 1, "max": 10,
                    "sql_type": "INTEGER",
                    "aliases": ["severity", "s", "schweregrad", "severity s",
                                "s (1-10)", "schweregrad s", "auswirkung",
                                "impact", "effect"],
                },
                "occurrence": {
                    "type": "score", "required": True, "min": 1, "max": 10,
                    "sql_type": "INTEGER",
                    "aliases": ["occurrence", "o", "auftretenswahrscheinlichkeit",
                                "occurrence o", "o (1-10)",
                                "eintrittswahrscheinlichkeit", "likelihood"],
                },
                "detection": {
                    "type": "score", "required": True, "min": 1, "max": 10,
                    "sql_type": "INTEGER",
                    "aliases": ["detection", "d", "entdeckungsgrad",
                                "detektionsgrad", "detection d", "erkennbarkeit",
                                "d (1-10)", "detectability"],
                },
                "rpn": {
                    "type": "computed", "compute": "rpn", "sql_type": "INTEGER",
                    "factors": ["severity", "occurrence", "detection"],
                    "aliases": ["rpn", "risk priority number", "rpn score"],
                },
                "risk_level": {
                    "type": "computed", "compute": "threshold_level",
                    "source": "rpn",
                    "thresholds": [
                        {"max": 39, "value": "low"},
                        {"max": 99, "value": "medium"},
                        {"value": "high"},
                    ],
                    "aliases": ["risk level", "risk classification", "risikostufe",
                                "risikoklasse", "classification"],
                },
                "current_measures": {
                    "type": "text",
                    "aliases": ["current measures", "measures", "action",
                                "risk control", "vorhandene massnahmen",
                                "schutzmassnahmen", "reaktionsplan",
                                "existing measures", "derzeitige massnahmen"],
                },
                "recommended_action": {
                    "type": "text",
                    "aliases": ["recommended action", "recommended measures",
                                "action to take", "empfohlene massnahmen",
                                "korrekturmassnahme", "recommended action / measures",
                                "action recommended"],
                },
                "responsibility": {
                    "type": "text",
                    "aliases": ["responsibility", "responsible", "owner",
                                "verantwortlich", "zustandig", "responsible person"],
                },
                "target_date": {
                    "type": "date",
                    "aliases": ["target date", "due date", "completion date",
                                "zieldatum", "faellig", "termin", "deadline"],
                },
                "status": {
                    "type": "enum",
                    "aliases": ["status", "state", "state of the action",
                                "status der massnahme", "action status"],
                },
            },
            "enum_values": {
                "status": {
                    "open": "open", "offen": "open", "in progress": "in_progress",
                    "in bearbeitung": "in_progress", "done": "closed",
                    "closed": "closed", "erledigt": "closed",
                    "implemented": "closed", "umgesetzt": "closed",
                },
            },
        },
        "nc_register": {
            "kind": "generic",
            "table": "nc_register",
            "priority": 8,
            "label": "Nonconformity / CAPA register",
            "description": (
                "Nonconformities and corrective actions — the evidence behind "
                "the nonconformity and complaint criteria in VA26."
            ),
            "natural_key": ["nc_id"],
            "match_fields": ["nc_id"],
            "on_existing": "update",
            "facts": [
                {
                    "category": "nc",
                    "field_name": "nonconformance",
                    "value": "{nc_id}: {description}",
                    "fact_key": "nc_id",
                    "confidence": 0.85,
                }
            ],
            "fields": {
                "nc_id": {
                    "type": "text", "required": True,
                    "aliases": ["nc id", "nc number", "nonconformance id",
                                "abweichungsnummer", "finding id", "number",
                                "nc no", "abweichung id", "capa id"],
                },
                "description": {
                    "type": "text", "required": True,
                    "aliases": ["description", "beschreibung", "nonconformance",
                                "deviation", "abweichung", "finding", "issue",
                                "feststellung", "text"],
                },
                "raised_date": {
                    "type": "date",
                    "aliases": ["raised date", "date raised", "discovery date",
                                "erstellungsdatum", "datum", "feststellungsdatum",
                                "date of detection"],
                },
                "severity": {
                    "type": "enum",
                    "aliases": ["severity", "classification", "criticality",
                                "schweregrad", "einstufung", "gravitaet"],
                },
                "root_cause": {
                    "type": "text",
                    "aliases": ["root cause", "cause", "ursache",
                                "root cause analysis", "fehlerursache"],
                },
                "corrective_action": {
                    "type": "text",
                    "aliases": ["corrective action", "capa", "action",
                                "korrekturmassnahme", "massnahme",
                                "corrective action / preventive action"],
                },
                "due_date": {
                    "type": "date",
                    "aliases": ["due date", "target date", "faelligkeitsdatum",
                                "termin", "deadline"],
                },
                "status": {
                    "type": "enum",
                    "aliases": ["status", "state", "status der massnahme"],
                },
                "closed_date": {
                    "type": "date",
                    "aliases": ["closed date", "completion date", "abschlussdatum",
                                "date closed"],
                },
            },
            "enum_values": {
                "severity": {
                    "major": "major", "critical": "critical", "minor": "minor",
                    "observation": "observation", "feststellung": "observation",
                },
                "status": {
                    "open": "open", "offen": "open", "in progress": "in_progress",
                    "in bearbeitung": "in_progress", "closed": "closed",
                    "done": "closed", "erledigt": "closed",
                },
            },
        },
        "audit_findings": {
            "kind": "generic",
            "table": "audit_findings",
            "priority": 8,
            "label": "Audit findings (per evaluation)",
            "description": (
                "Findings from an internal or supplier audit — the evidence "
                "for the supplier-audit and complaint criteria in VA26."
            ),
            "natural_key": ["finding_id"],
            "match_fields": ["finding_id"],
            "on_existing": "update",
            "facts": [
                {
                    "category": "audit",
                    "field_name": "audit_finding",
                    "value": "{finding_id}: {description}",
                    "fact_key": "finding_id",
                    "confidence": 0.85,
                }
            ],
            "fields": {
                "finding_id": {
                    "type": "text", "required": True,
                    "aliases": ["finding id", "finding number", "audit finding",
                                "befund nummer", "befund-id", "id",
                                "finding no", "befund"],
                },
                "source": {
                    "type": "text",
                    "aliases": ["source", "audit", "audit type", "quelle",
                                "audit type", "herkunft"],
                },
                "description": {
                    "type": "text", "required": True,
                    "aliases": ["description", "finding", "beschreibung",
                                "observation", "feststellung"],
                },
                "classification": {
                    "type": "enum",
                    "aliases": ["classification", "category", "finding type",
                                "klassifizierung", "kategorie"],
                },
                "severity": {
                    "type": "enum",
                    "aliases": ["severity", "major minor", "kritikalitat",
                                "schweregrad", "gravitaet"],
                },
                "due_date": {
                    "type": "date",
                    "aliases": ["due date", "target date", "faelligkeitsdatum",
                                "termin"],
                },
                "status": {
                    "type": "enum",
                    "aliases": ["status", "state"],
                },
                "closed_date": {
                    "type": "date",
                    "aliases": ["closed date", "completion date", "abschlussdatum"],
                },
            },
            "enum_values": {
                "classification": {
                    "major": "major", "minor": "minor", "observation": "observation",
                    "feststellung": "observation", "recommendation": "recommendation",
                },
                "severity": {
                    "major": "major", "critical": "critical", "minor": "minor",
                },
                "status": {
                    "open": "open", "offen": "open", "in progress": "in_progress",
                    "closed": "closed", "done": "closed", "erledigt": "closed",
                },
            },
        },
        "certificate_register": {
            "kind": "generic",
            "table": "certificate_register",
            "priority": 8,
            "label": "Certificate register",
            "description": (
                "Certificates with issue and expiry dates — the evidence for "
                "the certification criteria in VA26. Expiry is checked in "
                "Python, never by a model."
            ),
            "natural_key": ["certificate_number"],
            "match_fields": ["certificate_number"],
            "on_existing": "update",
            "facts": [
                {
                    "category": "cert",
                    "field_name": "certification",
                    "value": "{certificate_type} ({certificate_number})",
                    "fact_key": "certificate_number",
                    "valid_from": "issued_date",
                    "valid_until": "expiry_date",
                    "confidence": 0.9,
                }
            ],
            "fields": {
                "certificate_number": {
                    "type": "text", "required": True,
                    "aliases": ["certificate number", "certificate no", "cert no",
                                "zertifikatsnummer", "cert number", "number",
                                "certificate", "zertifikat"],
                },
                "certificate_type": {
                    "type": "enum",
                    "aliases": ["certificate type", "type", "certification",
                                "zertifikatsart", "art", "certification type"],
                },
                "issued_date": {
                    "type": "date",
                    "aliases": ["issue date", "issued", "valid from",
                                "ausstellungsdatum", "gueltig ab",
                                "date of issue"],
                },
                "expiry_date": {
                    "type": "date",
                    "aliases": ["expiry date", "expiration date", "valid until",
                                "gueltig bis", "ablaufdatum", "expiry",
                                "date of expiry"],
                },
                "scope": {
                    "type": "text",
                    "aliases": ["scope", "geltungsbereich", "anwendungsbereich",
                                "certificate scope"],
                },
                "issuing_body": {
                    "type": "text",
                    "aliases": ["issuing body", "certification body",
                                "notified body", "ausstellende stelle",
                                "zertifizierungsstelle", "body"],
                },
                "status": {
                    "type": "enum",
                    "aliases": ["status", "state"],
                },
            },
            "enum_values": {
                "certificate_type": {
                    "iso 13485": "iso_13485", "iso 9001": "iso_9001",
                    "iso 14971": "iso_14971", "ce": "ce", "mdr": "mdr",
                    "iso 14001": "iso_14001",
                },
                "status": {
                    "valid": "valid", "gueltig": "valid", "expired": "expired",
                    "abgelaufen": "expired", "suspended": "suspended",
                    "withdrawn": "withdrawn", "zurueckgezogen": "withdrawn",
                },
            },
        },
        "tabular_records": {
            "kind": "raw_records",
            "table": "tabular_records",
            "label": "Unclassified tabular records (safe landing zone)",
            "description": (
                "Catch-all target for files that match no known table. Rows are "
                "stored verbatim (payload_json) with full provenance so nothing "
                "is ever lost, and can be re-mapped later."
            ),
            "natural_key": [],
            "on_existing": "skip",
            "fields": {},
        },
    },
    "routes": [
        {
            "match": {"file_pattern": "*buy*history*"},
            "target": "purchase_history",
            "priority": 50,
        },
        {
            "match": {"file_pattern": "*purchase*history*"},
            "target": "purchase_history",
            "priority": 50,
        },
        {
            "match": {"file_pattern": "*einkauf*"},
            "target": "purchase_history",
            "priority": 40,
        },
        {
            "match": {"file_pattern": "*lieferanten*stamm*"},
            "target": "supplier_master",
            "priority": 40,
        },
        {
            "match": {"file_pattern": "*supplier*list*"},
            "target": "supplier_master",
            "priority": 40,
        },
        {
            "match": {"sheet_name": "purchase_history"},
            "target": "purchase_history",
            "priority": 30,
        },
        {
            "match": {"sheet_name": "Purchase History"},
            "target": "purchase_history",
            "priority": 30,
        },
        {
            "match": {"sheet_contains": "purchase"},
            "target": "purchase_history",
            "priority": 20,
        },
        {
            "match": {"sheet_contains": "bestellung"},
            "target": "purchase_history",
            "priority": 20,
        },
        {
            "match": {"sheet_contains": "supplier"},
            "target": "supplier_master",
            "priority": 20,
        },
    ],
}


def _config_module():
    """Import the pipeline `config` module (same pattern as the other agents)."""
    import sys

    here = Path(__file__).resolve().parent
    for candidate in [here, here.parent, here.parent.parent]:
        if (candidate / "config.py").exists():
            if str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
            import config  # type: ignore

            return config
    return None


def get_registry_path() -> Path:
    """Path of the (editable) registry file."""
    override = os.environ.get("SUPPLIER_PIPELINE_TABLE_REGISTRY")
    if override:
        return Path(override).expanduser().resolve()
    config = _config_module()
    if config is not None:
        return config.get_data_dir() / "table_registry.json"
    return Path(__file__).resolve().parent.parent.parent / "data" / "table_registry.json"


def get_registry(path: Optional[Path] = None, create: bool = True) -> dict:
    """Load the registry, creating it from the defaults on first use."""
    path = Path(path) if path else get_registry_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"table registry is not valid JSON: {exc}") from exc
        # merge defaults so new fields appear after an upgrade
        for key, value in DEFAULT_REGISTRY.items():
            data.setdefault(key, value)
        for key, value in DEFAULT_REGISTRY["targets"].items():
            data.setdefault("targets", {}).setdefault(key, value)
        return data

    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(DEFAULT_REGISTRY, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return json.loads(json.dumps(DEFAULT_REGISTRY))


def save_registry(registry: dict, path: Optional[Path] = None) -> Path:
    path = Path(path) if path else get_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return path


def get_target(registry: dict, target_key: str) -> dict:
    """Return a target definition, falling back to the safe landing zone."""
    targets = registry.get("targets", {})
    if target_key in targets:
        return targets[target_key]
    fallback = registry.get("fallback_target", "tabular_records")
    return targets.get(fallback, {"kind": "raw_records", "table": "tabular_records",
                                  "fields": {}, "natural_key": [], "on_existing": "skip"})


def list_targets(registry: dict) -> list[dict]:
    """Human readable list of known target tables."""
    out = []
    for key, tdef in registry.get("targets", {}).items():
        out.append({
            "key": key,
            "kind": tdef.get("kind"),
            "table": tdef.get("table"),
            "label": tdef.get("label", key),
            "fields": list((tdef.get("fields") or {}).keys()),
            "natural_key": tdef.get("natural_key", []),
        })
    return out
