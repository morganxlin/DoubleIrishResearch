#!/usr/bin/env python3
"""
PDF Attribute Extractor - Extracts all attributes from a PDF document.
Includes: metadata, text, images, links, annotations, form fields, outline, and more.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import List, Optional

try:
    import fitz  # type: ignore[import-untyped]  # PyMuPDF (package name: pymupdf)
except ImportError:
    print("Installing PyMuPDF... run: pip install pymupdf")
    sys.exit(1)


def extract_metadata(doc: fitz.Document) -> dict:
    """Extract all document metadata (standard and custom)."""
    meta = doc.metadata
    result = {}
    for key, value in meta.items():
        if value:
            result[key] = value
    result["page_count"] = doc.page_count
    return result


def extract_page_attributes(doc: fitz.Document, page_num: int) -> dict:
    """Extract attributes for a single page."""
    page = doc[page_num]
    rect = page.rect

    return {
        "page_number": page_num + 1,
        "width": round(rect.width, 2),
        "height": round(rect.height, 2),
        "rotation": page.rotation,
        "mediabox": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
    }


def extract_text(doc: fitz.Document) -> dict:
    """Extract text from all pages (plain and by blocks)."""
    result = {"by_page": [], "full_text": ""}
    for page_num in range(doc.page_count):
        page = doc[page_num]
        text = page.get_text()
        blocks = page.get_text("dict")["blocks"]
        result["by_page"].append({
            "page": page_num + 1,
            "text": text,
            "block_count": len(blocks),
        })
        result["full_text"] += text
    return result


def extract_images(doc: fitz.Document, extract_bytes: bool = False) -> list:
    """Extract image info (and optionally image bytes) from all pages."""
    images = []
    for page_num in range(doc.page_count):
        page = doc[page_num]
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                info = {
                    "page": page_num + 1,
                    "xref": xref,
                    "width": base_image["width"],
                    "height": base_image["height"],
                    "colorspace": base_image["colorspace"],
                    "bpc": base_image["bpc"],
                    "ext": base_image["ext"],
                }
                if extract_bytes:
                    info["size_bytes"] = len(base_image["image"])
                images.append(info)
            except Exception as e:
                images.append({"page": page_num + 1, "xref": xref, "error": str(e)})
    return images


def extract_links(doc: fitz.Document) -> list:
    """Extract all links from the document."""
    links = []
    for page_num in range(doc.page_count):
        page = doc[page_num]
        for link in page.get_links():
            from_rect = None
            if "from" in link:
                r = link["from"]
                from_rect = [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]
            rect = link.get("rect")
            if rect is not None:
                rect = [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)]
            links.append({
                "page": page_num + 1,
                "kind": link.get("kind", "unknown"),
                "uri": link.get("uri", ""),
                "rect": rect,
                "from_rect": from_rect,
            })
    return links


def extract_annotations(doc: fitz.Document) -> list:
    """Extract annotations (comments, highlights, etc.) from all pages."""
    annotations = []
    for page_num in range(doc.page_count):
        page = doc[page_num]
        for ann in page.annots():
            try:
                annotations.append({
                    "page": page_num + 1,
                    "type": ann.type[1] if ann.type else None,
                    "rect": [round(ann.rect.x0, 2), round(ann.rect.y0, 2), round(ann.rect.x1, 2), round(ann.rect.y1, 2)],
                    "content": ann.info.get("content", ""),
                    "author": ann.info.get("author", ""),
                    "subject": ann.info.get("subject", ""),
                })
            except Exception as e:
                annotations.append({"page": page_num + 1, "error": str(e)})
    return annotations


def extract_form_fields(doc: fitz.Document) -> list:
    """Extract form field attributes from all pages."""
    fields = []
    for page_num in range(doc.page_count):
        page = doc[page_num]
        try:
            widget_list = page.widgets()
        except Exception:
            widget_list = []
        if not widget_list:
            continue
        for w in widget_list:
            try:
                fields.append({
                    "page": page_num + 1,
                    "field_name": getattr(w, "field_name", ""),
                    "field_type": str(getattr(w, "field_type", "")),
                    "field_value": getattr(w, "field_value", ""),
                    "rect": [round(w.rect.x0, 2), round(w.rect.y0, 2), round(w.rect.x1, 2), round(w.rect.y1, 2)],
                })
            except Exception as e:
                fields.append({"page": page_num + 1, "error": str(e)})
    return fields


def extract_outline(doc: fitz.Document) -> list:
    """Extract table of contents / outline."""
    toc = doc.get_toc()
    result = []
    for level, title, page_num in toc:
        result.append({"level": level, "title": title, "page": page_num})
    return result


def extract_fonts(doc: fitz.Document) -> list:
    """Extract font names used in the document."""
    fonts = set()
    for page_num in range(doc.page_count):
        page = doc[page_num]
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("font"):
                        fonts.add(span["font"])
    return sorted(fonts)


def _parse_pl_table_block(block: str) -> list[dict]:
    """
    Parse a profit and loss table text block into a list of rows.

    Heuristic:
    - Each non-empty line is assumed to be one row.
    - The row starts with a text label and ends with one or more numeric columns (years).
    - We capture all trailing numeric-looking tokens as values.
    """
    rows: list[dict] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Skip page numbers or lone numbers
        if re.fullmatch(r"\d+", line):
            continue
        # Split tokens
        tokens = line.split()
        if not tokens:
            continue
        # Walk from the end collecting numeric tokens
        values_rev: list[str] = []
        for tok in reversed(tokens):
            if re.fullmatch(r"[(),\-\d\.]+", tok):
                values_rev.append(tok)
            else:
                break
        if not values_rev:
            # No obvious numeric column; treat whole line as label
            rows.append({"label": line, "values": []})
            continue
        n_val = len(values_rev)
        label_tokens = tokens[:-n_val]
        label = " ".join(label_tokens).strip()
        values = list(reversed(values_rev))
        if not label:
            label = line
        rows.append({"label": label, "values": values})
    return rows


def extract_profit_and_loss_table(data: dict) -> Optional[dict]:
    """
    Best-effort extraction of the profit and loss account table.

    Returns a dict like:
    {
        "heading": "...",
        "raw_block": "...",
        "rows": [
            {"label": "Turnover", "values": ["123,456", "120,000"]},
            {"label": "Gross profit", "values": ["78,900", "75,000"]},
            ...
        ]
    }
    or None if no plausible table is found.
    """
    text = (data.get("text") or {}).get("full_text") or ""
    if not text:
        return None

    # Look for a heading like "PROFIT AND LOSS ACCOUNT" or similar.
    heading_re = re.compile(
        r"(PROFIT\s+AND\s+LOSS\s+ACCOUNT|PROFIT\s+AND\s+LOSS\s+STATEMENT|STATEMENT\s+OF\s+COMPREHENSIVE\s+INCOME)",
        re.IGNORECASE,
    )
    m = heading_re.search(text)
    if not m:
        return None

    heading = m.group(1).strip()
    after = text[m.end():]

    # Capture until a strong break: double blank line or another all-caps style heading.
    stop_re = re.compile(
        r"\n\s*\n\s*[A-Z][A-Z\s/&\-]{3,}\n"  # blank line then another big heading
    )
    stop = stop_re.search(after)
    if stop:
        block = after[: stop.start()]
    else:
        # Fallback: limit to a few thousand characters
        block = after[:2000]

    block = block.strip()
    if not block:
        return None

    rows = _parse_pl_table_block(block)
    if not rows:
        return None

    return {"heading": heading, "raw_block": block, "rows": rows}


def get_pdf_paths(path: str | Path, recursive: bool = False) -> List[Path]:
    """Return a sorted list of PDF file paths under path (file or directory)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    if path.is_file():
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Not a PDF file: {path}")
        return [path]
    # Directory: collect all .pdf files
    if recursive:
        pdfs = sorted(path.rglob("*.pdf"), key=lambda p: str(p).lower())
    else:
        pdfs = sorted(path.glob("*.pdf"), key=lambda p: str(p).lower())
    return pdfs


def extract_all_attributes(pdf_path: str | Path, include_image_bytes: bool = False) -> dict:
    """
    Extract all attributes from a PDF file.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Load entire file into memory and open as stream so all pages are parsed
    # (avoids linearized/partial PDFs only exposing first N pages)
    pdf_bytes = pdf_path.read_bytes()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        result = {
            "source": str(pdf_path.resolve()),
            "metadata": extract_metadata(doc),
    #BG Notes: This line is doing a LOT of heavy lifting. 
            "pages": [extract_page_attributes(doc, i) for i in range(doc.page_count)],
            "text": extract_text(doc),
            "images": extract_images(doc, extract_bytes=include_image_bytes),
            "links": extract_links(doc),
            "annotations": extract_annotations(doc),
            "form_fields": extract_form_fields(doc),
            "outline": extract_outline(doc),
            "fonts": extract_fonts(doc),
            "profit_and_loss_table": None,
        }
        # Attach profit and loss table (if any) based on extracted text.
        pl = extract_profit_and_loss_table(result)
        if pl is not None:
            result["profit_and_loss_table"] = pl
        return result
    finally:
        doc.close()


def extract_current_directors(data: dict) -> Optional[str]:
    """
    Extract 'Current Directors' from extracted PDF data (metadata, form fields, or text).
    Returns the first value found (may be multi-line), or None.
    """
    # 1. Metadata (e.g. custom XMP or doc info)
    meta = data.get("metadata") or {}
    for key, value in meta.items():
        if value and "current" in key.lower() and "director" in key.lower():
            return value.strip() if isinstance(value, str) else str(value).strip()
    for key, value in meta.items():
        if value and key.lower().strip() == "current directors":
            return value.strip() if isinstance(value, str) else str(value).strip()

    # 2. Form fields (field_name contains "current" and "director", use field_value)
    for field in data.get("form_fields") or []:
        name = (field.get("field_name") or "").lower()
        if "current" in name and "director" in name:
            val = field.get("field_value") or ""
            if isinstance(val, str) and val.strip():
                return val.strip()
            if val:
                return str(val).strip()
    for field in data.get("form_fields") or []:
        name = (field.get("field_name") or "").lower()
        if "director" in name:
            val = field.get("field_value") or ""
            if isinstance(val, str) and val.strip():
                return val.strip()
            if val:
                return str(val).strip()

    # 3. Text: look for "Current Directors" then value (same line or following lines until blank/next section)
    text = (data.get("text") or {}).get("full_text") or ""
    if not text:
        return None
    # Pattern: "Current Directors" followed by : or - and optional spaces, capture rest of line
    m = re.search(r"Current\s+Directors\s*[:\-]\s*([^\n\r]+)", text, re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        if val:
            return val
    # Multi-line: "Current Directors" then newline then indented/list of names (capture until double newline or next heading)
    m = re.search(
        r"Current\s+Directors\s*[:\-]?\s*\n([\s\S]*?)(?=\n\s*\n|\n[A-Z][a-z]+[\s\w]*[:\-]|\Z)",
        text,
        re.IGNORECASE,
    )
    if m:
        val = m.group(1).strip()
        if val:
            return val
    # Fallback: any line containing "current director(s)" and a value
     # Fallback: any line containing "current director(s)" and a value
    for line in text.splitlines():
        if re.search(r"current\s+directors?\s*[:\-]", line, re.IGNORECASE):
            after = re.sub(r"^.*?Current\s+Directors?\s*[:\-]\s*", "", line, flags=re.IGNORECASE).strip()
            if after:
                return after

    # 4. Company information blocks often have a "Directors" section:
    #   Directors
    #   Name 1
    #   Name 2
    #   Secretary / Company secretary / etc...
    stop_headings = (
        r"Company\s+secretary|Secretary|Sectetaty|Sectetary|Sccrclnry|"
        r"Registered\s+number|Registered\s+office|Registered\s+office|"
        r"Statutory\s+auditors?|Auditors?|Bankers?|Solicitors?|CONTENTS|Page\s+\d+"
    )

    # 4a. Prefer explicit role lines like "Name - Director".
    role_directors: list[str] = []
    for m in re.finditer(r"^\s*([^\n\r]+?)\s*-\s*Director\b", text, re.IGNORECASE | re.MULTILINE):
        name = m.group(1).strip()
        if name:
            role_directors.append(name)
    if role_directors:
        seen: set[str] = set()
        ordered: list[str] = []
        for n in role_directors:
            k = n.casefold()
            if k in seen:
                continue
            seen.add(k)
            ordered.append(n)
        return "\n".join(ordered).strip() or None

    directors_heading = r"(?:Directors?|Ditectors|D1rectors)"
    context_re = re.compile(r"(COMPANY\s+INFORMATION|Directors[\s\S]{0,80}information)", re.IGNORECASE)
    directors_block_re = re.compile(
        rf"(?:^|\n)\s*{directors_heading}\s*\n([\s\S]*?)(?=(?:\n\s*(?:{stop_headings})\b)|\Z)",
        re.IGNORECASE,
    )
    for m in directors_block_re.finditer(text):
        # Require a nearby info-section header to avoid false positives like "Dear Directors".
        window_start = max(0, m.start() - 1200)
        if not context_re.search(text[window_start:m.start()]):
            continue

        block = m.group(1)
        lines: list[str] = []
        for raw in block.splitlines():
            s = raw.strip()
            if not s:
                continue
            if re.fullmatch(r"\d+", s):
                continue
            if re.search(r"\bDocuSign Envelope ID\b", s, re.IGNORECASE):
                continue
            if re.fullmatch(stop_headings, s, flags=re.IGNORECASE):
                break
            lines.append(s)
        if lines:
            seen: set[str] = set()
            out_lines: list[str] = []
            for ln in lines:
                k = ln.strip().casefold()
                if not k or k in seen:
                    continue
                seen.add(k)
                out_lines.append(ln.strip())
            val = "\n".join(out_lines).strip()
            if val:
                return val

    # 4c. Some "Company Information" pages list column headers first, then names later.
    header_re = re.compile(
        rf"COMPANY\s+INFORMATION[\s\S]{{0,400}}?\b{directors_heading}\b[\s\S]{{0,250}}?\bSolicitors\b",
        re.IGNORECASE,
    )
    hm = header_re.search(text)
    if hm:
        after = text[hm.end():]
        cutoff = re.search(r"(?m)^\s*\d{5,}\s*$", after)
        chunk = after[: cutoff.start()] if cutoff else after[:2000]
        secretary_names = {
            sm.group(1).strip().casefold()
            for sm in re.finditer(r"^\s*([^\n\r]+?)\s*-\s*Secretary\b", text, re.IGNORECASE | re.MULTILINE)
            if sm.group(1).strip()
        }
        names: list[str] = []
        for raw in chunk.splitlines():
            s = raw.strip()
            if not s:
                continue
            if re.fullmatch(stop_headings, s, flags=re.IGNORECASE):
                continue
            if re.fullmatch(r"\d{1,3}", s):
                continue
            if names and re.search(
                r"\b(Business\s+Park|Registered\s+office|Quay|Dublin|Galway|Ireland|Netherlands|Postbus)\b",
                s,
                re.IGNORECASE,
            ):
                break
            if names and re.search(r"\d", s) and re.search(r"[A-Za-z]", s):
                break
            if re.search(r"^(Block\s+[A-Z]|PricewaterhouseCoopers|Chartered Accountants)", s, re.IGNORECASE):
                break
            if not re.search(r"[A-Za-z]", s):
                continue
            if len(s) > 80:
                continue
            if s.casefold() in secretary_names:
                continue
            names.append(s)
        if names:
            seen: set[str] = set()
            out: list[str] = []
            for n in names:
                k = n.strip().casefold()
                if not k or k in seen:
                    continue
                seen.add(k)
                out.append(n.strip())
            return "\n".join(out).strip() or None

    return None


def extract_year_ended(data: dict) -> Optional[str]:
    """
    Extract a "year ended" / "financial year ended" date string from the PDF text/metadata.
    Returns the first match (e.g. "31 December 2020" or "29 December 2024"), else None.
    """
    meta = data.get("metadata") or {}
    for key in ("subject", "title"):
        v = meta.get(key)
        if isinstance(v, str) and v.strip():
            m = re.search(
                r"(?:year|financial\s+year)\s+ended\s+([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
                v,
                re.IGNORECASE,
            )
            if m:
                return m.group(1).strip()

    text = (data.get("text") or {}).get("full_text") or ""
    if not text:
        return None

    # Common report headings
    patterns = [
        r"(?:for\s+the\s+)?(?:financial\s+)?year\s+ended\s+([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:for\s+the\s+)?year\s+ended\s+([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:for\s+the\s+year\s+ended|year\s+ended)\s+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def extract_company_name(data: dict) -> Optional[str]:
    """
    Best-effort company name extraction.
    - Prefer PDF metadata title if it looks like a company name.
    - Else use the first prominent line in text (often all-caps), avoiding generic headings.
    """
    meta = data.get("metadata") or {}
    title = meta.get("title")
    if isinstance(title, str):
        t = title.strip()
        if t and not re.search(r"\b(annual\s+report|financial\s+statements?|report)\b", t, re.IGNORECASE):
            return t

    text = (data.get("text") or {}).get("full_text") or ""
    if not text:
        return None

    bad = re.compile(
        r"^(overall\s+certificate|annual\s+report|reports?\s+and\s+financial\s+statements?|contents|page\s*\(?s?\)?|statement|independent|docusign)\b",
        re.IGNORECASE,
    )
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if len(s) < 3 or len(s) > 80:
            continue
        if bad.search(s):
            continue
        # Heuristic: company names are often mostly letters/spaces/&/.- and contain a legal suffix.
        if re.search(r"\b(Limited|Ltd\.?|plc|DAC|Company|Corporation|Group)\b", s, re.IGNORECASE):
            return s
        # Fallback: first all-caps-ish line that isn't a heading.
        letters = re.sub(r"[^A-Za-z]+", "", s)
        if letters and letters.isupper() and not bad.search(s):
            return s
    return None


def get_json_paths(path: str | Path, recursive: bool = False) -> List[Path]:
    """Return a sorted list of .json file paths under path (file or directory)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    if path.is_file():
        if path.suffix.lower() != ".json":
            raise ValueError(f"Not a JSON file: {path}")
        return [path]
    if recursive:
        return sorted(path.rglob("*.json"), key=lambda p: str(p).lower())
    return sorted(path.glob("*.json"), key=lambda p: str(p).lower())


def main():
    if len(sys.argv) < 2:
        print("Usage: python pdf_extractor.py <path_to_pdf_or_directory> [--json] [--include-image-sizes] [--recursive]")
        print("       python pdf_extractor.py <path_to_json_directory> --directors [--recursive]")
        print("  path                Single PDF file or directory containing PDFs (or JSONs with --directors)")
        print("  --json              Output as JSON (default: human-readable)")
        print("  --include-image-sizes  Include image byte sizes in image list")
        print("  --recursive         If path is a directory, include PDFs/JSONs in subdirectories")
        print("  --directors         Extract 'Current Directors' from all JSON files in the directory")
        sys.exit(1)

    args = sys.argv[1:]
    path_arg = args[0]
    output_json = "--json" in args
    include_image_sizes = "--include-image-sizes" in args
    recursive = "--recursive" in args
    extract_directors = "--directors" in args

    # Mode: extract Current Directors from all JSON files in directory
    if extract_directors:
        try:
            json_paths = get_json_paths(path_arg, recursive=recursive)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        if not json_paths:
            print("No JSON files found.", file=sys.stderr)
            sys.exit(1)
        results = []
        for jpath in json_paths:
            try:
                data = json.loads(jpath.read_text(encoding="utf-8"))
                company_name = extract_company_name(data)
                year_ended = extract_year_ended(data)
                current_directors = extract_current_directors(data)
                results.append({
                    "file": str(jpath),
                    "company_name": company_name,
                    "year_ended": year_ended,
                    "current_directors": current_directors,
                })
                # Save as .txt in same directory, same base name as JSON
                txt_path = jpath.with_suffix(".txt")
                txt_path.write_text(
                    "Company: " + (company_name or "(not found)") + "\n"
                    "Year ended: " + (year_ended or "(not found)") + "\n"
                    "Current Directors: " + (current_directors or "(not found)") + "\n",
                    encoding="utf-8",
                )
            except Exception as e:
                results.append({"file": str(jpath), "error": str(e)})
                txt_path = jpath.with_suffix(".txt")
                txt_path.write_text(f"Error: {e}\n", encoding="utf-8")
        out = {"source": path_arg, "file_count": len(results), "current_directors": results}
        print(json.dumps(out, indent=2, default=str))
        return

    try:
        pdf_paths = get_pdf_paths(path_arg, recursive=recursive)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not pdf_paths:
        print("No PDF files found.", file=sys.stderr)
        sys.exit(1)

    results = []
    written = []
    for pdf_path in pdf_paths:
        try:
            data = extract_all_attributes(pdf_path, include_image_bytes=include_image_sizes)
            results.append({"file": str(pdf_path), "data": data})
            # Write one JSON per file, same path and base name as source, .json extension
            json_path = pdf_path.with_suffix(".json")
            json_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            written.append(str(json_path))
            # Additionally, if a profit and loss table was found, write a readable .txt file for it.
            pl = data.get("profit_and_loss_table")
            if pl:
                txt_name = pdf_path.stem + "_pl.txt"
                txt_path = pdf_path.with_name(txt_name)
                lines = []
                heading = pl.get("heading") or "Profit and Loss Account"
                lines.append(heading)
                lines.append("=" * len(heading))
                lines.append("")
                for row in pl.get("rows") or []:
                    label = row.get("label", "").strip()
                    values = row.get("values") or []
                    if values:
                        lines.append(f"{label}: " + "  ".join(values))
                    else:
                        lines.append(label)
                txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception as e:
            print(f"Error processing {pdf_path}: {e}", file=sys.stderr)
            results.append({"file": str(pdf_path), "error": str(e)})

    # Summary to stdout
    if output_json:
        out = {"source": path_arg, "file_count": len(results), "json_outputs": written}
        print(json.dumps(out, indent=2, default=str))
    else:
        lines = [f"Source: {path_arg}", f"PDF files processed: {len(results)}"]
        for p in written:
            lines.append(f"  Wrote: {p}")
        lines.append("")
        for item in results:
            if "error" in item:
                lines.append(f"--- {item['file']} ---\nError: {item['error']}\n")
            else:
                data = item["data"]
                lines.extend([
                    f"--- {item['file']} ---",
                    f"  Page count: {len(data['pages'])}",
                    f"  Images: {len(data['images'])}, Links: {len(data['links'])}, Annotations: {len(data['annotations'])}",
                    f"  Metadata: {json.dumps(data['metadata'], default=str)}",
                    "",
                ])
        print("\n".join(lines))


if __name__ == "__main__":
    main()


### THE BELOW CODE IS BASED ON ME WORKING WITH CHATGPT BASED ON ONE FINANCIAL STATEMENT (SO THERE WILL BE MORE VARIATIONS NEEDED EVENTUALLY)
# I believe by explicitly telling the code what financial statement items to extract will fix the problem we discussed on 3.23.26 (e.g., the code will try harder to extact the information that is currently missing from the other file).
# I only reviewed the income statement extractor lines (starting at approx 270), so some of theis may be reducdant 

# In this file, there are also three ways that we attempt to extract the data (however, we may only need one (i.e., the one that has the title of hte income statement). But for completeness, I kept all of hte differernt ways of doing so (along with notes for why) 

# A few other notes: 
#If the JSON comes back with status = "needs_ocr", that is not a parsing bug. It means the PDF likely has no machine-readable text layer.
#The most useful field for debugging is table_rows in the JSON, because it shows exactly what the parser extracted before standardization.
#For these filings, this contents-first method is better than using “turnover” or “gross profit” as the first locator

from __future__ import annotations

## =========================================================
## Income Statement Extractor
##
## Purpose
## -------
## This script is designed for statutory account PDFs where the
## income statement appears later in the document and is often
## listed in the table of contents.
##
## Preferred workflow
## ------------------
## 1. Find the contents page
## 2. Read the page number listed for:
##      - Statement of Comprehensive Income
##      - Profit and Loss Account
##      - Income Statement
## 3. Jump to that page
## 4. Verify that the page looks like the actual statement page
## 5. Extract the table rows and key items
##
## Why this approach?
## ------------------
## In many annual reports, words like "turnover", "taxation",
## or "profit before tax" can appear before the actual statement
## page in:
##   - directors' reports
##   - overview pages
##   - accounting policies
##   - notes
##
## So the script does NOT start by locating the statement page
## using generic line-item words alone.
##
## Important note on scanned PDFs
## ------------------------------
## If a PDF is image-only and does not contain an embedded text
## layer, PyMuPDF text extraction will fail or return empty text.
## In that case, OCR is needed first.
##
## Recommended OCR workflow:
##   OCR the PDFs first, then run this script.
##
## Installation
## ------------
## pip install pymupdf
##
## Usage examples
## --------------
## Single PDF:
##   python extract_income_statement.py "C:\\path\\file.pdf" -o "C:\\output"
##
## Folder of PDFs:
##   python extract_income_statement.py "C:\\path\\folder" -o "C:\\output" -r
##
## Output
## ------
## 1. One JSON file per PDF
## 2. One combined CSV for all PDFs
## =========================================================

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF


## =========================================================
## 1. Configuration
## =========================================================

## Titles that may identify the actual statement page
STATEMENT_TITLES = [
    "statement of comprehensive income",
    "profit and loss account",
    "income statement",
    "statement of income",
    "statement of profit and loss",
]

## Labels we want to standardize from the extracted table
STANDARD_LABELS = {
    "revenue": [
        "turnover",
        "revenue",
        "sales",
        "net sales",
        "net revenue",
        "sales revenue",
    ],
    "cost_of_sales": [
        "cost of sales",
        "cost of goods sold",
        "cost of goods",
        "cost of revenue",
        "costs of sales",
    ],
    "gross_profit": [
        "gross profit",
    ],
    "operating_profit": [
        "operating profit",
        "operating loss",
        "operating profit/(loss)",
        "operating result",
        "profit from operations",
        "operating income",
    ],
    "profit_before_tax": [
        "profit before tax",
        "profit before taxation",
        "profit/(loss) before taxation",
        "profit/(loss) before tax",
        "profit on ordinary activities before taxation",
    ],
    "taxation": [
        "taxation",
        "tax on profit",
        "tax on profit/(loss)",
        "income tax",
        "tax expense",
        "corporation tax",
        "tax on ordinary activities",
    ],
    "profit_after_tax": [
        "profit for the financial year",
        "profit/(loss) for the financial year",
        "profit for the year",
        "profit after tax",
        "net income",
        "net profit",
    ],
}

## Used only as a weak fallback signal, not the primary locator
LINE_ITEM_KEYWORDS = [
    "turnover",
    "revenue",
    "cost of sales",
    "gross profit",
    "operating profit",
    "profit before tax",
    "profit before taxation",
    "taxation",
    "profit for the financial year",
]

NUMBER_LIKE_RE = re.compile(
    r"""
    ^(
        - |
        \(?\d[\d,]*\.?\d*\)? |
        \(?\d[\d,]*\)?
    )$
    """,
    re.VERBOSE,
)

YEAR_RE = re.compile(r"^(19|20)\d{2}$")
NOTE_RE = re.compile(r"^\d+[A-Za-z]?$")


## =========================================================
## 2. Basic helpers
## =========================================================

def get_pdf_paths(path: str | Path, recursive: bool = False) -> List[Path]:
    """
    Return a sorted list of PDF paths from a file or directory.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    if path.is_file():
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Not a PDF file: {path}")
        return [path]

    if recursive:
        return sorted(path.rglob("*.pdf"), key=lambda p: str(p).lower())
    return sorted(path.glob("*.pdf"), key=lambda p: str(p).lower())


def normalize_text(s: str) -> str:
    """
    Lowercase and normalize whitespace.
    """
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("€", "")
    return s


def clean_label(label: str) -> str:
    """
    Clean whitespace and trailing punctuation from a row label.
    """
    return re.sub(r"\s+", " ", label).strip(" .:-")


def parse_accounting_number(raw: Optional[str]) -> Optional[float]:
    """
    Convert accounting-style numeric text into a float.

    Examples:
      '43,680,095'   -> 43680095.0
      '(30,836,954)' -> -30836954.0
      '-'            -> None
    """
    if raw is None:
        return None

    s = raw.strip()
    if s in {"", "-"}:
        return None

    s = s.replace("€", "").replace(",", "").strip()
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")

    try:
        val = float(s)
        return -val if negative else val
    except ValueError:
        return None


def map_label_to_standard(label: str) -> Optional[str]:
    """
    Map a raw row label to one standardized variable name.
    """
    label_norm = normalize_text(label)

    for standard_name, variants in STANDARD_LABELS.items():
        for variant in variants:
            if variant in label_norm:
                return standard_name

    return None


def is_number_like_token(token: str) -> bool:
    """
    Return True if a token looks like an accounting number or dash.
    """
    token = token.strip().replace("€", "")
    return bool(NUMBER_LIKE_RE.match(token))


def pdf_has_extractable_text(doc: fitz.Document, sample_pages: int = 5) -> bool:
    """
    Quick diagnostic:
    Returns True if at least one of the sampled pages contains text/words.

    This helps flag image-only PDFs that may need OCR first.
    """
    n = min(sample_pages, doc.page_count)
    for i in range(n):
        page = doc.load_page(i)
        text = page.get_text("text").strip()
        words = page.get_text("words")
        if text or words:
            return True
    return False


## =========================================================
## 3. Group page words into rows
##
## Why?
## ----
## The statement typically has columns:
##   label | note | current year | prior year
##
## Using word coordinates lets us rebuild rows more reliably
## than plain page text alone.
## =========================================================

def group_words_into_rows(page: fitz.Page, y_tolerance: float = 3.0) -> List[Dict[str, Any]]:
    """
    Group individual words into rows by y-position.
    """
    words = page.get_text("words")
    if not words:
        return []

    words = sorted(words, key=lambda w: (w[1], w[0]))

    grouped: List[List[tuple]] = []
    current_row: List[tuple] = []
    current_y: Optional[float] = None

    for w in words:
        x0, y0, x1, y1, text, *_ = w

        if current_y is None:
            current_y = y0
            current_row.append(w)
        elif abs(y0 - current_y) <= y_tolerance:
            current_row.append(w)
        else:
            grouped.append(current_row)
            current_row = [w]
            current_y = y0

    if current_row:
        grouped.append(current_row)

    rows: List[Dict[str, Any]] = []
    for row_words in grouped:
        row_words = sorted(row_words, key=lambda w: w[0])
        row_text = " ".join(w[4] for w in row_words).strip()
        if not row_text:
            continue

        rows.append({
            "y0": min(w[1] for w in row_words),
            "y1": max(w[3] for w in row_words),
            "x0": min(w[0] for w in row_words),
            "x1": max(w[2] for w in row_words),
            "text": row_text,
            "words": [
                {"x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3], "text": w[4]}
                for w in row_words
            ],
        })

    return rows


## =========================================================
## 4. Contents-page logic
##
## Primary goal:
## -------------
## Identify the page number listed in the table of contents for:
##   - Statement of Comprehensive Income
##   - Profit and Loss Account
##   - Income Statement
##
## This is the preferred way to locate the statement page.
## =========================================================

def score_page_as_contents(page: fitz.Page) -> int:
    """
    Score a page for how likely it is to be the table of contents.

    We look for:
      - the word 'contents'
      - multiple lines ending with page numbers
      - statement titles listed in the page text
    """
    text = normalize_text(page.get_text("text"))
    if not text:
        return 0

    score = 0

    if "contents" in text:
        score += 10

    lines = [line.strip() for line in page.get_text("text").splitlines() if line.strip()]
    page_number_line_count = 0
    for line in lines:
        if re.search(r"\b\d{1,3}\s*$", line):
            page_number_line_count += 1

    score += min(page_number_line_count, 10)

    for title in STATEMENT_TITLES:
        if title in text:
            score += 5

    return score


def find_contents_page(doc: fitz.Document, max_pages_to_check: int = 8) -> Optional[int]:
    """
    Search the early part of the document for the contents page.
    Returns a 0-based page number, or None.
    """
    best_page = None
    best_score = -1

    for i in range(min(max_pages_to_check, doc.page_count)):
        page = doc.load_page(i)
        score = score_page_as_contents(page)
        if score > best_score:
            best_score = score
            best_page = i

    if best_score >= 10:
        return best_page
    return None


def extract_statement_page_number_from_contents(page: fitz.Page) -> Optional[int]:
    """
    Attempt to read the statement page number from the contents page.

    Looks for lines like:
      STATEMENT OF COMPREHENSIVE INCOME ........ 10
      Profit and loss account 12

    Returns the printed page number as an integer, not a 0-based index.
    """
    text_lines = [line.strip() for line in page.get_text("text").splitlines() if line.strip()]

    for line in text_lines:
        line_norm = normalize_text(line)

        if any(title in line_norm for title in STATEMENT_TITLES):
            m = re.search(r"(\d{1,3})\s*$", line)
            if m:
                return int(m.group(1))

    return None


## =========================================================
## 5. Direct title search fallback
##
## If contents-page parsing fails, search pages directly for a
## statement title near the top of the page.
## =========================================================

def page_title_score(page: fitz.Page) -> int:
    """
    Score a page for whether it appears to have a statement title.
    """
    text = page.get_text("text")
    if not text:
        return 0

    first_chunk = normalize_text("\n".join(text.splitlines()[:12]))
    score = 0

    for title in STATEMENT_TITLES:
        if title in first_chunk:
            score += 10

    return score


def find_statement_pages_by_title(doc: fitz.Document) -> List[int]:
    """
    Return 0-based page numbers with likely statement titles.
    """
    candidates = []
    for i in range(doc.page_count):
        page = doc.load_page(i)
        if page_title_score(page) >= 10:
            candidates.append(i)
    return candidates


## =========================================================
## 6. Weak fallback locator
##
## This is only used if:
##   - contents lookup fails
##   - direct title search fails
##
## It uses:
##   - some line-item terms
##   - evidence of year columns
##   - evidence of a Notes column
## =========================================================

def weak_statement_page_score(page: fitz.Page) -> int:
    text = normalize_text(page.get_text("text"))
    if not text:
        return 0

    score = 0

    if "notes" in text:
        score += 2

    year_count = len(re.findall(r"\b(19|20)\d{2}\b", text))
    if year_count >= 2:
        score += 3

    for kw in LINE_ITEM_KEYWORDS:
        if kw in text:
            score += 1

    return score


def find_statement_pages_by_weak_signals(doc: fitz.Document, min_score: int = 5) -> List[int]:
    candidates = []
    for i in range(doc.page_count):
        page = doc.load_page(i)
        score = weak_statement_page_score(page)
        if score >= min_score:
            candidates.append(i)
    return candidates


## =========================================================
## 7. Convert printed page number to PDF page index
##
## Why needed?
## -----------
## The contents page often lists internal page numbers such as 10,
## but the PDF may have cover pages before that. So printed page 10
## may not equal PDF index 9.
##
## Strategy:
## ---------
## We search nearby pages for a title match and choose the best fit.
## =========================================================

def page_matches_statement_title(page: fitz.Page) -> bool:
    text = normalize_text(page.get_text("text"))
    if not text:
        return False

    first_chunk = normalize_text("\n".join(page.get_text("text").splitlines()[:15]))
    return any(title in first_chunk for title in STATEMENT_TITLES)


def resolve_printed_page_to_pdf_index(
    doc: fitz.Document,
    printed_page_num: int,
    search_window: int = 4,
) -> Optional[int]:
    """
    Try to align a printed page number from the contents page to an
    actual PDF page index.

    We first try the obvious mapping:
      printed page 10 -> PDF index 9

    Then search nearby pages for a page with a statement title.
    """
    guess = printed_page_num - 1

    candidates = []
    for idx in range(max(0, guess - search_window), min(doc.page_count, guess + search_window + 1)):
        page = doc.load_page(idx)
        score = page_title_score(page) + weak_statement_page_score(page)
        candidates.append((score, idx))

    candidates.sort(reverse=True)
    if candidates and candidates[0][0] > 0:
        return candidates[0][1]

    if 0 <= guess < doc.page_count:
        return guess

    return None


## =========================================================
## 8. Verify that a page really looks like the statement
##
## We want to avoid jumping to a narrative page that happens to
## mention the statement title or some financial terms.
## =========================================================

def verify_statement_page(page: fitz.Page) -> bool:
    """
    Verify the page has features typical of the actual statement:
      - title near the top or strong statement structure
      - Notes column and/or multiple years
      - multiple line items with accounting numbers
    """
    text = page.get_text("text")
    if not text:
        return False

    rows = group_words_into_rows(page)
    full_text_norm = normalize_text(text)
    top_text_norm = normalize_text("\n".join(text.splitlines()[:15]))

    title_hit = any(title in top_text_norm for title in STATEMENT_TITLES)
    notes_hit = "notes" in full_text_norm
    year_hits = len(re.findall(r"\b(19|20)\d{2}\b", full_text_norm))

    line_item_hits = 0
    for kw in LINE_ITEM_KEYWORDS:
        if kw in full_text_norm:
            line_item_hits += 1

    row_with_numbers = 0
    for row in rows:
        numeric_tokens = [w for w in row["words"] if is_number_like_token(w["text"])]
        if numeric_tokens:
            row_with_numbers += 1

    if title_hit and (notes_hit or year_hits >= 2) and row_with_numbers >= 5:
        return True

    if line_item_hits >= 4 and year_hits >= 2 and row_with_numbers >= 5:
        return True

    return False


## =========================================================
## 9. Detect statement columns
##
## Typical statement layout:
##   Label | Notes | 2017 | 2016
##
## This function estimates the x-position of those columns.
## =========================================================

def detect_columns_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    note_x = None
    current_year_x = None
    prior_year_x = None
    current_year = None
    prior_year = None
    header_y = None

    for row in rows:
        row_text_norm = normalize_text(row["text"])

        has_notes = "notes" in row_text_norm
        year_words = [w for w in row["words"] if YEAR_RE.match(w["text"])]

        if has_notes or len(year_words) >= 2:
            header_y = row["y0"]

            for w in row["words"]:
                if normalize_text(w["text"]) == "notes":
                    note_x = (w["x0"] + w["x1"]) / 2
                    break

            year_words_sorted = sorted(year_words, key=lambda w: w["x0"])
            if len(year_words_sorted) >= 2:
                current_year = year_words_sorted[0]["text"]
                prior_year = year_words_sorted[1]["text"]
                current_year_x = (year_words_sorted[0]["x0"] + year_words_sorted[0]["x1"]) / 2
                prior_year_x = (year_words_sorted[1]["x0"] + year_words_sorted[1]["x1"]) / 2

            break

    return {
        "note_x": note_x,
        "current_year_x": current_year_x,
        "prior_year_x": prior_year_x,
        "current_year": current_year,
        "prior_year": prior_year,
        "header_y": header_y,
    }


## =========================================================
## 10. Extract structured rows from the statement page
##
## Output for each row:
##   - raw label
##   - standardized label
##   - note number
##   - current-year raw and numeric values
##   - prior-year raw and numeric values
## =========================================================

def extract_statement_rows_from_page(page: fitz.Page) -> Dict[str, Any]:
    rows = group_words_into_rows(page)
    colinfo = detect_columns_from_rows(rows)

    header_y = colinfo["header_y"]
    note_x = colinfo["note_x"]
    current_year_x = colinfo["current_year_x"]
    prior_year_x = colinfo["prior_year_x"]

    use_fallback_numeric_assignment = current_year_x is None or prior_year_x is None

    parsed_rows = []

    for row in rows:
        if header_y is not None and row["y0"] <= header_y:
            continue

        words = row["words"]
        texts = [w["text"] for w in words]
        row_text = " ".join(texts).strip()
        row_text_norm = normalize_text(row_text)

        if not row_text_norm:
            continue

        if row_text_norm in {"€", "notes"}:
            continue

        numeric_words = [w for w in words if is_number_like_token(w["text"])]
        if not numeric_words and not any(kw in row_text_norm for kw in LINE_ITEM_KEYWORDS):
            continue

        note_value = None
        current_value = None
        prior_value = None
        label_tokens = []

        if not use_fallback_numeric_assignment:
            label_right_bound = note_x - 10 if note_x is not None else current_year_x - 20
            year_split = (current_year_x + prior_year_x) / 2

            for w in words:
                xmid = (w["x0"] + w["x1"]) / 2
                token = w["text"]

                if xmid < label_right_bound:
                    label_tokens.append(token)
                    continue

                if note_x is not None and abs(xmid - note_x) < 30 and NOTE_RE.match(token):
                    note_value = token
                    continue

                if is_number_like_token(token):
                    if xmid < year_split:
                        if current_value is None:
                            current_value = token
                    else:
                        if prior_value is None:
                            prior_value = token

            label_raw = clean_label(" ".join(label_tokens))

        else:
            idx_numeric = [i for i, t in enumerate(texts) if is_number_like_token(t)]
            if not idx_numeric:
                continue

            label_end_idx = idx_numeric[0]
            label_raw = clean_label(" ".join(texts[:label_end_idx]))

            value_tokens = [texts[i] for i in idx_numeric]
            if len(value_tokens) >= 2:
                current_value = value_tokens[0]
                prior_value = value_tokens[1]
            elif len(value_tokens) == 1:
                current_value = value_tokens[0]

        if not label_raw:
            continue

        if normalize_text(label_raw) in {"notes"}:
            continue

        parsed_rows.append({
            "page": page.number + 1,
            "label_raw": label_raw,
            "label_standard": map_label_to_standard(label_raw),
            "note": note_value,
            "current_year_raw": current_value,
            "prior_year_raw": prior_value,
            "current_year_numeric": parse_accounting_number(current_value),
            "prior_year_numeric": parse_accounting_number(prior_value),
            "line_raw": row_text,
        })

    return {
        "page": page.number + 1,
        "current_year": colinfo["current_year"],
        "prior_year": colinfo["prior_year"],
        "rows": parsed_rows,
    }


## =========================================================
## 11. Post-processing
## =========================================================

def deduplicate_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []

    for row in rows:
        key = (
            normalize_text(row["label_raw"]),
            row["current_year_raw"],
            row["prior_year_raw"],
            row["page"],
        )
        if key not in seen:
            seen.add(key)
            out.append(row)

    return out


def build_key_items(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Keep the first row that maps to each standardized item.
    """
    key_items: Dict[str, Any] = {
        "revenue": None,
        "cost_of_sales": None,
        "gross_profit": None,
        "operating_profit": None,
        "profit_before_tax": None,
        "taxation": None,
        "profit_after_tax": None,
    }

    for row in rows:
        std = row["label_standard"]
        if std is not None and key_items[std] is None:
            key_items[std] = {
                "label_raw": row["label_raw"],
                "note": row["note"],
                "page": row["page"],
                "current_year_raw": row["current_year_raw"],
                "prior_year_raw": row["prior_year_raw"],
                "current_year_numeric": row["current_year_numeric"],
                "prior_year_numeric": row["prior_year_numeric"],
            }

    return key_items


## =========================================================
## 12. Statement page locator
##
## This is the key logic change you wanted.
##
## Order of operations:
##   A. Contents-page lookup
##   B. Direct title search
##   C. Weak fallback signals
## =========================================================

def locate_income_statement_pages(doc: fitz.Document) -> Dict[str, Any]:
    """
    Locate likely statement pages using a hierarchy:
      1. contents-page lookup
      2. direct title search
      3. weak fallback signals
    """
    result = {
        "method": None,
        "contents_page_pdf_index": None,
        "contents_printed_page_number": None,
        "candidate_pages_pdf_index": [],
    }

    ## Step A: contents-page lookup
    contents_idx = find_contents_page(doc)
    if contents_idx is not None:
        result["contents_page_pdf_index"] = contents_idx
        contents_page = doc.load_page(contents_idx)
        printed_page_num = extract_statement_page_number_from_contents(contents_page)
        result["contents_printed_page_number"] = printed_page_num

        if printed_page_num is not None:
            resolved_idx = resolve_printed_page_to_pdf_index(doc, printed_page_num)
            if resolved_idx is not None:
                page = doc.load_page(resolved_idx)
                if verify_statement_page(page):
                    result["method"] = "contents_page"
                    result["candidate_pages_pdf_index"] = [resolved_idx]
                    return result

    ## Step B: direct title search
    title_candidates = find_statement_pages_by_title(doc)
    verified_title_candidates = []
    for idx in title_candidates:
        page = doc.load_page(idx)
        if verify_statement_page(page):
            verified_title_candidates.append(idx)

    if verified_title_candidates:
        result["method"] = "title_search"
        result["candidate_pages_pdf_index"] = verified_title_candidates
        return result

    ## Step C: weak fallback
    weak_candidates = find_statement_pages_by_weak_signals(doc)
    verified_weak_candidates = []
    for idx in weak_candidates:
        page = doc.load_page(idx)
        if verify_statement_page(page):
            verified_weak_candidates.append(idx)

    if verified_weak_candidates:
        result["method"] = "weak_fallback"
        result["candidate_pages_pdf_index"] = verified_weak_candidates
        return result

    result["method"] = "not_found"
    return result


## =========================================================
## 13. Main extractor for one PDF
## =========================================================

def extract_income_statement_from_pdf(pdf_path: str | Path) -> Dict[str, Any]:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pdf_bytes = pdf_path.read_bytes()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    try:
        has_text = pdf_has_extractable_text(doc)

        ## If there is no text layer, extraction will likely fail until OCR is run.
        if not has_text:
            return {
                "source": str(pdf_path.resolve()),
                "status": "needs_ocr",
                "message": (
                    "This PDF appears to have little or no extractable text. "
                    "Run OCR first, then rerun this script."
                ),
                "locator": None,
                "current_year": None,
                "prior_year": None,
                "table_rows": [],
                "key_items": {
                    "revenue": None,
                    "cost_of_sales": None,
                    "gross_profit": None,
                    "operating_profit": None,
                    "profit_before_tax": None,
                    "taxation": None,
                    "profit_after_tax": None,
                },
            }

        locator = locate_income_statement_pages(doc)
        candidate_pages = locator["candidate_pages_pdf_index"]

        all_rows = []
        detected_year_pairs = []

        for idx in candidate_pages:
            page = doc.load_page(idx)
            page_result = extract_statement_rows_from_page(page)
            all_rows.extend(page_result["rows"])

            if page_result["current_year"] or page_result["prior_year"]:
                detected_year_pairs.append(
                    (page_result["current_year"], page_result["prior_year"])
                )

        all_rows = deduplicate_rows(all_rows)
        key_items = build_key_items(all_rows)

        current_year = None
        prior_year = None
        if detected_year_pairs:
            current_year = detected_year_pairs[0][0]
            prior_year = detected_year_pairs[0][1]

        status = "ok" if candidate_pages else "statement_not_found"

        return {
            "source": str(pdf_path.resolve()),
            "status": status,
            "locator": {
                "method": locator["method"],
                "contents_page_pdf_index": (
                    locator["contents_page_pdf_index"] + 1
                    if locator["contents_page_pdf_index"] is not None else None
                ),
                "contents_printed_page_number": locator["contents_printed_page_number"],
                "candidate_pages_pdf": [i + 1 for i in candidate_pages],
            },
            "current_year": current_year,
            "prior_year": prior_year,
            "table_rows": all_rows,
            "key_items": key_items,
        }

    finally:
        doc.close()


## =========================================================
## 14. Output helpers
## =========================================================

def flatten_for_csv(result: Dict[str, Any]) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "source": result["source"],
        "status": result.get("status"),
        "locator_method": result.get("locator", {}).get("method") if result.get("locator") else None,
        "contents_page_pdf": result.get("locator", {}).get("contents_page_pdf_index") if result.get("locator") else None,
        "contents_printed_page_number": result.get("locator", {}).get("contents_printed_page_number") if result.get("locator") else None,
        "candidate_pages_pdf": ",".join(str(x) for x in result.get("locator", {}).get("candidate_pages_pdf", []))
        if result.get("locator") else None,
        "current_year": result.get("current_year"),
        "prior_year": result.get("prior_year"),
    }

    for key in [
        "revenue",
        "cost_of_sales",
        "gross_profit",
        "operating_profit",
        "profit_before_tax",
        "taxation",
        "profit_after_tax",
    ]:
        item = result["key_items"].get(key)

        row[f"{key}_label_raw"] = item.get("label_raw") if item else None
        row[f"{key}_note"] = item.get("note") if item else None
        row[f"{key}_page"] = item.get("page") if item else None
        row[f"{key}_current_raw"] = item.get("current_year_raw") if item else None
        row[f"{key}_prior_raw"] = item.get("prior_year_raw") if item else None
        row[f"{key}_current_numeric"] = item.get("current_year_numeric") if item else None
        row[f"{key}_prior_numeric"] = item.get("prior_year_numeric") if item else None

    return row


def write_json(data: Dict[str, Any], out_path: Path) -> None:
    out_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_csv(rows: List[Dict[str, Any]], out_path: Path) -> None:
    if not rows:
        return

    fieldnames = []
    seen = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)

    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


## =========================================================
## 15. Batch processor
## =========================================================

def process_pdfs(input_path: str | Path, output_dir: str | Path, recursive: bool = False) -> None:
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = get_pdf_paths(input_path, recursive=recursive)
    if not pdfs:
        print("No PDFs found.")
        return

    csv_rows = []

    for pdf in pdfs:
        try:
            result = extract_income_statement_from_pdf(pdf)

            json_path = output_dir / f"{pdf.stem}_income_statement.json"
            write_json(result, json_path)

            csv_rows.append(flatten_for_csv(result))
            print(f"Processed: {pdf.name} | status={result.get('status')}")

        except Exception as e:
            print(f"Error processing {pdf}: {e}")

    combined_csv = output_dir / "income_statement_key_items.csv"
    write_csv(csv_rows, combined_csv)
    print(f"Wrote combined CSV: {combined_csv}")


## =========================================================
## 16. Command-line entry point
## =========================================================

def main():
    parser = argparse.ArgumentParser(
        description="Extract income statement key items from PDF files using contents-page-first logic."
    )
    parser.add_argument("input_path", help="Path to a PDF file or folder of PDFs")
    parser.add_argument(
        "-o",
        "--output_dir",
        default="output_income_statement",
        help="Folder for JSON and CSV output",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively search subfolders for PDFs",
    )

    args = parser.parse_args()

    process_pdfs(
        input_path=args.input_path,
        output_dir=args.output_dir,
        recursive=args.recursive,
    )


if __name__ == "__main__":
    main()

