"""Deterministic normalization, validation and column mapping.

AGENTS.md rule 5: "Determinism stays in code. Date comparisons, expiry checks,
completeness checks, scoring arithmetic ... are Python. The LLM never computes
them." Same applies here: a date in `01.03.2024` is parsed by Python, never by
a model. The LLM is only consulted for the one thing code cannot decide
(ambiguous header -> target table), and it degrades gracefully.

Everything in this module is pure and side-effect free so it can be unit
tested and re-run over the same file for the same result.
"""

from __future__ import annotations

import datetime as dt
import difflib
import re
import unicodedata
from typing import Any, Optional

NBSP = " "

# ── text ──────────────────────────────────────────────────────────────────────

_MOJIBAKE_RE = re.compile("[\u00c3\u00c2\u00e2][\u0080-\u00ff\u00a0-\u00bf]")

_TRUTHY = {
    "1", "true", "yes", "y", "ja", "j", "x", "✓", "wahr", "ok", "present",
    "yes ", "yep", "problem", "reclamation",
}
_FALSEY = {
    "0", "false", "no", "n", "nein", "nein ", "falsch", "korrekt", "ok",
    "none", "n/a", "na", "-", "",
}

_MONTHS = {
    # English
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
    # German
    "januar": 1, "februar": 2, "maerz": 3, "mrz": 3, "märz": 3, "marz": 3,
    "april": 4, "mai": 5, "juni": 6, "juli": 7, "august": 8, "september": 9,
    "oktober": 10, "okt": 10, "november": 11, "dez": 12, "dezember": 12,
}

_CURRENCY_WORDS = re.compile(
    r"(?i)(eur|usd|chf|gbp|jpy|sek|nok|dkk|pln|czk|zar|aud|cad|inr|rmb|"
    r"euro|dollar|franc|pound|yen|dollars|euros)\b"
)
_CURRENCY_SYMBOLS = "$€£¥₹"


def fix_mojibake(s: str) -> str:
    """Repair UTF-8 bytes that were decoded as cp1252/latin-1 (common when a
    German Excel file travels through a system that assumes latin-1)."""
    if not _MOJIBAKE_RE.search(s):
        return s
    try:
        return s.encode("cp1252", errors="strict").decode("utf-8", errors="strict")
    except Exception:
        return s


def norm_text(value: Any) -> Optional[str]:
    """Normalize any cell value to a clean string (or None when empty)."""
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    s = str(value).replace(NBSP, " ").replace("\u200b", "").replace("\u00ad", "")
    s = s.strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{2,}", "\n", s)
    s = fix_mojibake(s)
    return s or None


def norm_key(value: Any) -> str:
    """Normalize a header into a comparison key: `Bestell-Nr.` -> `bestell_nr`."""
    s = norm_text(value) or ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


# ── dates ─────────────────────────────────────────────────────────────────────

_EXCEL_EPOCH = dt.date(1899, 12, 30)


def parse_date(value: Any, dayfirst: bool = True) -> Optional[str]:
    """Parse a date cell into ISO `YYYY-MM-DD`.

    Handles: datetime/date objects, Excel serial numbers, ISO strings,
    `01.03.2024`, `1/3/2024`, `2024-03-01`, `01.03.24`, `Mar 2024`, `März 2024`.
    Returns None when the value is not a date (never guesses).
    """
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        # Excel serial date (1900 system); plausible range 1970..2100
        if 25569 <= float(value) <= 73050:
            return (_EXCEL_EPOCH + dt.timedelta(days=int(value))).isoformat()
        return None

    s = norm_text(value)
    if not s:
        return None
    s = s.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")

    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _ymd(y, mo, d)

    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000 if y < 70 else 1900
        day, mon = (a, b) if dayfirst else (b, a)
        # if the "day" cannot be a day but the "month" can, swap
        if day > 31 and mon <= 31:
            day, mon = mon, day
        return _ymd(y, mon, day)

    m = re.fullmatch(r"(\d{8})", s)
    if m:
        s8 = m.group(1)
        if s8[:4] in ("19", "20"):
            return _ymd(int(s8[:4]), int(s8[4:6]), int(s8[6:8]))
        return _ymd(int(s8[4:8]), int(s8[2:4]), int(s8[0:2]))

    # "12 Mar 2024" / "März 2024" / "Mar-2024"
    m = re.search(r"([A-Za-zäöüÄÖÜß]+)[\s\-./]*(\d{4})", s)
    if m:
        name = norm_key(m.group(1))
        month = _MONTHS.get(name)
        if month:
            return _ymd(int(m.group(2)), month, 1)

    return None


def _ymd(y: int, m: int, d: int) -> Optional[str]:
    try:
        return dt.date(y, m, d).isoformat()
    except ValueError:
        return None


# ── numbers ───────────────────────────────────────────────────────────────────

def parse_number(value: Any, decimal_separator: str = "auto") -> Optional[float]:
    """Parse a numeric cell. Handles `1.234,56` (DE), `1,234.56` (EN),
    `(123,45)` (negative), `1 234,56`, currency symbols, `12 %`."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    s = norm_text(value)
    if not s:
        return None
    s = _CURRENCY_WORDS.sub("", s)                    # EUR 1 250,00 -> " 1 250,00"
    s = s.replace(NBSP, "").replace(" ", "").replace("\u2009", "").replace("\u202f", "")
    s = re.sub(r"^[A-Za-z]{3}(?=\d)", "", s)          # EUR1250
    s = re.sub(r"[A-Za-z]{3}$", "", s)                # 1250EUR
    s = "".join(ch for ch in s if ch not in _CURRENCY_SYMBOLS)
    s = s.replace("%", "")
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")

    has_c, has_d = "," in s, "." in s
    if has_c and has_d:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        thou = "." if dec == "," else ","
        s = s.replace(thou, "").replace(dec, ".")
    elif has_c:
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+", s):
            s = s.replace(",", "")            # 1,234,567 -> thousands
        elif decimal_separator == ".":
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")           # 1234,56 -> 1234.56
    elif has_d:
        if re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
            s = s.replace(".", "")            # 1.234.567 -> thousands
        elif decimal_separator == ",":
            s = s.replace(".", "")

    try:
        out = float(s)
    except ValueError:
        return None
    return -out if negative else out


def parse_bool(value: Any) -> Optional[bool]:
    """Parse a truthy/falsy cell. Returns None when it is not a flag at all."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    s = (norm_text(value) or "").strip().lower()
    if s in _TRUTHY:
        return True
    if s in _FALSEY:
        return False
    return None


# ── column mapping ───────────────────────────────────────────────────────────

# Aliases that are too generic to count as a strong signal. "number" fits a
# purchase order, a certificate and a nonconformity alike — matching it must
# not decide the routing.
WEAK_ALIASES = {
    "number", "id", "name", "date", "type", "ref", "code", "state",
    "description", "value", "status", "note", "notes",
}


def _score(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    at, bt = set(a.split("_")), set(b.split("_"))
    jaccard = len(at & bt) / len(at | bt) if at and bt else 0.0
    # Substring containment only counts when the shorter key is long enough
    # to be meaningful — otherwise the alias "s" (FMEA severity) would match
    # "purchase_date" because it contains the letter "s".
    contains = 0.0
    if min(len(a), len(b)) >= 4 and (a in b or b in a):
        contains = 1.0
    return max(min(ratio, 1.0), jaccard * 0.95, contains * 0.9)


def map_columns(headers: list[str], target_def: dict,
                threshold: float = 0.82) -> dict:
    """Map source headers onto canonical target fields.

    Returns:
        {
          "mapping": {source_header: field_name},
          "unmapped": [source_header, ...],
          "scores": {source_header: round(score, 3)},
          "missing_required": [field, ...],
          "coverage": float,
        }
    """
    fields: dict = target_def.get("fields", {})
    alias_index: dict[str, str] = {}
    for fname, fdef in fields.items():
        for alias in [fname] + list(fdef.get("aliases", [])):
            key = norm_key(alias)
            if key and key not in alias_index:
                alias_index[key] = fname

    mapping: dict[str, str] = {}
    scores: dict[str, float] = {}
    strong: set[str] = set()
    used_fields: set[str] = set()

    # pass 1 — exact alias hits
    for header in headers:
        key = norm_key(header)
        if key in alias_index and alias_index[key] not in used_fields:
            fname = alias_index[key]
            mapping[header] = fname
            scores[header] = 1.0
            used_fields.add(fname)
            if key not in WEAK_ALIASES:
                strong.add(fname)

    # pass 2 — fuzzy hits on the remaining headers
    for header in headers:
        if header in mapping:
            continue
        key = norm_key(header)
        if not key:
            continue
        best_field, best_score, best_key = None, 0.0, ""
        for alias_key, fname in alias_index.items():
            if fname in used_fields:
                continue
            s = _score(key, alias_key)
            if s > best_score:
                best_field, best_score, best_key = fname, s, alias_key
        if best_field and best_score >= threshold:
            mapping[header] = best_field
            scores[header] = round(best_score, 3)
            used_fields.add(best_field)
            if best_key not in WEAK_ALIASES:
                strong.add(best_field)

    required = [f for f, d in fields.items() if d.get("required")]
    missing_required = [f for f in required if f not in used_fields]
    unmapped = [h for h in headers if h not in mapping]

    total_fields = len(fields) or 1
    coverage = len(used_fields) / total_fields
    strong_coverage = len(strong) / total_fields

    # Precision: how much of THIS sheet the target explains. A strong match
    # counts 1.0, a match through a generic alias ("number", "id") 0.4.
    # A target is never punished for fields the sheet simply does not have.
    weight = 0.0
    for header, fname in mapping.items():
        key = norm_key(header)
        alias_keys = {norm_key(a) for a in [fname] + list(fields[fname].get("aliases", []))}
        weak = bool(alias_keys & WEAK_ALIASES) and key in WEAK_ALIASES
        weight += 0.4 if weak else 1.0
    precision = weight / len(headers) if headers else 0.0

    return {
        "mapping": mapping,
        "unmapped": unmapped,
        "scores": scores,
        "missing_required": missing_required,
        "coverage": round(coverage, 3),
        "strong_coverage": round(strong_coverage, 3),
        "precision": round(precision, 3),
        "strong_fields": sorted(strong),
    }


def coerce_value(value: Any, field_def: dict, decimal_separator: str = "auto") -> Any:
    """Coerce one cell to the canonical type of its target field.

    Types: text | date | number | int | bool | enum | score | computed
    """
    ftype = field_def.get("type", "text")
    if ftype == "date":
        return parse_date(value, dayfirst=field_def.get("dayfirst", True))
    if ftype == "number":
        return parse_number(value, decimal_separator=decimal_separator)
    if ftype == "bool":
        return parse_bool(value)
    if ftype == "int":
        num = parse_number(value, decimal_separator=decimal_separator)
        return int(num) if num is not None else None
    if ftype == "score":
        num = parse_number(value, decimal_separator=decimal_separator)
        return int(round(num)) if num is not None else None
    if ftype == "computed":
        return None            # filled in by _compute_fields()
    return norm_text(value)


# ── deterministic computed fields ────────────────────────────────────────────
# AGENTS.md rule 5: "Determinism stays in code. Date comparisons, expiry
# checks, completeness checks, scoring arithmetic ... are Python. The LLM
# never computes them." RPN and risk levels are scoring arithmetic, so they
# are computed here — never asked of a model.

def _compute_rpn(record: dict, field_def: dict) -> Any:
    factors = field_def.get("factors", ["severity", "occurrence", "detection"])
    values = []
    for name in factors:
        raw = record.get(name)
        num = parse_number(raw) if raw is not None else None
        if num is None:
            return None
        values.append(int(round(num)))
    product = 1
    for v in values:
        product *= v
    return product


def _compute_threshold_level(record: dict, field_def: dict) -> Any:
    """Map a numeric value onto a label using the target's thresholds.

    `thresholds`: [{"max": 39, "value": "low"}, {"max": 99, "value": "medium"},
                   {"value": "high"}]  (first match wins, `max` inclusive)
    """
    source = field_def.get("source", "rpn")
    raw = record.get(source)
    num = parse_number(raw) if raw is not None else None
    if num is None:
        return None
    for rule in field_def.get("thresholds", []):
        limit = rule.get("max")
        if limit is None or num <= limit:
            return rule.get("value")
    return field_def.get("default")


COMPUTE_FUNCTIONS = {
    "rpn": _compute_rpn,
    "threshold_level": _compute_threshold_level,
}


def compute_fields(record: dict, target_def: dict) -> tuple[dict, list[dict]]:
    """Fill the computed fields of a record. Returns (record, errors)."""
    errors: list[dict] = []
    for fname, fdef in (target_def.get("fields") or {}).items():
        if fdef.get("type") != "computed":
            continue
        func = COMPUTE_FUNCTIONS.get(fdef.get("compute", ""))
        if func is None:
            errors.append({
                "source_row": None, "column": fname,
                "message": f"unknown compute function '{fdef.get('compute')}'",
                "raw_value": None,
            })
            continue
        value = func(record, fdef)
        if value is None:
            errors.append({
                "source_row": None, "column": fname,
                "message": "cannot compute — an input field is missing or invalid",
                "raw_value": None,
            })
        else:
            record[fname] = value
    return record, errors


def apply_enum(value: Any, field_def: dict) -> tuple[Any, bool]:
    """Map a value through the target's enum alias table.

    Returns (canonical_value, changed). Unknown values are kept verbatim
    (never silently dropped) and flagged by the caller as `unmapped_enum`.
    """
    if value is None:
        return None, False
    enum_map = {norm_key(k): v for k, v in (field_def.get("enum_values") or {}).items()}
    key = norm_key(value)
    if key in enum_map:
        return enum_map[key], enum_map[key] != value
    return value, False


# ── sheet level refinement ───────────────────────────────────────────────────

def refine_sheet(sheet, target_def: dict, mapping_info: dict,
                 decimal_separator: str = "auto", dayfirst: bool = True,
                 ) -> tuple[list[dict], list[dict]]:
    """Turn raw sheet rows into canonical records.

    Returns:
        (records, errors)

        records: [{"source_row": int, "record": {...}, "extra": {...},
                   "errors": [...], "warnings": [...], "natural_key": str}]
        errors:  [{"source_row": int, "column": str, "message": str,
                   "raw_value": Any}]
    """
    fields: dict = target_def.get("fields", {})
    mapping: dict = mapping_info.get("mapping", {})
    unmapped = [h for h in mapping_info.get("unmapped", [])]
    target_enums: dict = target_def.get("enum_values") or {}

    records: list[dict] = []
    errors: list[dict] = []

    for idx, row in enumerate(sheet.rows):
        source_row = (sheet.row_numbers[idx] if idx < len(sheet.row_numbers)
                      else idx + 1)
        record: dict[str, Any] = {}
        extra: dict[str, Any] = {}
        row_errors: list[dict] = []
        row_warnings: list[str] = []

        for header, field_name in mapping.items():
            fdef = fields.get(field_name, {})
            enum_values = (target_enums or {}).get(field_name) or fdef.get("enum_values")
            fdef = {**fdef, "enum_values": enum_values} if enum_values else fdef
            raw = row.get(header)
            ftype = fdef.get("type", "text")

            if ftype == "computed":
                # filled in after all the other fields are resolved
                continue

            if ftype == "enum":
                value, changed = apply_enum(norm_text(raw), fdef)
                if changed:
                    row_warnings.append(
                        f"'{raw}' mapped to canonical enum '{value}'")
                if value is not None and norm_key(value) not in {
                    norm_key(k) for k in (fdef.get("enum_values") or {})
                }:
                    row_warnings.append(
                        f"'{value}' is not a known value for {field_name}")
            else:
                value = coerce_value(
                    raw, fdef,
                    decimal_separator=decimal_separator,
                )
                if ftype == "date" and value is None and raw not in (None, ""):
                    row_errors.append({
                        "source_row": source_row, "column": header,
                        "message": f"could not parse '{raw}' as a date",
                        "raw_value": raw,
                    })
                if ftype in ("number", "int", "score") and value is None and raw not in (None, ""):
                    row_errors.append({
                        "source_row": source_row, "column": header,
                        "message": f"could not parse '{raw}' as a number",
                        "raw_value": raw,
                    })
                if ftype == "score" and value is not None:
                    low = fdef.get("min")
                    high = fdef.get("max")
                    if (low is not None and value < low) or (high is not None and value > high):
                        row_errors.append({
                            "source_row": source_row, "column": header,
                            "message": (f"value {value} is outside the allowed "
                                        f"range {low}-{high}"),
                            "raw_value": raw,
                        })

            if value is None and fdef.get("required"):
                row_errors.append({
                    "source_row": source_row, "column": header,
                    "message": f"required field '{field_name}' is missing",
                    "raw_value": raw,
                })
            if value is not None:
                record[field_name] = value

        record, compute_errors = compute_fields(record, target_def)
        for err in compute_errors:
            err = {**err, "source_row": source_row}
            row_errors.append(err)

        for header in unmapped:
            if header in row:
                extra[header] = row.get(header)

        natural_key_fields = target_def.get("natural_key") or []
        natural_key = "|".join(str(record.get(k, "")) for k in natural_key_fields)

        records.append({
            "source_row": source_row,
            "record": record,
            "extra": extra,
            "errors": row_errors,
            "warnings": row_warnings,
            "natural_key": natural_key,
        })
        errors.extend(row_errors)

    return records, errors
