#!/usr/bin/env python3
"""
Simple PDF to text extractor using PyMuPDF
"""

import sys
from pathlib import Path

try:
    import fitz
except ImportError:
    print("Error: pymupdf not installed. Run: pip install pymupdf")
    sys.exit(1)

def extract_pdf_to_text(pdf_path, output_path):
    """Extract all text from PDF and save to text file"""
    try:
        doc = fitz.open(str(pdf_path))
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        
        # Save to text file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        return True, len(text)
    except Exception as e:
        return False, str(e)

def main():
    workspace_dir = Path("/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample")
    
    # Find all PDFs
    pdf_files = sorted(workspace_dir.glob("*account*.pdf"))
    
    print(f"Found {len(pdf_files)} PDF files to process\n")
    
    successful = 0
    failed = 0
    
    for pdf_path in pdf_files:
        # Create output filename: remove .pdf and add _pl.txt
        output_name = pdf_path.stem + "_pl.txt"
        output_path = workspace_dir / output_name
        
        # Skip if already exists
        if output_path.exists():
            print(f"⊘ {pdf_path.name} → Already extracted")
            continue
        
        success, result = extract_pdf_to_text(pdf_path, output_path)
        
        if success:
            print(f"✓ {pdf_path.name}")
            print(f"  → {output_name} ({result} chars)")
            successful += 1
        else:
            print(f"✗ {pdf_path.name}")
            print(f"  Error: {result}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Summary: {successful} successful, {failed} failed")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
