#!/usr/bin/env python3
"""
PDF Attribute Extractor - Extracts all attributes from a PDF document.
Includes: metadata, text, images, links, annotations, form fields, outline, and more.
"""

import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Union

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


def get_pdf_paths(path: Union[str, Path], recursive: bool = False) -> List[Path]:
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


def extract_all_attributes(pdf_path: Union[str, Path], include_image_bytes: bool = False) -> dict:
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


def get_json_paths(path: Union[str, Path], recursive: bool = False) -> List[Path]:
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



