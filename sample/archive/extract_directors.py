#!/usr/bin/env python3
"""
Extract Current Directors and Company Information from PDF files
Uses functions from pdf_extractor_withnotes.py
"""

import json
import sys
from pathlib import Path

try:
    import fitz
except ImportError:
    print("Error: pymupdf not installed. Run: pip install pymupdf")
    sys.exit(1)

# Import the extraction functions from pdf_extractor_withnotes
sys.path.insert(0, "/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample")

from pdf_extractor_withnotes import (
    extract_all_attributes,
    extract_current_directors,
    extract_company_name,
    extract_year_ended,
)

def extract_directors_from_pdf(pdf_path):
    """Extract directors, company name, and year from a single PDF"""
    try:
        pdf_path = Path(pdf_path)
        
        # Extract all attributes
        data = extract_all_attributes(pdf_path, include_image_bytes=False)
        
        # Pull out what we need
        company_name = extract_company_name(data)
        year_ended = extract_year_ended(data)
        current_directors = extract_current_directors(data)
        
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
