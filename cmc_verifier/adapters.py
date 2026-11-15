"""Ingestion adapters (ARCHITECTURE.md §2.1) — the moat.

Each adapter turns ONE messy source format into normalized SourceFacts. The
contract is identical for every adapter, so `ingest` just routes by file type and
nothing downstream ever changes.

The CSV adapter survives what real CoAs actually throw at you:
  - a preamble block above the table (title, product, batch, date)
  - the header row buried somewhere in the middle
  - units baked into the value string ("99.2 %", "0.32%")
  - padded / inconsistent analyte names (" Assay ")
  - blank filler rows and category sub-headers ("Impurities")
  - limit results ("< 0.05")             -> qualifier "<", value 0.05
  - non-numeric results ("ND", "N/D")    -> result_text "ND"
  - multiple batches in one file (a mid-table "Batch No." row switches batch)
  - a signature/footer block below the table
  - analyte aliases ("Water" -> "Water Content")
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from .models import SourceFact, SourceRef

_REQUIRED_HEADERS = {"test", "result"}
_BATCH_KEYS = {"batch no.", "batch no", "batch id", "batch"}
_DATE_KEYS = {"date of manufacture", "date"}

# Optional sign; thousands-grouped (1,234.5), plain, or decimal-comma (0,5); optional exponent.
_NUM_RE = re.compile(r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:[.,]\d+)?(?:[eE][-+]?\d+)?")
_QUALIFIERS = ("<=", ">=", "≤", "≥", "<", ">")   # match 2-char operators first
_QUALIFIER_NORMAL = {"≤": "<=", "≥": ">="}
# Below-quantitation results: kept as a qualitative token instead of being dropped.
_BLQ_RE = re.compile(r"^(?:<\s*LOQ|<\s*LOD|BLQ|BQL|BELOW\s+LOQ)$", re.I)


def _to_float(token: str) -> float:
    """'1,234.5' -> 1234.5 ; '1,234' -> 1234.0 ; '0,5' -> 0.5 ; '1.2e-3' -> 0.0012."""
    if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?:[eE][-+]?\d+)?", token):
        token = token.replace(",", "")       # thousands separators
    else:
        token = token.replace(",", ".")      # decimal comma
    return float(token)


# Non-numeric qualitative results, normalized (dots/spaces removed) -> canonical.
_NON_NUMERIC = {"ND": "ND", "N/D": "ND", "NOTDETECTED": "ND", "NONEDETECTED": "ND"}

# Nomenclature resolution (ARCHITECTURE.md §2.1). Grow this as aliases appear.
ANALYTE_ALIASES = {
    "water": "Water Content",
    "water content": "Water Content",
    "assay": "Assay",
    "related substances - total": "Related Substances - Total",
    "total related substances": "Related Substances - Total",
}


def _clean(s: str) -> str:
    return s.strip()


def canonical_analyte(name: str) -> str:
    key = re.sub(r"\s+", " ", name.strip().lower())
    return ANALYTE_ALIASES.get(key, name.strip())


def parse_measurement(raw: str) -> tuple[str | None, float | None, str | None, str | None]:
    """Parse a Result cell into (qualifier, value, unit, result_text).

      "99.2 %"       -> (None, 99.2, "%", None)
      "< 0.05 %"     -> ("<", 0.05, "%", None)
      "ND" / "N/D"   -> (None, None, None, "ND")
      "of" / ""      -> (None, None, None, None)   # nothing usable
    """
    s = raw.strip()
    if not s:
        return (None, None, None, None)

    norm = re.sub(r"[.\s]", "", s.upper())   # "N.D." -> "ND", "Not Detected" -> "NOTDETECTED"
    if norm in _NON_NUMERIC:
        return (None, None, None, _NON_NUMERIC[norm])

    if _BLQ_RE.match(s):
        return (None, None, None, "BLQ")

    qualifier = None
    for q in _QUALIFIERS:
        if s.startswith(q):
            qualifier = _QUALIFIER_NORMAL.get(q, q)
            s = s[len(q):].strip()
            break

    m = _NUM_RE.search(s)
    if not m:
        return (None, None, None, None)
    rest = s[m.end():].strip()
    if re.match(r"^(?:-|–|to)\s*\d", rest, re.I):   # "95-105": a range, not a value
        return (None, None, None, None)
    value = _to_float(m.group())
    unit = rest or None
    return (qualifier, value, unit, None)


def parse_value(raw: str) -> tuple[float | None, str | None]:
    """Backward-compatible wrapper: (value, unit) only."""
    _q, value, unit, _t = parse_measurement(raw)
    return (value, unit)


def facts_from_rows(rows, document_id):
    """Turn a table of rows-and-cells into normalized SourceFacts.

    This is the shared normalization used by EVERY source format. An adapter's
    only job is to produce `rows` (a list of cell-lists, preamble included) in
    this shape; from here the logic is identical whether it came from CSV, PDF,
    XLSX, or a vision model. Do not duplicate this in an adapter.
    """
    batch_id = date = header = None
    facts = []
    for line_no, row in enumerate(rows, start=1):
        cells = [_clean(c) for c in row]
        if not any(cells):
            continue
        key = cells[0].lower()
        if key in _BATCH_KEYS and len(cells) > 1 and cells[1]:
            batch_id = cells[1]; continue
        if header is None and key in _DATE_KEYS and len(cells) > 1 and cells[1]:
            date = cells[1]; continue
        if header is None:
            if _REQUIRED_HEADERS.issubset({c.lower() for c in cells}):
                header = [c.lower() for c in cells]
            continue
        record = dict(zip(header, cells))
        analyte_raw = record.get("test", "")
        if not analyte_raw:
            continue
        qualifier, value, unit_from_value, result_text = parse_measurement(record.get("result", ""))
        if value is None and result_text is None:
            continue
        facts.append(SourceFact(
            analyte=canonical_analyte(analyte_raw),
            method=record.get("method") or None,
            result=value, qualifier=qualifier, result_text=result_text,
            unit=None if result_text else (unit_from_value or record.get("units") or None),
            batch_id=batch_id, date=date,
            source_ref=SourceRef(document_id=document_id, page=1, location=f"row {line_no}"),
        ))
    return facts


def parse_coa_csv(path):
    """CSV adapter: read the file into rows, hand them to the shared normalizer."""
    path = Path(path)
    rows = list(csv.reader(io.StringIO(path.read_text())))
    return facts_from_rows(rows, document_id=path.stem)

_TEXT_TABLE_SETTINGS = {"vertical_strategy": "text", "horizontal_strategy": "text"}


def _tables_to_rows(tables):
    rows = []
    for table in tables:
        for r in table:
            rows.append([(c or "").strip() for c in r])
    return rows


def _has_header(rows):
    return any(_REQUIRED_HEADERS.issubset({c.lower() for c in row}) for row in rows)


def _extract_table_rows(page):
    """Prefer ruled lines; fall back to text-alignment for borderless tables.

    Bordered CoAs resolve cleanly via ruling lines. Borderless ones have no lines
    to detect, so we reconstruct columns from text alignment. We only accept a
    strategy that actually yields a header row, so a borderless page doesn't fall
    through to a garbage line-based result (and vice versa).
    """
    line_rows = _tables_to_rows(page.extract_tables())
    if _has_header(line_rows):
        return line_rows
    text_rows = _tables_to_rows(page.extract_tables(_TEXT_TABLE_SETTINGS))
    return text_rows if _has_header(text_rows) else line_rows


def parse_coa_pdf(path):
    """PDF adapter (ARCHITECTURE.md §2.1).

    Its ONLY new job vs CSV: turn a PDF into the same rows-and-cells shape, then
    hand off to facts_from_rows. The table comes from pdfplumber (lines first,
    text-alignment fallback for borderless tables); the batch/date live in free
    text above the table, so we scan for them and synthesize the same preamble
    rows the CSV path would have had. Requires: pip install pdfplumber
    """
    import pdfplumber

    path = Path(path)
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                mb = re.search(r"Batch No\.?\s*:?\s*([A-Za-z0-9\-]+)", line, re.I)
                if mb:
                    rows.append(["Batch No.", mb.group(1)])
                md = re.search(r"Date of Manufacture\s*:?\s*(.+)", line, re.I)
                if md:
                    rows.append(["Date of Manufacture", md.group(1).strip()])
            rows.extend(_extract_table_rows(page))
    return facts_from_rows(rows, document_id=path.stem)