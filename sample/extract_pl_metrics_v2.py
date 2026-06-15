"""
Extract key P&L metrics: Turnover, Operating Profit, Profit Before Tax, Profit/(Loss) for Financial Year
Handles different formatting and naming conventions across documents.
FIXED: Skip small reference numbers and get the actual metric values
"""

import re
import json
from pathlib import Path
from typing import Dict, Optional, Tuple, List

def extract_number(text: str) -> Optional[float]:
    """Extract numeric value from text, handling accounting formats."""
    text = text.strip()
    if not text:
        return None

    # Remove currency markers that can confuse number parsing
    cleaned = text.replace("€", "").replace("$", "").replace("£", "")
    matches = re.findall(r"\(?-?\d[\d,]*\.?\d*\)?", cleaned)
    if not matches:
        return None

    candidates: List[float] = []
    for token in matches:
        token = token.strip()
        is_negative = token.startswith("(") and token.endswith(")")
        raw = token.strip("()").replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue

        if is_negative:
            value = -value
        # Skip obvious year-like noise that is often captured in OCR text
        if abs(value) in {2014.0, 2015.0, 2016.0, 2017.0, 2018.0, 2019.0, 2020.0, 2021.0, 2022.0, 2023.0, 2024.0, 2025.0, 2026.0}:
            continue
        candidates.append(value)

    if not candidates:
        return None
    # Prefer the largest magnitude number on the line (usually the financial amount)
    return max(candidates, key=lambda x: abs(x))


def extract_lines_from_json(json_path: Path) -> List[str]:
    """Extract textual lines from a companion JSON file if present."""
    if not json_path.exists():
        return []

    try:
        with open(json_path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    lines: List[str] = []

    # Prefer page-level text when available (contains full statement tables).
    text_obj = data.get("text")
    if isinstance(text_obj, dict):
        by_page = text_obj.get("by_page", [])
        if by_page:
            for page in by_page:
                page_text = page.get("text") if isinstance(page, dict) else None
                if isinstance(page_text, str) and page_text.strip():
                    lines.extend([ln.strip() for ln in page_text.splitlines() if ln.strip()])

        if not lines:
            full_text = text_obj.get("full_text")
            if isinstance(full_text, str) and full_text.strip():
                lines.extend([ln.strip() for ln in full_text.splitlines() if ln.strip()])

    # Fallback format: page->blocks->lines->spans
    if not lines:
        for page in data.get("pages", []):
            for block in page.get("blocks", []):
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    if not spans:
                        continue
                    text = " ".join((span.get("text") or "").strip() for span in spans).strip()
                    if text:
                        lines.append(text)

    # Deduplicate while preserving order
    deduped: List[str] = []
    seen = set()
    for line in lines:
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    lines = deduped
    return lines


def extract_statement_source_text(json_path: Path) -> str:
    """Return best available text for statement parsing from companion JSON."""
    if not json_path.exists():
        return ""
    try:
        with open(json_path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return ""

    text_obj = data.get("text")
    if isinstance(text_obj, dict):
        by_page = text_obj.get("by_page", [])
        page_texts = [
            page.get("text", "")
            for page in by_page
            if isinstance(page, dict) and isinstance(page.get("text"), str) and page.get("text").strip()
        ]
        if page_texts:
            return "\n\n".join(page_texts)

        full_text = text_obj.get("full_text")
        if isinstance(full_text, str) and full_text.strip():
            return full_text

    lines = extract_lines_from_json(json_path)
    return "\n".join(lines)


def extract_full_text_from_json(json_path: Path) -> str:
    """Return full extracted text from companion JSON when available."""
    if not json_path.exists():
        return ""
    try:
        with open(json_path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return ""

    text_obj = data.get("text")
    if isinstance(text_obj, dict):
        full_text = text_obj.get("full_text")
        if isinstance(full_text, str):
            return full_text
    return ""


def parse_accounting_token(token: str) -> Optional[float]:
    token = token.strip()
    if not token:
        return None
    is_negative = token.startswith("(") and token.endswith(")")
    raw = token.strip("()").replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    return -value if is_negative else value


def parse_amount_token(token: str) -> Optional[float]:
    """Parse table amounts, including OCR-corrupted tokens (e.g. 796,1Sl -> 796151)."""
    token = token.strip()
    if not token:
        return None
    is_negative = ("(" in token and ")" in token) or token.startswith("-")

    ocr_decimal = re.match(r"(\d),(\d{2})\.(\d)", token.strip("()"))
    if ocr_decimal:
        value = float(f"{ocr_decimal.group(1)}{ocr_decimal.group(2)}{ocr_decimal.group(3)}")
        return -value if is_negative else value

    value = parse_accounting_token(re.sub(r"[^0-9,().\-]", "", token))
    if value is not None and abs(value) >= 10:
        return -abs(value) if is_negative and value > 0 else value

    if "," in token:
        parts = token.split(",")
        left = re.sub(r"\D", "", parts[0])
        right = re.sub(r"\D", "", parts[1]) if len(parts) > 1 else ""
        if len(left) == 3 and len(right) >= 2:
            combined = left + right
        else:
            combined = left + right
        if len(combined) >= 4:
            value = float(combined)
            return -value if is_negative else value

    digits = "".join(re.findall(r"\d", token))
    if len(digits) >= 4:
        value = float(digits)
        return -value if is_negative else value
    return value


def normalize_pl_label(line: str) -> str:
    """Collapse OCR noise on P&L row labels for fuzzy matching."""
    s = re.sub(r"[^a-z0-9]", "", line.lower())
    s = s.replace("1", "l").replace("0", "o")
    replacements = (
        ("turniwer", "turnover"),
        ("operatingpol1e", "operatingprofit"),
        ("operatingpolit", "operatingprofit"),
        ("operatingprofit", "operatingprofit"),
        ("prootbefore", "profitbefore"),
        ("profitbeforetaxation", "profitbeforetax"),
        ("profitonordinaryactivitiesbeforetaxation", "profitbeforetax"),
        ("lossforthefinanchd", "profitforthefinancialyear"),
        ("profitforthefinanchd", "profitforthefinancialyear"),
        ("profitforthefinancialyear", "profitforthefinancialyear"),
        ("rotltandloss", "profitandloss"),
    )
    for old, new in replacements:
        s = s.replace(old, new)
    return s


def fuzzy_has_turnover(text: str) -> bool:
    low = text.lower()
    if "turnover" in low:
        return True
    if re.search(r"turn\W*wer", low, re.IGNORECASE):
        return True
    return "turniwer" in normalize_pl_label(low)


def extract_table_metric_from_block(block: str, pattern: str) -> Optional[float]:
    m = re.search(pattern, block, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    token = m.group(1)
    return parse_accounting_token(token)


STATEMENT_HEADING_RE = re.compile(
    r"(?:profit\s+and\s+loss\s+account|statement\s+of\s+profit\s+and\s+loss|"
    r"p\.?\s*rotlt\s+and\s+.*loss\s+acct)",
    re.IGNORECASE,
)

INTERLEAVED_YEAR_HEADER_RE = re.compile(
    r"\b(20\d{2})\s*\n\s*(20\d{2})\s*\n"
    r"(?:[^\n]*(?:€|\$|£|\?000|000)[^\n]*\n){1,3}",
    re.IGNORECASE,
)


def find_interleaved_year_header(block: str) -> Optional[re.Match]:
    """Find two distinct year columns before currency markers (not duplicate headings)."""
    for match in INTERLEAVED_YEAR_HEADER_RE.finditer(block):
        y1, y2 = int(match.group(1)), int(match.group(2))
        if y1 != y2:
            return match
    return None


def infer_year_from_stem(stem: str) -> Optional[int]:
    match = re.search(r"(20\d{2})", stem)
    return int(match.group(1)) if match else None


def find_best_statement_block(full_text: str) -> str:
    """Locate the income statement table section in extracted text."""
    direct_patterns = [
        (
            r"Profit and loss account and other comprehensive income\s+"
            r"for the year ended.*?(?=\n\s*Balance sheet\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        (
            r"Statement of Profit and Loss\s+"
            r"for the year ended.*?(?=\n\s*Statement of Other|\n\s*Balance Sheet\b)",
            re.IGNORECASE | re.DOTALL,
        ),
    ]
    for pattern, flags in direct_patterns:
        match = re.search(pattern, full_text, flags)
        if match and fuzzy_has_turnover(match.group(0)):
            return match.group(0)

    starts = list(STATEMENT_HEADING_RE.finditer(full_text))
    if not starts:
        return ""

    best_block = ""
    best_score = -1
    for sm in starts:
        tail = full_text[sm.start() :]
        end_match = re.search(
            r"\n\s*(?:balance sheet|statement of financial position)\b",
            tail,
            re.IGNORECASE,
        )
        block = tail[: end_match.start()] if end_match else tail[:6000]
        block_lower = block.lower()
        first_chunk = block_lower[:1200]

        # Skip obvious non-statement hits (auditor report, balance sheet, notes-only).
        if not fuzzy_has_turnover(first_chunk):
            continue
        if "tangible fixed assets" in first_chunk or "current assets" in first_chunk:
            continue
        if "independent auditor" in first_chunk:
            continue

        score = 0
        if "for the year ended" in block_lower or "for the financial year ended" in block_lower:
            score += 8
        if "other comprehensive income" in block_lower:
            score += 4
        if fuzzy_has_turnover(first_chunk):
            score += 6
        if "cost of sales" in block_lower:
            score += 2
        if "gross profit" in block_lower:
            score += 2
        if "operating profit" in block_lower:
            score += 3
        if "before taxation" in block_lower or "before tax" in block_lower:
            score += 2
        if re.search(r"20\d{2}\s*\n\s*€'?000", block, re.IGNORECASE):
            score += 5
        if "contents" in block_lower:
            score -= 6
        if "directors' report" in first_chunk:
            score -= 5
        if score > best_score:
            best_score = score
            best_block = block

    if best_block:
        return best_block

    # OCR fallback: score page-sized chunks (e.g. Gartner 2018/2019 garbled headings).
    for chunk in full_text.split("\n\n"):
        chunk_lower = chunk.lower()
        score = 0
        if re.search(r"for the (?:financial )?year ended", chunk, re.IGNORECASE):
            score += 8
        if fuzzy_has_turnover(chunk):
            score += 6
        if "cost of sales" in chunk_lower or "costofsales" in normalize_pl_label(chunk):
            score += 2
        if find_interleaved_year_header(chunk):
            score += 5
        if re.search(r"20\d{2}\s*\n\s*€'?000", chunk, re.IGNORECASE):
            score += 5
        if re.search(r"\b\d{3},\d{3}\b", chunk):
            score += 4
        if "independent auditor" in chunk_lower[:600]:
            score -= 8
        if len(chunk) > 1800:
            score -= 6
        if re.search(r"\b796[,\d]", chunk):
            score += 4
        if score > best_score:
            best_score = score
            best_block = chunk
    return best_block


def extract_inline_pl_metrics(block: str) -> Dict[str, Optional[float]]:
    """Extract metrics from row-style P&L tables (label + current/prior year columns)."""
    profit_for_year = extract_table_metric_from_block(
        block,
        r"Total\s+comprehensive\s+income(?:/\(loss\))?\s+for\s+the\s+financial\s+year\s*(\(?-?\d[\d,]*\)?)",
    )
    if profit_for_year is None:
        profit_for_year = extract_table_metric_from_block(
            block,
            r"Profit(?:\s*/\(loss\))?\s+for\s+the\s+financial\s+year\s*(\(?-?\d[\d,]*\)?)",
        )

    return {
        "turnover": extract_table_metric_from_block(
            block, r"Turnover\s+\d+\s+(\(?-?\d[\d,]*\)?)"
        ),
        "operating_profit": extract_table_metric_from_block(
            block, r"Operating\s+profit(?:\s*/\(loss\))?\s*(\(?-?\d[\d,]*\)?)"
        ),
        "profit_before_tax": extract_table_metric_from_block(
            block,
            r"(?:Profit|Loss)[^\n]{0,80}before\s+taxation\s+\d+\s+(\(?-?\d[\d,]*\)?)",
        ),
        "profit_loss_for_year": profit_for_year,
    }


def pl_label_section(block: str) -> str:
    """Label-only portion of a columnar P&L block (exclude numeric tail)."""
    end = len(block)
    note_match = re.search(r"\n\s*Note\b", block, re.IGNORECASE)
    if note_match:
        end = min(end, note_match.start())
    year_hdr = find_interleaved_year_header(block)
    if year_hdr:
        end = min(end, year_hdr.start())
    return block[:end]


def parse_columnar_rows(block: str) -> List[str]:
    """Return normalized row labels from a column-style P&L table."""
    rows: List[str] = []
    stop_markers = (
        "all activities in current",
        "the notes on pages",
        "derived from continuing",
    )
    for line in pl_label_section(block).splitlines():
        low = line.strip().lower()
        if not low:
            continue
        if any(marker in low for marker in stop_markers):
            break
        if low.startswith("statement of") or "for the year ended" in low:
            continue
        if low.startswith("profit and loss account"):
            continue
        if re.fullmatch(r"\d+", low):
            continue
        rows.append(low)
    return rows


def columnar_row_index(
    rows: List[str], *patterns: str, exclude: Optional[Tuple[str, ...]] = None
) -> Optional[int]:
    normalized_patterns = [normalize_pl_label(p) for p in patterns]
    exclude_norm = [normalize_pl_label(e) for e in (exclude or ())]
    for idx, row in enumerate(rows):
        row_norm = normalize_pl_label(row)
        if exclude_norm and any(e in row_norm for e in exclude_norm):
            continue
        if any(p in row_norm for p in normalized_patterns):
            return idx
        if any(pattern in row for pattern in patterns):
            return idx
    return None


def resolve_target_year(
    stem_year: Optional[int],
    report_year: Optional[int],
    available_years: List[int],
) -> Tuple[Optional[int], List[str]]:
    """Pick statement column year from filename vs report year vs available columns."""
    notes: List[str] = []
    if not available_years:
        return stem_year or report_year, notes

    if stem_year and report_year and stem_year == report_year and stem_year in available_years:
        return stem_year, notes

    if stem_year and stem_year in available_years:
        if report_year and stem_year < report_year:
            notes.append(
                f"using comparative column {stem_year} from FY{report_year} report"
            )
        return stem_year, notes

    if report_year and report_year in available_years:
        if stem_year and stem_year not in available_years:
            notes.append(
                f"filename year {stem_year} not in statement columns {sorted(available_years)}; "
                f"using report year {report_year}"
            )
        return report_year, notes

    return available_years[0], notes


def extract_interleaved_columnar_pl_metrics(
    block: str, target_year: int
) -> Dict[str, Optional[float]]:
    """
    P&L tables with two year headers then one currency row and interleaved values:
      2018 / 2017 / €'000 / 668,926 / 600,975 / ...
    """
    result: Dict[str, Optional[float]] = {
        "turnover": None,
        "operating_profit": None,
        "profit_before_tax": None,
        "profit_loss_for_year": None,
    }
    header = find_interleaved_year_header(block)
    if not header:
        return result

    y_current, y_prior = int(header.group(1)), int(header.group(2))
    if y_current == y_prior:
        return result

    chunk = block[header.end() :]
    raw_tokens = re.findall(r"\([^)]*\)|[-]?\d[\d,.\w]{0,14}", chunk)
    values: List[float] = []
    for token in raw_tokens:
        parsed = parse_amount_token(token)
        if parsed is None:
            continue
        if abs(parsed) in {
            2.0, 3.0, 4.0, 5.0, 7.0, 8.0, 9.0, 11.0, 14.0, 15.0, 34.0,
        }:
            continue
        values.append(parsed)

    if len(values) < 4:
        return result

    columns = {y_current: values[0::2], y_prior: values[1::2]}
    if target_year not in columns:
        return result

    rows = parse_columnar_rows(block)
    if not rows:
        return result

    year_values = columns[target_year]
    # Gartner interleaved layout (labels then paired €'000 values).
    default_rows = {
        "turnover": 0,
        "operating_profit": 4,
        "profit_before_tax": 7,
        "profit_loss_for_year": 9,
    }
    label_rows = {
        "turnover": columnar_row_index(rows, "turnover"),
        "operating_profit": columnar_row_index(rows, "operating profit", "operating p"),
        "profit_before_tax": columnar_row_index(
            rows,
            "before taxation",
            "profit before taxation",
            "profit on ordinary activities before",
            exclude=("tax on profit", "tax on loss"),
        ),
        "profit_loss_for_year": columnar_row_index(
            rows,
            "profit for the financial year",
            "loss for the financial year",
            "profit for the financhd",
            "loss for the financhd",
        ),
    }
    for metric_name, default_idx in default_rows.items():
        row_idx = label_rows.get(metric_name)
        if row_idx is None or row_idx >= len(year_values):
            row_idx = default_idx
        if row_idx < len(year_values):
            result[metric_name] = year_values[row_idx]
    return result


def extract_ocr_gartner_pair_metrics(
    block: str, target_year: int
) -> Dict[str, Optional[float]]:
    """Heavily OCR-corrupted Gartner tables with paired numeric lines (e.g. 2019)."""
    result: Dict[str, Optional[float]] = {
        "turnover": None,
        "operating_profit": None,
        "profit_before_tax": None,
        "profit_loss_for_year": None,
    }
    if not re.search(r"796[,\d\w]", block, re.IGNORECASE):
        return result

    values: List[float] = []
    for line in block.splitlines():
        parsed = parse_amount_token(line.strip())
        if parsed is None:
            continue
        if abs(parsed) < 80 and parsed > 0:
            continue
        values.append(parsed)

    if len(values) < 6:
        return result

    current_col = values[0::2]
    row_map = {
        "turnover": 0,
        "operating_profit": 4,
        "profit_before_tax": 7,
        "profit_loss_for_year": 9,
    }
    for metric, idx in row_map.items():
        if idx < len(current_col):
            result[metric] = current_col[idx]
    return result


def extract_columnar_pl_metrics(block: str, target_year: int) -> Dict[str, Optional[float]]:
    """
    Extract metrics from P&L tables where values are listed under year headers
    (e.g. 2015 / 2014 columns with €'000 rows).
    """
    result: Dict[str, Optional[float]] = {
        "turnover": None,
        "operating_profit": None,
        "profit_before_tax": None,
        "profit_loss_for_year": None,
    }

    year_chunks = list(
        re.finditer(r"(20\d{2})\s*\n\s*€'?000\s*\n", block, re.IGNORECASE)
    )
    if not year_chunks:
        return result

    columns: Dict[int, List[float]] = {}
    for idx, ym in enumerate(year_chunks):
        year = int(ym.group(1))
        start = ym.end()
        end = year_chunks[idx + 1].start() if idx + 1 < len(year_chunks) else len(block)
        chunk = block[start:end]
        values = [
            parse_amount_token(token)
            for token in re.findall(r"\([^)]*\)|\(?-?\d[\d,.\w]*\)?", chunk)
        ]
        columns[year] = [v for v in values if v is not None]

    if target_year not in columns:
        return result

    rows = parse_columnar_rows(block)
    if not rows:
        return result

    year_values = columns[target_year]
    metric_row_map = {
        "turnover": columnar_row_index(rows, "turnover"),
        "operating_profit": columnar_row_index(rows, "operating profit"),
        "profit_before_tax": columnar_row_index(
            rows, "before taxation", "before tax"
        ),
        "profit_loss_for_year": columnar_row_index(
            rows, "profit for the financial year"
        ),
    }
    for metric_name, row_idx in metric_row_map.items():
        if row_idx is not None and row_idx < len(year_values):
            result[metric_name] = year_values[row_idx]
    return result


def extract_metrics_from_statement_block(
    full_text: str, filename_stem: str = ""
) -> Dict[str, Optional[float]]:
    """
    Extract key values from the explicit Profit and Loss statement block.
    Supports inline row tables and year-column tables (page 9 style).
    """
    result: Dict[str, Optional[float]] = {
        "turnover": None,
        "operating_profit": None,
        "profit_before_tax": None,
        "profit_loss_for_year": None,
    }
    if not full_text:
        return result

    block = find_best_statement_block(full_text)
    if not block:
        return result

    stem_year = infer_year_from_stem(filename_stem)
    report_year_match = re.search(
        r"for the (?:financial )?year ended .*? (20\d{2})",
        block,
        re.IGNORECASE,
    )
    report_year = int(report_year_match.group(1)) if report_year_match else None

    # Column-style tables (stacked years or interleaved year columns).
    has_stacked = bool(re.search(r"20\d{2}\s*\n\s*€'?000", block, re.IGNORECASE))
    interleaved_header = find_interleaved_year_header(block)
    has_interleaved = interleaved_header is not None
    if has_stacked or has_interleaved:
        available_years: List[int] = []
        if has_stacked:
            available_years = [
                int(m.group(1))
                for m in re.finditer(r"(20\d{2})\s*\n\s*€'?000", block, re.IGNORECASE)
            ]
        elif interleaved_header:
            available_years = [
                int(interleaved_header.group(1)),
                int(interleaved_header.group(2)),
            ]

        target_year, year_notes = resolve_target_year(
            stem_year, report_year, available_years
        )
        if target_year:
            column_metrics = extract_columnar_pl_metrics(block, target_year)
            if not any(column_metrics.values()) and has_interleaved:
                column_metrics = extract_interleaved_columnar_pl_metrics(
                    block, target_year
                )
            elif has_interleaved and stem_year == report_year:
                interleaved_metrics = extract_interleaved_columnar_pl_metrics(
                    block, target_year
                )
                for key, value in interleaved_metrics.items():
                    if value is not None:
                        column_metrics[key] = value

            for key, value in column_metrics.items():
                if value is not None:
                    result[key] = value
            if any(result.values()):
                return result

        ocr_year = target_year or stem_year or report_year
        ocr_metrics = extract_ocr_gartner_pair_metrics(block, ocr_year or 0)
        for key, value in ocr_metrics.items():
            if value is not None and result.get(key) is None:
                result[key] = value
        if any(result.values()):
            return result

    # Inline row tables (e.g. ArcRoyal 138763_2021)
    inline_metrics = extract_inline_pl_metrics(block)
    for key, value in inline_metrics.items():
        if value is not None:
            result[key] = value
    return result


def find_income_statement_start(lines: List[str]) -> int:
    """
    Find the best income statement section start.
    Prefer explicit income-statement headings that are near common row labels.
    """
    heading_terms = ("income statement", "profit and loss", "profit & loss")
    row_terms = (
        "turnover",
        "cost of sales",
        "gross profit",
        "operating",
        "before tax",
        "for the financial year",
    )

    best_idx = 0
    best_score = -1
    for i, line in enumerate(lines):
        low = line.lower()
        if not any(term in low for term in heading_terms):
            continue

        # score this heading by row-label density nearby
        nearby = lines[i : i + 120]
        score = 0
        if "for the year ended" in low or "for the financial year ended" in low:
            score += 8
        if "other comprehensive income" in low:
            score += 10
        for nl in nearby:
            nlow = nl.lower()
            if any(rt in nlow for rt in row_terms):
                score += 1
            if "€'000" in nlow or "$000" in nlow or nlow.strip() == "note":
                score += 1
            if "contents" in nlow or "directors" in nlow:
                score -= 1
        if score > best_score:
            best_score = score
            best_idx = i

    return best_idx


def is_narrative_line(line: str) -> bool:
    """Heuristic: narrative prose lines should not be used as metric rows."""
    low = line.lower()
    words = [w for w in re.split(r"\s+", low.strip()) if w]
    if len(words) > 14:
        return True
    narrative_markers = (
        "the company",
        "recorded",
        "therefore",
        "during the year",
        "directors",
        "report",
        "notes to the financial statements",
    )
    return any(marker in low for marker in narrative_markers)


def extract_numbers_in_order(text: str) -> List[float]:
    """Extract numbers in text order, including accounting negatives."""
    cleaned = text.replace("€", "").replace("$", "").replace("£", "")
    matches = re.finditer(r"\(?-?\d[\d,]*\.?\d*\)?", cleaned)
    out: List[float] = []
    for m in matches:
        token = m.group(0).strip()
        is_negative = token.startswith("(") and token.endswith(")")
        raw = token.strip("()").replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        if is_negative:
            value = -value
        if abs(value) in {
            2014.0, 2015.0, 2016.0, 2017.0, 2018.0, 2019.0, 2020.0, 2021.0,
            2022.0, 2023.0, 2024.0, 2025.0, 2026.0
        }:
            continue
        out.append(value)
    return out


def extract_value_after_keyword(line: str, keyword: str, min_abs: float) -> Optional[float]:
    """
    Prefer value tokens appearing after keyword on same line.
    Example: Turnover 2 34,711 38,685 -> choose 34,711.
    """
    low = line.lower()
    idx = low.find(keyword.lower())
    if idx < 0:
        return None
    segment = line[idx + len(keyword) :]
    values = extract_numbers_in_order(segment)
    if not values:
        return None

    filtered = [v for v in values if abs(v) >= min_abs]
    if filtered:
        return filtered[0]
    return values[0]

def find_metric_value(
    lines: list, keywords: list, context_lines: int = 10, min_abs: float = 1.0
) -> Optional[Tuple[float, int]]:
    """
    Find a metric by searching for keywords and extracting the numeric value.
    Skips small reference numbers and gets the actual metric value.
    Returns (value, line_number) or None if not found.
    """
    for i, line in enumerate(lines):
        line_lower = line.lower()
        matched_keyword = next(
            (keyword for keyword in keywords if keyword.lower() in line_lower),
            None,
        )
        if matched_keyword:
            same_line_from_keyword = extract_value_after_keyword(
                line, matched_keyword, min_abs=min_abs
            )
            if (
                same_line_from_keyword is not None
                and abs(same_line_from_keyword) >= min_abs
                and not is_narrative_line(line)
            ):
                return (same_line_from_keyword, i)

            # First try same line (many statements are "Label 123,456")
            same_line_value = extract_number(line)
            if (
                same_line_value is not None
                and abs(same_line_value) >= min_abs
                and not is_narrative_line(line)
            ):
                return (same_line_value, i)

            # Then look ahead for values, skipping small reference numbers
            for j in range(1, context_lines + 1):
                if i + j < len(lines):
                    next_line = lines[i + j].strip()
                    if len(next_line) > 2:
                        value = extract_number(next_line)
                        if (
                            value is not None
                            and abs(value) >= min_abs
                            and not is_narrative_line(next_line)
                        ):
                            # Accept value-like rows quickly; OCR often splits rows
                            if abs(value) >= min_abs or j >= 2:
                                return (value, i + j)
    
    return None

def extract_pl_metrics(file_path: Path) -> Dict:
    """Extract P&L metrics from a single file."""
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        txt_lines = content.split('\n')

    # Try companion JSON first, then append TXT lines as fallback/source fusion.
    base_name = file_path.stem.replace("_pl", "")
    companion_json = file_path.parent / f"{base_name}.json"
    json_lines = extract_lines_from_json(companion_json)
    lines = json_lines + txt_lines if json_lines else txt_lines
    statement_source_text = extract_statement_source_text(companion_json)
    if not statement_source_text:
        statement_source_text = "\n".join(json_lines) if json_lines else content

    filename = file_path.stem
    
    metrics = {
        'filename': filename,
        'file_path': str(file_path),
        'turnover': None,
        'operating_profit': None,
        'profit_before_tax': None,
        'profit_loss_for_year': None,
        'currency': None,
        'raw_data': [],
        'confidence': 'low'
    }

    # First pass: read directly from statement table block when available.
    block_metrics = extract_metrics_from_statement_block(
        statement_source_text, filename_stem=base_name
    )
    for key in ["turnover", "operating_profit", "profit_before_tax", "profit_loss_for_year"]:
        if block_metrics.get(key) is not None:
            metrics[key] = block_metrics[key]
            metrics["raw_data"].append(f"{key}: statement-block extraction")
    
    # Detect currency (prefer statement JSON text over noisy pl.txt OCR).
    if "€" in statement_source_text or re.search(r"€'?000", statement_source_text):
        metrics["currency"] = "EUR"
    elif "£" in statement_source_text:
        metrics["currency"] = "GBP"
    elif "$" in statement_source_text:
        metrics["currency"] = "USD"
    else:
        currency_source = content + statement_source_text
        if "$" in currency_source:
            metrics["currency"] = "USD"
        elif "€" in currency_source:
            metrics["currency"] = "EUR"
        elif "£" in currency_source:
            metrics["currency"] = "GBP"
        else:
            metrics["currency"] = "Unknown"
    
    # Find Income Statement section
    income_statement_start = find_income_statement_start(lines)

    # Primary pass: search the statement neighborhood first.
    search_lines = lines[income_statement_start : income_statement_start + 220]
    if not search_lines:
        search_lines = lines
    
    # Search for Turnover
    turnover_keywords = ['turnover', 'revenue', 'sales revenue', 'net sales', 'total revenue']
    result = find_metric_value(search_lines, turnover_keywords, min_abs=500.0)
    if result and metrics['turnover'] is None:
        metrics['turnover'], line_num = result
        metrics['raw_data'].append(f"Turnover: {search_lines[line_num].strip()[:80]}")
    
    # Search for Operating Profit
    op_profit_keywords = ['operating profit', 'operating loss', 'operating (loss)', 'operating income', 'ebit', 'operating result']
    result = find_metric_value(search_lines, op_profit_keywords, min_abs=50.0)
    if result and metrics['operating_profit'] is None:
        metrics['operating_profit'], line_num = result
        metrics['raw_data'].append(f"Operating Profit: {search_lines[line_num].strip()[:80]}")
    
    # Search for Profit Before Tax
    pbt_keywords = ['profit before tax', 'loss before tax', '(loss)/profit before', 
                   'profit before income tax', 'loss before income tax', '(loss) /profit before', 'pbt', 'ebt']
    result = find_metric_value(search_lines, pbt_keywords, min_abs=50.0)
    if result and metrics['profit_before_tax'] is None:
        metrics['profit_before_tax'], line_num = result
        metrics['raw_data'].append(f"Profit Before Tax: {search_lines[line_num].strip()[:80]}")
        metrics['confidence'] = 'high'
    
    # Search for Profit/Loss for Year
    pfy_keywords = ['profit for the financial year', 'loss for the financial year',
                   '(loss)/profit for the financial year', 'profit for the year',
                   'loss for the year', 'net income', 'net loss', 'profit after tax', 'profit after taxation']
    result = find_metric_value(search_lines, pfy_keywords, min_abs=50.0)
    if result and metrics['profit_loss_for_year'] is None:
        metrics['profit_loss_for_year'], line_num = result
        metrics['raw_data'].append(f"Profit/Loss for Year: {search_lines[line_num].strip()[:80]}")
        metrics['confidence'] = 'high'

    # Secondary fallback pass on full text for any still-missing metrics.
    # Skip when statement block already populated metrics (avoids OCR garbage overrides).
    statement_populated = sum(
        1 for key in ("turnover", "operating_profit", "profit_before_tax", "profit_loss_for_year")
        if any(f"{key}: statement-block" in note for note in metrics["raw_data"])
    )
    if statement_populated >= 2:
        pass
    elif any(
        metrics[k] is None
        for k in ['turnover', 'operating_profit', 'profit_before_tax', 'profit_loss_for_year']
    ):
        fallback_lines = lines
        if metrics['turnover'] is None:
            result = find_metric_value(fallback_lines, turnover_keywords, min_abs=500.0)
            if result:
                metrics['turnover'], line_num = result
                metrics['raw_data'].append(f"Turnover: {fallback_lines[line_num].strip()[:80]}")
        if metrics['operating_profit'] is None:
            result = find_metric_value(fallback_lines, op_profit_keywords, min_abs=50.0)
            if result:
                metrics['operating_profit'], line_num = result
                metrics['raw_data'].append(f"Operating Profit: {fallback_lines[line_num].strip()[:80]}")
        if metrics['profit_before_tax'] is None:
            result = find_metric_value(fallback_lines, pbt_keywords, min_abs=50.0)
            if result:
                metrics['profit_before_tax'], line_num = result
                metrics['raw_data'].append(f"Profit Before Tax: {fallback_lines[line_num].strip()[:80]}")
        if metrics['profit_loss_for_year'] is None:
            result = find_metric_value(fallback_lines, pfy_keywords, min_abs=50.0)
            if result:
                metrics['profit_loss_for_year'], line_num = result
                metrics['raw_data'].append(f"Profit/Loss for Year: {fallback_lines[line_num].strip()[:80]}")
    
    # Raise confidence if multiple fields were populated.
    populated = sum(
        1 for key in ['turnover', 'operating_profit', 'profit_before_tax', 'profit_loss_for_year']
        if metrics[key] is not None
    )
    if populated >= 3:
        metrics['confidence'] = 'high'
    elif populated >= 1 and metrics['confidence'] == 'low':
        metrics['confidence'] = 'medium'

    return metrics

def process_all_pl_files():
    """Process all P&L files and save cleaned data."""

    workspace = Path(__file__).resolve().parent
    pl_files = sorted(workspace.glob('*_pl.txt'))
    
    print(f"Found {len(pl_files)} P&L files")
    
    output_folder = workspace / 'pl_metrics_cleaned'
    output_folder.mkdir(exist_ok=True)
    
    all_metrics = []
    
    for file_path in pl_files:
        print(f"Processing: {file_path.name}")
        metrics = extract_pl_metrics(file_path)
        all_metrics.append(metrics)
        
        json_output = output_folder / f"{metrics['filename']}_metrics.json"
        with open(json_output, 'w') as f:
            json.dump(metrics, f, indent=2)
    
    # Save summary CSV
    csv_output = output_folder / 'pl_metrics_summary.csv'
    with open(csv_output, 'w') as f:
        f.write('Filename,Turnover,Operating Profit,Profit Before Tax,Profit/Loss for Year,Currency\n')
        for metrics in all_metrics:
            f.write(f"{metrics['filename']},{metrics['turnover']},{metrics['operating_profit']},")
            f.write(f"{metrics['profit_before_tax']},{metrics['profit_loss_for_year']},{metrics['currency']}\n")
    
    json_all = output_folder / 'all_pl_metrics.json'
    with open(json_all, 'w') as f:
        json.dump(all_metrics, f, indent=2)
    
    print(f"\nExtracted {len(all_metrics)} files")
    print(f"Results saved to: {output_folder}")
    
    return all_metrics

if __name__ == '__main__':
    metrics = process_all_pl_files()
    
    print("\n=== Top Companies by Turnover ===")
    with_turnover = [m for m in metrics if m['turnover'] is not None]
    with_turnover.sort(key=lambda x: x['turnover'], reverse=True)
    
    for m in with_turnover[:5]:
        print(f"\n{m['filename']} ({m['currency']})")
        print(f"  Turnover: {m['turnover']:,.0f}")
        if m['operating_profit']:
            print(f"  Operating Profit: {m['operating_profit']:,.0f}")
        if m['profit_loss_for_year']:
            print(f"  Net Profit: {m['profit_loss_for_year']:,.0f}")
