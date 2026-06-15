#!/usr/bin/env python3
"""Clean directors extraction - focused on the structured format."""

import json
import re
from pathlib import Path
from typing import Dict, List

try:
    import fitz
except ImportError:
    print("Error: pymupdf not installed. Run: pip install pymupdf")
    exit(1)

# Configuration
WORKSPACE_DIR = Path(
    "/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-Villanova"
    "University/Brian Grant - Grant and Lin/sample"
)
OUTPUT_DIR = WORKSPACE_DIR / "directors_output_clean"


def extract_directors_structured(text: str) -> Dict[str, List[str]]:
    """
    Extract from the structured company information section format:

    Directors
    John Smith
    Jane Doe

    Company secretary
    [name or title]

    Independent auditors
    [name]
    """
    result = {}
    
    # Look for the structured section
    # Find lines with role headers, then capture the lines underneath
    
    # 1. Extract Directors section
    directors_match = re.search(
        r'(?:^|\n)\s*Directors\s*(?:$|\n)((?:(?!Company\s+secretary|Independent|Auditor|Bankers|Solicitors|Registered).*\n?)+)',
        text,
        re.IGNORECASE | re.MULTILINE
    )
    
    if directors_match:
        directors_block = directors_match.group(1)
        directors = []
        for line in directors_block.split('\n'):
            line = line.strip()
            # Skip empty lines, page numbers, dates in parentheses
            if not line or re.match(r'^\d+$', line) or re.match(r'^\(.*\)$', line):
                continue
            # Skip short words or labels
            if len(line) < 3 or len(line) > 100:
                continue
            # Skip common non-name patterns
            if any(x in line.lower() for x in ['page', 'contents', 'report', 'auditor', 'secretary', 'banker']):
                continue
            # This should be a name
            directors.append(line)
        
        if directors:
            result['Director'] = directors
    
    # 2. Extract Company Secretary section
    secretary_match = re.search(
        r'(?:^|\n)\s*(?:Company\s+)?Secretary\s*(?:$|\n)((?:(?!Registered|Independent|Auditor|Bankers|Solicitors|Directors).*\n?)+)',
        text,
        re.IGNORECASE | re.MULTILINE
    )
    
    if secretary_match:
        secretary_block = secretary_match.group(1)
        secretaries = []
        for line in secretary_block.split('\n'):
            line = line.strip()
            if not line or len(line) < 3 or len(line) > 100:
                continue
            if re.match(r'^\d+$', line) or re.match(r'^\(.*\)$', line):
                continue
            if any(x in line.lower() for x in ['page', 'contents', 'report', 'register', 'office']):
                continue
            secretaries.append(line)
        
        if secretaries:
            result['Secretary'] = secretaries
    
    # 3. Extract Auditors section
    auditor_match = re.search(
        r'(?:^|\n)\s*(?:Independent\s+)?Auditors?\s*(?:$|\n)((?:(?!Bankers|Solicitors|Registered|Directors).*\n?)+)',
        text,
        re.IGNORECASE | re.MULTILINE
    )
    
    if auditor_match:
        auditor_block = auditor_match.group(1)
        auditors = []
        for line in auditor_block.split('\n'):
            line = line.strip()
            if not line or len(line) < 3 or len(line) > 100:
                continue
            if re.match(r'^\d+$', line) or re.match(r'^\(.*\)$', line):
                continue
            if any(x in line.lower() for x in ['page', 'contents', 'report', 'chartered', 'firm']):
                continue
            auditors.append(line)
        
        if auditors:
            result['Auditor'] = auditors
    
    return result


def extract_from_pdf(pdf_path: Path) -> Dict[str, List[str]]:
    """Extract directors info from PDF."""
    try:
        doc = fitz.open(str(pdf_path))
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()

        return extract_directors_structured(text)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"Warning: Could not process {pdf_path}: {e}")
        return {}


def format_output(directors_dict: Dict[str, list]) -> str:
    """Format as: Role: Name"""
    if not directors_dict:
        return "(No directors information found)"
    
    lines = []
    role_order = ['Director', 'Secretary', 'Auditor']
    
    for role in role_order:
        if role in directors_dict:
            for name in directors_dict[role]:
                lines.append(f"{role}: {name}")
    
    return "\n".join(lines) if lines else "(No directors information found)"


def main() -> None:
    """Main function to extract and save directors information."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    pdf_files = sorted(WORKSPACE_DIR.glob("*account*.pdf"))

    print(f"{'='*80}")
    print("EXTRACTING CLEAN DIRECTORS INFORMATION (STRUCTURED FORMAT)")
    print(f"{'='*80}\n")

    results = []

    for pdf_path in pdf_files:
        directors_dict = extract_from_pdf(pdf_path)
        formatted = format_output(directors_dict)

        # Save to text file
        txt_filename = pdf_path.stem + "_directors_clean.txt"
        txt_path = OUTPUT_DIR / txt_filename

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"FILE: {pdf_path.name}\n")
            f.write(f"{'='*80}\n\n")
            f.write(formatted)

        results.append({"file": pdf_path.name, "directors": directors_dict})

        print(f"✓ {pdf_path.name}")
        print(f"  {formatted}\n")

    # Save combined JSON
    json_output = OUTPUT_DIR / "directors_all_clean.json"
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"{'='*80}")
    print(f"✓ Clean directors extracted to: {OUTPUT_DIR}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
