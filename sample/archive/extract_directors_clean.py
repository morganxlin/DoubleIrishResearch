#!/usr/bin/env python3
"""
Extract and clean directors information with roles
Output format: Role: Person Name
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict

try:
    import fitz
except ImportError:
    print("Error: pymupdf not installed. Run: pip install pymupdf")
    exit(1)


def clean_ocr_artifacts(text: str) -> str:
    """Clean common OCR artifacts"""
    # Replace common OCR errors
    replacements = {
        r'[l1I|][l1I|]': 'll',  # ll errors
        r'rn': 'rn',  # Keep valid
        r'(?<![a-zA-Z])m(?![a-zA-Z])': 'm',
    }
    result = text
    # Fix spacing issues
    result = re.sub(r'\s+', ' ', result)
    result = re.sub(r'([a-z])([A-Z])', r'\1 \2', result)  # Add space between camelCase
    return result.strip()


def extract_directors_from_text(text: str) -> Dict[str, list]:
    """
    Extract directors and officers with their roles.
    Much stricter filtering - only actual names with titles.
    """
    if not text:
        return {}
    
    search_text = text[:20000] if len(text) > 20000 else text
    result = {}
    
    # STRATEGY 1: Look for "Name - Title" or "Name\nTitle" patterns
    # This is the most reliable pattern
    director_patterns = [
        # Mr/Ms/Dr FirstName LastName - Director
        r'((?:Mr|Ms|Mrs|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:\s+[A-Z][a-z]+)?)\s*(?:-|\n)\s*Director',
        # FirstName LastName - Director  
        r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(?:-|\n)\s*Director',
    ]
    
    secretary_patterns = [
        r'((?:Mr|Ms|Mrs|Dr)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:\s+[A-Z][a-z]+)?)\s*(?:-|\n)\s*(?:Company\s+)?Secretary',
        r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(?:-|\n)\s*(?:Company\s+)?Secretary',
    ]
    
    auditor_patterns = [
        r'((?:Mr|Ms|Mrs|Dr)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:\s+[A-Z][a-z]+)?)\s*(?:-|\n)\s*Auditor',
        r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(?:-|\n)\s*Auditor',
    ]
    
    # Extract Directors
    for pattern in director_patterns:
        for m in re.finditer(pattern, search_text, re.IGNORECASE):
            name = m.group(1).strip()
            name = clean_ocr_artifacts(name)
            if name not in result.get('Director', []):
                result.setdefault('Director', []).append(name)
    
    # Extract Secretaries
    for pattern in secretary_patterns:
        for m in re.finditer(pattern, search_text, re.IGNORECASE):
            name = m.group(1).strip()
            name = clean_ocr_artifacts(name)
            if name not in result.get('Secretary', []):
                result.setdefault('Secretary', []).append(name)
    
    # Extract Auditors
    for pattern in auditor_patterns:
        for m in re.finditer(pattern, search_text, re.IGNORECASE):
            name = m.group(1).strip()
            name = clean_ocr_artifacts(name)
            if name not in result.get('Auditor', []):
                result.setdefault('Auditor', []).append(name)
    
    # STRATEGY 2: If no matches found, look in "Directors" section more carefully
    if not result:
        directors_section = re.search(
            r'(?:^|\n)\s*Directors?\s*(?::|$)\s*\n((?:[^\n]*\n){1,10}?)(?=\n\s*(?:Secretary|Auditor|Registered|Company\s+Information)|\Z)',
            search_text,
            re.IGNORECASE | re.MULTILINE
        )
        
        if directors_section:
            section = directors_section.group(1)
            for line in section.split('\n'):
                line = line.strip()
                if not line or len(line) > 80:
                    continue
                
                # Skip labels
                if any(x in line.lower() for x in ['secretary', 'auditor', 'banker', 'solicitor', 'page', 'notes', 'contents']):
                    continue
                
                # Check if looks like a name
                if re.match(r'^(?:Mr|Ms|Mrs|Dr)?\s?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', line):
                    name = clean_ocr_artifacts(line)
                    if 5 <= len(name) <= 60:
                        result.setdefault('Director', []).append(name)
    
    return result


def format_directors_output(directors_dict: Dict[str, list]) -> str:
    """Format directors dictionary into clean text"""
    if not directors_dict:
        return "(No directors information found)"
    
    lines = []
    
    # Standard order of roles
    role_order = ['Director', 'Managing Director', 'Chairman', 'Chief Executive', 
                  'Secretary', 'Auditor']
    
    for role in role_order:
        if role in directors_dict and directors_dict[role]:
            for name in directors_dict[role]:
                lines.append(f"{role}: {name}")
    
    # Add any other roles
    for role in sorted(directors_dict.keys()):
        if role not in role_order and directors_dict[role]:
            for name in directors_dict[role]:
                lines.append(f"{role}: {name}")
    
    return "\n".join(lines) if lines else "(No directors information found)"


def extract_from_pdf(pdf_path: Path) -> Dict[str, list]:
    """Extract directors info from PDF"""
    try:
        doc = fitz.open(str(pdf_path))
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        
        return extract_directors_from_text(text)
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        return {}


def main():
    workspace_dir = Path("/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample")
    output_dir = workspace_dir / "directors_output_clean"
    output_dir.mkdir(exist_ok=True)
    
    # Get all PDFs
    pdf_files = sorted(workspace_dir.glob("*account*.pdf"))
    
    print(f"{'='*80}")
    print("EXTRACTING CLEAN DIRECTORS INFORMATION")
    print(f"{'='*80}\n")
    
    results = []
    
    for pdf_path in pdf_files:
        directors_dict = extract_from_pdf(pdf_path)
        formatted = format_directors_output(directors_dict)
        
        # Save to text file
        txt_filename = pdf_path.stem + "_directors_clean.txt"
        txt_path = output_dir / txt_filename
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"FILE: {pdf_path.name}\n")
            f.write(f"{'='*80}\n\n")
            f.write(formatted)
        
        # Save to JSON
        results.append({
            "file": pdf_path.name,
            "directors": directors_dict
        })
        
        print(f"✓ {pdf_path.name}")
        print(f"  {formatted[:100]}...\n" if len(formatted) > 100 else f"  {formatted}\n")
    
    # Save combined JSON
    json_output = output_dir / "directors_all_clean.json"
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"{'='*80}")
    print(f"✓ Output saved to: {output_dir}")
    print(f"  - Individual files: *_directors_clean.txt")
    print(f"  - Combined JSON: directors_all_clean.json")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
