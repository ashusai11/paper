"""Fact projection — turn spreadsheet rows into `profile_facts`.

A spreadsheet can carry facts about a supplier, not just transactions:
a certificate register says *ISO 13485 is valid until 2027*; an NC register
says *this defect was found and closed*. Those are exactly what
`profile_facts` holds and what the VA26 gate engine reads:

    category="cert"    → the certification criterion + "ISO 13485 NOT FOUND"
    category="nc"      → the nonconformity / complaint criterion
    category="audit"   → the supplier-audit criterion
    category="risk"    → the risk signals shown in the evaluation context

**Purchase history is deliberately NOT projected into facts.** Its rows are
the economic evidence: `economic.py` and `context_builder.py` read
`purchase_history` directly (n purchases, late rate, amount, quality
issues). Copying the same orders into facts would create a second source
of truth and double-count them.

The projection is deterministic — the values are already parsed and
canonical, so no model is involved (AGENTS.md rule 5). Every fact carries
its provenance: the document, the sheet and row it came from, the chunk it
lives in, and the snippet it was read from.

A target declares its projection in the registry:

    "facts": [
        {"category": "cert", "field_name": "certification",
         "value": "{certificate_type} ({certificate_number})",
         "valid_from": "issued_date", "valid_until": "expiry_date"}
    ]
"""

from __future__ import annotations

from typing import Any, Optional

# A fact is only written when every placeholder in its template resolves.
# A half-filled value ("ISO 13485 ()") is worse than no fact at all.
_MISSING = object()


class _Record(dict):
    """Dict that returns a sentinel for missing keys."""

    def __missing__(self, key):
        return _MISSING


def _render(template: str, record: dict) -> Optional[str]:
    """Render a `{field}` template against a record; None if anything is missing."""
    if not template:
        return None
    if any(v is _MISSING for v in _resolve(template, record)):
        return None  # a placeholder in the template has no value in this record
    try:
        rendered = template.format_map(_Record(record))
    except (KeyError, IndexError, ValueError):
        return None
    rendered = " ".join(str(rendered).split())
    return rendered or None


def _resolve(template: str, record: dict) -> list:
    """The values a template's placeholders resolve to (sentinel if missing)."""
    import string

    out = []
    for _, field, _, _ in string.Formatter().parse(template):
        if field:
            out.append(record.get(field, _MISSING))
    return out


def _snippet(raw_row: dict, max_len: int = 400) -> str:
    """A readable excerpt of the row the fact came from."""
    if not raw_row:
        return ""
    parts = []
    for key, value in raw_row.items():
        if value is None or str(value).strip() == "":
            continue
        parts.append(f"{key}={str(value).strip()}")
    text = " | ".join(parts)
    return text[:max_len]


def project_facts(
    store,
    target_def: dict,
    rows: list[dict],
    document_id: str = None,
    chunk_lookup: Optional[dict] = None,
    sheet_name: str = "",
) -> int:
    """Write the facts a sheet implies into `profile_facts`.

    `rows` entries look like:
        {"record": {...}, "raw_row": {...}, "source_row": 12,
         "supplier_id": "SUP-x"}

    `chunk_lookup` maps a source row number to the chunk id that contains it.

    Returns the number of facts written (facts that already existed are
    not rewritten — `add_profile_fact` is idempotent).
    """
    specs = target_def.get("facts") or []
    if not specs:
        return 0

    written = 0
    for entry in rows:
        record = entry.get("record") or {}
        raw_row = entry.get("raw_row") or {}
        supplier_id = entry.get("supplier_id")
        source_row = entry.get("source_row")
        if not supplier_id:
            continue

        for spec in specs:
            template = spec.get("value")
            if not template:
                continue
            value = _render(template, record)
            if not value:
                continue

            valid_from = record.get(spec["valid_from"]) if spec.get("valid_from") else None
            valid_until = record.get(spec["valid_until"]) if spec.get("valid_until") else None

            chunk_id = None
            if chunk_lookup and source_row is not None:
                chunk_id = chunk_lookup.get(source_row)

            # The item key: two certificates of the same supplier are two
            # facts, not a conflict. Without it, the second one would
            # supersede the first and the criterion would report
            # "ISO 13485 NOT FOUND" although it is on file.
            fact_key = None
            key_spec = spec.get("fact_key")
            if key_spec:
                if "|" in key_spec:
                    fact_key = "|".join(
                        str(record.get(part, "")).strip() for part in key_spec.split("|")
                    )
                else:
                    fact_key = str(record.get(key_spec, "")).strip()
                if not fact_key:
                    fact_key = None

            store.add_profile_fact(
                supplier_id=supplier_id,
                category=spec.get("category", "summary"),
                field_name=spec.get("field_name", "fact"),
                value=value,
                fact_key=fact_key,
                source_document_id=document_id,
                source_page=(f"{sheet_name}!{source_row}" if sheet_name and source_row
                             is not None else sheet_name or None),
                source_chunk_id=chunk_id,
                snippet=_snippet(raw_row),
                confidence=spec.get("confidence", 0.9),
                valid_from=valid_from,
                valid_until=valid_until,
            )
            written += 1
    return written
