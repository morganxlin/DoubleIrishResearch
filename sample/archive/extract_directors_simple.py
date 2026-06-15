#!/usr/bin/env python3
"""
Extract Current Directors and Company Information from PDFs
Simplified version that uses PyMuPDF directly
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional

try:
    import fitz
except ImportError:
    print("Error: pymupdf not installed. Run: pip install pymupdf")
    sys.exit(1)


def extract_current_directors(text: str) -> Optional[str]:
    """
    Extract 'Current Directors' from text - optimized for speed.
    Returns the first value found, or None.
    """
    if not text:
        return None
    
    # Stop words that indicate administrative roles, not actual names
    STOP_WORDS = {'secretary', 'auditor', 'banker', 'solicitor', 'accountant',
                  'registered', 'office', 'date:', 'page', 'company', 'information',
                  'notes', 'contents', 'report', 'mr', 'ms', 'mrs', 'dr', 'prof'}
    
    # Limit search to first part of document (directors usually near top)
    search_text = text[:10000] if len(text) > 10000 else text
    
    # Quick Pattern 1: "Name - Director" (fastest)
    for m in re.finditer(r"^\s*([A-Za-z][A-Za-z\s\-'.]{2,60})\s*-\s*Director\b", search_text, re.IGNORECASE | re.MULTILINE):
        name = m.group(1).strip()
        if name and len(name) > 2 and not any(stop in name.lower() for stop in STOP_WORDS):
            return name
    
    # Pattern 2: "Directors:" section followed by names
    m = re.search(r"Directors?\s*:?\s*\n((?:[A-Za-z][A-Za-z\s\-'.]{2,60}\n?)+?)(?:\n\s*(?:Secretary|Auditor|Registered|CONTENTS)|\Z)", search_text, re.IGNORECASE | re.MULTILINE)
    if m:
        block = m.group(1)
        lines = []
        for raw in block.splitlines():
            s = raw.strip()
            if s and 3 <= len(s) < 80 and not any(stop in s.lower() for stop in STOP_WORDS):
                if re.match(r"^[A-Za-z]", s):  # Starts with letter
                    lines.append(s)
        if lines:
            return lines[0]  # Return first director found
    
    return None


def extract_company_name(text: str) -> Optional[str]:
    """
    Extract company name from text.
    """
    if not text:
        return None
    
    bad = re.compile(
        r"^(overall\s+certificate|annual\s+report|reports?\s+and\s+financial\s+statements?|contents|page\s*\(?s?\)?|statement|independent|docusign)\b",
        re.IGNORECASE,
    )
    
    for raw in text.splitlines():
        s = raw.strip()
        if not s or len(s) < 3 or len(s) > 80:
            continue
        if bad.search(s):
            continue
        # Company names often contain legal suffixes
        if re.search(r"\b(Limited|Ltd\.?|plc|DAC|Company|Corporation|Group)\b", s, re.IGNORECASE):
            return s
    
    return None


def extract_year_ended(text: str) -> Optional[str]:
    """
    Extract a "year ended" date from text.
    """
    if not text:
        return None
    
    patterns = [
        r"(?:for\s+the\s+)?(?:financial\s+)?year\s+ended\s+([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
        r"(?:for\s+the\s+year\s+ended|year\s+ended)\s+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
    ]
    
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    
    return None


def extract_directors_from_pdf(pdf_path):
    """Extract directors, company name, and year from a single PDF"""
    try:
        pdf_path = Path(pdf_path)
        
        # Open PDF and extract text
        doc = fitz.open(str(pdf_path))
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        
        # Extract information
        company_name = extract_company_name(text)
        year_ended = extract_year_ended(text)
        current_directors = extract_current_directors(text)
        
        return {
            "file": pdf_path.name,
            "status": "success",
            "company_name": company_name,
            "year_ended": year_ended,
            "current_directors": current_directors,
        }
    except Exception as e:
        return {
            "file": str(pdf_path),
            "status": "error",
            "error": str(e),
        }


def main():
    workspace_dir = Path("/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample")
    output_dir = workspace_dir / "directors_output"
    output_dir.mkdir(exist_ok=True)
    
    # Get all PDFs
    pdf_files = sorted(workspace_dir.glob("*account*.pdf"))
    
    print(f"{'='*80}")
    print("EXTRACTING DIRECTORS AND COMPANY INFORMATION")
    print(f"{'='*80}")
    print(f"Found {len(pdf_files)} PDF files\n")
    
    results = []
    successful = 0
    
    for pdf_path in pdf_files:
        result = extract_directors_from_pdf(pdf_path)
        results.append(result)
        
        if result["status"] == "success":
            successful += 1
            print(f"✓ {pdf_path.name}")
            print(f"  Company: {result['company_name'] or '(not found)'}")
            print(f"  Year: {result['year_ended'] or '(not found)'}")
            if result['current_directors']:
                directors_preview = result['current_directors'][:60] + "..." if len(result['current_directors']) > 60 else result['current_directors']
                print(f"  Directors: {directors_preview}")
            else:
                print(f"  Directors: (not found)")
            print()
        else:
            print(f"✗ {result['file']}")
            print(f"  Error: {result.get('error', 'Unknown error')}\n")
    
    # Save results to JSON
    json_output = output_dir / "directors_extracted.json"
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Save individual text files for each PDF
    for result in results:
        if result["status"] == "success":
            txt_filename = result["file"].replace(".pdf", "_directors.txt")
            txt_path = output_dir / txt_filename
            
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(f"Company: {result.get('company_name') or '(not found)'}\n")
                f.write(f"Year Ended: {result.get('year_ended') or '(not found)'}\n")
                f.write(f"Current Directors:\n")
                if result.get('current_directors'):
                    f.write(result['current_directors'] + "\n")
                else:
                    f.write("(not found)\n")
    
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"✓ Successfully extracted: {successful} files")
    print(f"✗ Failed: {len(pdf_files) - successful} files")
    print(f"\nOutput saved to: {output_dir}")
    print(f"JSON results: {json_output}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
