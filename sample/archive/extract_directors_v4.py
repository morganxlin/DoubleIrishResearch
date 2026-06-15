#!/usr/bin/env python3
"""
Extract directors information with clean, structured output.
Targets the company information section at the beginning of financial statements.
"""

import re
import os
from pathlib import Path

workspace_dir = Path(__file__).parent
text_dir = workspace_dir
output_dir = workspace_dir / "directors_output_clean"
output_dir.mkdir(exist_ok=True)


def extract_directors_clean(text):
    """
    Extract directors from the company information section.
    Returns list of (role, name) tuples.
    """
    directors = []
    
    # Search only the first 2000 characters (company info section is at start)
    search_text = text[:3000]
    
    # Pattern: Role header on its own line, followed by names/entities
    # Stop at next major section (Financial, Independent Auditors, Registered, etc.)
    
    # Directors section
    directors_match = re.search(
        r'(?:^|\n)\s*Directors\s*(?:\n|$)((?:(?!\n\s*(?:Company|Independent|Secretary|Auditor|Registered|Business|Principal)).)+)',
        search_text,
        re.IGNORECASE | re.MULTILINE | re.DOTALL
    )
    
    if directors_match:
        director_block = directors_match.group(1).strip()
        # Split into lines and filter out empty/short lines
        for line in director_block.split('\n'):
            line = line.strip()
            if line and len(line) > 2 and not line.startswith(('(', '€', '€', '-', '–')):
                # Clean up OCR artifacts
                line = re.sub(r'[^\w\s\-\(\)\.]', '', line)
                line = line.strip()
                if line and len(line) > 2 and line[0].isupper():
                    directors.append(('Director', line))
    
    # Company Secretary section
    secretary_match = re.search(
        r'(?:^|\n)\s*(?:Company\s+)?[Ss]ecretary\s*(?:\n|$)((?:(?!\n\s*(?:Registered|Independent|Auditor|Business)).)+)',
        search_text,
        re.IGNORECASE | re.MULTILINE | re.DOTALL
    )
    
    if secretary_match:
        secretary_block = secretary_match.group(1).strip()
        for line in secretary_block.split('\n'):
            line = line.strip()
            if line and len(line) > 2 and not line.startswith(('(', '€', '-', '–')):
                line = re.sub(r'[^\w\s\-\(\)\.]', '', line)
                line = line.strip()
                if line and len(line) > 2:
                    directors.append(('Secretary', line))
                    break  # Usually just one secretary
    
    # Independent Auditors/Auditor section
    auditor_match = re.search(
        r'(?:^|\n)\s*(?:Independent\s+)?Auditor[s]?\s*(?:\n|$)((?:(?!\n\s*(?:Registered|Directors|Company|Business)).)+)',
        search_text,
        re.IGNORECASE | re.MULTILINE | re.DOTALL
    )
    
    if auditor_match:
        auditor_block = auditor_match.group(1).strip()
        for line in auditor_block.split('\n'):
            line = line.strip()
            if line and len(line) > 2 and not line.startswith(('(', '€', '-', '–', 'Note', 'The')):
                line = re.sub(r'[^\w\s\-\(\)\.]', '', line)
                line = line.strip()
                if line and len(line) > 2:
                    directors.append(('Auditor', line))
                    break  # Usually just one line for auditor firm
    
    return directors


def main():
    """Process all cleaned text files."""
    text_files = sorted(text_dir.glob("*_pl.txt"))
    
    print(f"\nProcessing {len(text_files)} text files...\n")
    
    for text_file in text_files:
        output_file = output_dir / text_file.name.replace("_pl.txt", "_directors.txt")
        
        try:
            with open(text_file, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            
            directors = extract_directors_clean(text)
            
            if directors:
                with open(output_file, 'w', encoding='utf-8') as f:
                    for role, name in directors:
                        f.write(f"{role}: {name}\n")
                print(f"✓ {text_file.name}")
                for role, name in directors[:5]:  # Show first 5
                    print(f"  {role}: {name}")
                if len(directors) > 5:
                    print(f"  ... and {len(directors) - 5} more")
            else:
                print(f"✗ {text_file.name} (No directors found)")
        
        except Exception as e:
            print(f"✗ {text_file.name} - Error: {str(e)}")
    
    print(f"\n✓ Results saved to: {output_dir}")


if __name__ == "__main__":
    main()
