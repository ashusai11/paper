"""Robust CSV / XLSX / XLS reading.

Real supplier spreadsheets are messy. This module isolates that mess so the
rest of the pipeline only ever sees a normalized `Sheet`:

    * CSV  — encoding detection (utf-8-sig / utf-8 / cp1252 / latin-1),
             delimiter sniffing (`,` `;` tab `|`), header row detection when
             the file starts with title junk, thousands separators kept as text.
    * XLSX — all sheets, formulas read as their cached values (with a
             formula-text fallback), merged header cells forward-filled.
    * XLS  — detected and reported clearly (binary format, needs conversion).

Header detection heuristic: the first row inside the first `max_header_scan`
rows whose cell count matches the modal width of the following rows and whose
cells are mostly non-numeric text. Everything above it is kept as `preamble`
context (useful for routing and for the RAG text).
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .refine import norm_key

MAX_HEADER_SCAN = 25
MAX_PREVIEW_ROWS = 5


class TabularReadError(Exception):
    """Raised when a file cannot be read as a table."""


@dataclass
class Sheet:
    """One normalized table extracted from a file."""

    name: str
    headers: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)          # {header: raw value}
    row_numbers: list[int] = field(default_factory=list)    # 1-based source rows
    header_row: Optional[int] = None
    preamble: list[str] = field(default_factory=list)       # lines above the header
    warnings: list[str] = field(default_factory=list)
    source_format: str = "csv"

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def column_values(self, header: str) -> list[Any]:
        return [r.get(header) for r in self.rows]

    def to_markdown(self, max_rows: Optional[int] = None) -> str:
        """Render the sheet as a markdown table (used for the `documents` row)."""
        if not self.headers:
            return ""
        rows = self.rows if max_rows is None else self.rows[:max_rows]
        out = ["| " + " | ".join(str(h) for h in self.headers) + " |",
               "| " + " | ".join("---" for _ in self.headers) + " |"]
        for r in rows:
            cells = ["" if r.get(h) is None else str(r.get(h)) for h in self.headers]
            out.append("| " + " | ".join(cells) + " |")
        if max_rows is not None and len(self.rows) > max_rows:
            out.append(f"| _… {len(self.rows) - max_rows} more rows_ |"
                       + " |" * (len(self.headers) - 1))
        return "\n".join(out)


# ── helpers ───────────────────────────────────────────────────────────────────

def _decode(data: bytes) -> tuple[str, str]:
    """Return (text, encoding) for raw file bytes."""
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8(replace)"


def _sniff_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        if dialect.delimiter:
            return dialect.delimiter
    except Exception:
        pass
    # fall back to the delimiter that yields the most columns in the header
def _sniff_delimiter(sample: str) -> str:
    """Pick the delimiter that actually splits this file into columns.

    `csv.Sniffer` is unreliable for files that start with a title line, so the
    decision is made by scoring each candidate: how many lines split into
    more than one field, and how many fields the typical line has.
    """
    lines = [ln for ln in sample.splitlines() if ln.strip()][:20]
    if not lines:
        return ","

    best_delim, best_score = ",", (-1, -1)
    for delim in (",", ";", "\t", "|"):
        widths = []
        for line in lines:
            try:
                widths.append(len(next(csv.reader([line], delimiter=delim))))
            except Exception:
                widths.append(1)
        split_lines = [w for w in widths if w > 1]
        if not split_lines:
            continue
        split_lines.sort()
        median = split_lines[len(split_lines) // 2]
        score = (len(split_lines), median)
        if score > best_score:
            best_delim, best_score = delim, score
    return best_delim


def _is_blank_row(row: list[Any]) -> bool:
    return all(v is None or (isinstance(v, str) and not v.strip()) for v in row)


def _looks_numeric(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, (int, float, dt.datetime, dt.date)) and not isinstance(v, bool):
        return True
    s = str(v).strip()
    if not s:
        return True
    return bool(re.fullmatch(r"[-+(]?\s*[\d.,]+%?\s*\)?([A-Za-z]{1,4})?", s))


def _detect_header_row(rows: list[list[Any]]) -> tuple[int, list[str]]:
    """Return (index of header row, headers). `index` is 0-based into `rows`."""
    scan = rows[:MAX_HEADER_SCAN]
    if not scan:
        return 0, []

    widths = [len([c for c in r]) for r in scan]
    modal_width = max(set(widths), key=widths.count)

    best_idx, best_score = 0, -1.0
    for i, row in enumerate(scan):
        cells = [c for c in row if c is not None and str(c).strip() != ""]
        if len(cells) < 2:
            continue
        text_cells = [c for c in cells if not _looks_numeric(c)]
        if not text_cells:
            continue
        text_ratio = len(text_cells) / len(cells)
        width_score = 1.0 if len(row) >= modal_width - 1 else 0.4
        score = text_ratio * width_score - i * 0.01  # earlier rows win ties
        if score > best_score:
            best_score, best_idx = score, i

    header_row = scan[best_idx]
    headers = _dedupe_headers(header_row)
    return best_idx, headers


def _dedupe_headers(row: list[Any]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for i, cell in enumerate(row):
        name = str(cell).strip() if cell is not None else ""
        name = re.sub(r"\s+", " ", name) or f"column_{i + 1}"
        key = name.lower()
        if key in seen:
            seen[key] += 1
            name = f"{name}_{seen[key]}"
        else:
            seen[key] = 0
        out.append(name)
    return out


def _is_repeated_header(row: list[Any], headers: list[str]) -> bool:
    """True when a data row is just the header repeated.

    Some ERP exports repeat the header every N rows or after a page break.
    Such a row is not data — keeping it would put a fake order into the
    target table.
    """
    values = [norm_key(c) for c in row if c is not None and str(c).strip() != ""]
    if not values:
        return False
    expected = [norm_key(h) for h in headers if str(h).strip() != ""]
    return values == expected


def _rows_to_dicts(rows: list[list[Any]], headers: list[str],
                   start_index: int) -> tuple[list[dict], list[int], int]:
    """Return (records, source row numbers, number of repeated header rows)."""
    data: list[dict] = []
    numbers: list[int] = []
    repeated = 0
    for offset, row in enumerate(rows):
        if _is_blank_row(row):
            continue
        if _is_repeated_header(row, headers):
            repeated += 1
            continue
        rec: dict[str, Any] = {}
        for i, h in enumerate(headers):
            rec[h] = row[i] if i < len(row) else None
        data.append(rec)
        numbers.append(start_index + offset + 1)  # 1-based source row
    return data, numbers, repeated


def _forward_fill_header(row: list[Any]) -> list[Any]:
    """Forward-fill empty header cells (merged title/header cells in Excel)."""
    out: list[Any] = []
    last = None
    for cell in row:
        if cell is None or (isinstance(cell, str) and not cell.strip()):
            out.append(last)
        else:
            out.append(cell)
            last = cell
    return out


# ── CSV ───────────────────────────────────────────────────────────────────────

def read_csv(path: Path) -> list[Sheet]:
    data = Path(path).read_bytes()
    text, encoding = _decode(data)
    delimiter = _sniff_delimiter(text[:4096])

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    raw_rows: list[list[Any]] = []
    for row in reader:
        raw_rows.append(row)
    if not raw_rows:
        raise TabularReadError(f"{path.name}: file is empty")

    # drop fully trailing empty lines
    while raw_rows and _is_blank_row(raw_rows[-1]):
        raw_rows.pop()

    header_idx, headers = _detect_header_row(raw_rows)
    if not headers:
        raise TabularReadError(f"{path.name}: could not detect a header row")

    data_rows, numbers, repeated = _rows_to_dicts(raw_rows[header_idx + 1:], headers,
                                                   header_idx + 1)
    preamble = [
        " | ".join(str(c) for c in row if c is not None and str(c).strip())
        for row in raw_rows[:header_idx]
    ]

    sheet = Sheet(
        name=Path(path).stem,
        headers=headers,
        rows=data_rows,
        row_numbers=numbers,
        header_row=header_idx + 1,
        preamble=[p for p in preamble if p],
        source_format="csv",
    )
    if encoding not in ("utf-8", "utf-8-sig"):
        sheet.warnings.append(f"decoded with {encoding}")
    if delimiter != ",":
        sheet.warnings.append(f"delimiter detected: {delimiter!r}")
    if sheet.preamble:
        sheet.warnings.append(f"{len(sheet.preamble)} preamble line(s) before the header")
    if repeated:
        sheet.warnings.append(f"{repeated} repeated header row(s) skipped")
    return [sheet]


# ── XLSX ─────────────────────────────────────────────────────────────────────

def read_xlsx(path: Path, data_only: bool = True) -> list[Sheet]:
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover
        raise TabularReadError(
            "openpyxl is required for Excel files — pip install openpyxl>=3.1.0"
        ) from exc

    try:
        wb = openpyxl.load_workbook(str(path), data_only=data_only, read_only=True)
    except Exception as exc:
        raise TabularReadError(f"{path.name}: cannot open workbook ({exc})") from exc

    sheets: list[Sheet] = []
    for ws in wb.worksheets:
        if ws.sheet_state != "visible":
            continue
        raw_rows = [list(r) for r in ws.iter_rows(values_only=True)]
        while raw_rows and _is_blank_row(raw_rows[-1]):
            raw_rows.pop()
        if not raw_rows:
            continue
        header_idx, headers = _detect_header_row(raw_rows)
        if not headers:
            continue
        headers = _dedupe_headers(_forward_fill_header(raw_rows[header_idx]))
        data_rows, numbers, repeated = _rows_to_dicts(raw_rows[header_idx + 1:], headers,
                                                       header_idx + 1)
        preamble = [
            " | ".join(str(c) for c in row if c is not None and str(c).strip())
            for row in raw_rows[:header_idx]
        ]
        sheet = Sheet(
            name=ws.title,
            headers=headers,
            rows=data_rows,
            row_numbers=numbers,
            header_row=header_idx + 1,
            preamble=[p for p in preamble if p],
            source_format="xlsx",
        )
        if sheet.preamble:
            sheet.warnings.append(f"{len(sheet.preamble)} preamble row(s) before the header")
        if repeated:
            sheet.warnings.append(f"{repeated} repeated header row(s) skipped")
        sheets.append(sheet)

    wb.close()
    return sheets


# ── dispatch ──────────────────────────────────────────────────────────────────

# ── JSON / JSONL ─────────────────────────────────────────────────────────────

def _rows_from_records(records: list[dict], name: str) -> Sheet:
    """Build a Sheet from a list of dict records (JSON / JSONL)."""
    headers: list[str] = []
    for rec in records:
        for key in rec:
            if key not in headers:
                headers.append(key)
    rows = []
    for index, rec in enumerate(records, start=1):
        row = {}
        for key in headers:
            value = rec.get(key)
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            row[key] = value
        rows.append(row)
    return Sheet(name=name, headers=headers, rows=rows,
                 row_numbers=list(range(1, len(rows) + 1)),
                 source_format="json")


def read_json(path: Path) -> list[Sheet]:
    """Read JSON or JSON-Lines into sheets.

    Accepts: a list of objects, a single object, an object whose values are
    lists (one sheet per list), and JSON-Lines.
    """
    raw = Path(path).read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        raise TabularReadError(f"{path.name}: file is empty")

    data: Any
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # JSON Lines
        records = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise TabularReadError(
                    f"{path.name}: not valid JSON or JSON-Lines ({exc})") from exc
        if not records:
            raise TabularReadError(f"{path.name}: no records found")
        return [_rows_from_records(records, path.stem)]

    sheets: list[Sheet] = []
    if isinstance(data, list):
        records = [r for r in data if isinstance(r, dict)]
        if not records:
            raise TabularReadError(
                f"{path.name}: JSON array does not contain objects")
        sheets.append(_rows_from_records(records, path.stem))
    elif isinstance(data, dict):
        list_values = [v for v in data.values() if isinstance(v, list)]
        if list_values and all(isinstance(v[0], dict) for v in list_values if v):
            for key, value in data.items():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    sheets.append(_rows_from_records(value, key))
            if sheets:
                return sheets
        sheets.append(_rows_from_records([data], path.stem))
    else:
        raise TabularReadError(f"{path.name}: unsupported JSON structure")
    return sheets


# ── XML ──────────────────────────────────────────────────────────────────────

def read_xml(path: Path) -> list[Sheet]:
    """Read XML into a sheet.

    Repeated sibling elements become the rows; their child elements and
    attributes become the columns. A document without repeated elements
    becomes a single row.
    """
    try:
        import xml.etree.ElementTree as ET
    except ImportError as exc:  # pragma: no cover
        raise TabularReadError("xml.etree is not available") from exc

    try:
        tree = ET.parse(str(path))
    except ET.ParseError as exc:
        raise TabularReadError(f"{path.name}: invalid XML ({exc})") from exc

    root = tree.getroot()
    groups: dict[str, list] = {}
    for child in root:
        groups.setdefault(_localname(child.tag), []).append(child)

    if not groups:
        return [Sheet(name=root.tag, headers=sorted(root.attrib) or ["value"],
                      rows=[root.attrib or {"value": (root.text or "").strip()}],
                      row_numbers=[1], source_format="xml")]

    # the group with the most members is the record set
    tag, elements = max(groups.items(), key=lambda kv: len(kv[1]))
    if len(elements) < 2:
        # no repeated elements -> one row describing the document
        headers = sorted(root.attrib) or ["value"]
        rows = [{h: root.attrib.get(h, (root.text or "").strip()) for h in headers}]
        return [Sheet(name=root.tag, headers=headers, rows=rows,
                      row_numbers=[1], source_format="xml")]

    headers: list[str] = []
    for element in elements:
        for key in element.attrib:
            if key not in headers:
                headers.append(key)
        for child in element:
            name = _localname(child.tag)
            if name not in headers:
                headers.append(name)
    if not headers:
        headers = ["value"]

    rows = []
    for element in elements:
        row: dict[str, Any] = {}
        for h in headers:
            value = element.attrib.get(h)
            if value is None:
                texts = [c for c in element
                         if _localname(c.tag) == h and (c.text or "").strip()]
                if texts:
                    value = ", ".join((c.text or "").strip() for c in texts)
                elif (element.text or "").strip():
                    value = element.text.strip()
            row[h] = value
        rows.append(row)

    return [Sheet(name=tag, headers=headers, rows=rows,
                  row_numbers=list(range(1, len(rows) + 1)),
                  source_format="xml")]


def _localname(tag: str) -> str:
    """Strip the XML namespace: `{http://...}order` -> `order`."""
    return tag.split("}")[-1] if "}" in tag else tag


def read_tabular(path: Path) -> list[Sheet]:
    """Read a CSV/XLSX/XLS file into a list of `Sheet` objects."""
    path = Path(path)
    if not path.exists():
        raise TabularReadError(f"file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv", ".txt"):
        if suffix == ".tsv":
            return _read_delimited(path, delimiter="\t")
        return read_csv(path)
    if suffix in (".xlsx", ".xlsm"):
        sheets = read_xlsx(path, data_only=True)
        if not sheets:
            # formulas without cached values -> fall back to formula text
            sheets = read_xlsx(path, data_only=False)
        return sheets
    if suffix in (".json", ".jsonl", ".ndjson"):
        return read_json(path)
    if suffix in (".xml", ".xsd", ".rss", ".atom"):
        return read_xml(path)
    if suffix == ".xls":
        raise TabularReadError(
            f"{path.name}: legacy .xls (BIFF) is not supported. "
            "Open it and save as .xlsx — everything else stays the same."
        )
    raise TabularReadError(f"{path.name}: unsupported extension '{suffix}'")


def _read_delimited(path: Path, delimiter: str) -> list[Sheet]:
    data = path.read_bytes()
    text, _enc = _decode(data)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    raw_rows = [list(r) for r in reader]
    while raw_rows and _is_blank_row(raw_rows[-1]):
        raw_rows.pop()
    if not raw_rows:
        raise TabularReadError(f"{path.name}: file is empty")
    header_idx, headers = _detect_header_row(raw_rows)
    data_rows, numbers, _repeated = _rows_to_dicts(raw_rows[header_idx + 1:], headers,
                                                   header_idx + 1)
    return [Sheet(
        name=path.stem,
        headers=headers,
        rows=data_rows,
        row_numbers=numbers,
        header_row=header_idx + 1,
        source_format="csv",
    )]


def preview(sheet: Sheet, n: int = MAX_PREVIEW_ROWS) -> list[dict]:
    return sheet.rows[:n]
