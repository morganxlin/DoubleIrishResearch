#!/usr/bin/env python3
"""
Extract 'Principal activities and business review' section
and save one output file per input file.
"""

import re
from pathlib import Path

def normalize_text(text: str) -> str:
    """
    Clean OCR/text issues slightly.
    """
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    return text


def extract_principal_activity(file_path: Path) -> tuple[bool, str | None]:
    """
    Extract the full paragraph under:
    'Principal activities and business review'

    Stops at the next section header.
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        content = normalize_text(content)

        # Match the section header
        heading_pattern = r'principal activities and business review'
        heading_match = re.search(heading_pattern, content, re.IGNORECASE)

        if not heading_match:
            return False, None

        start = heading_match.end()

        # Common next section headers
        next_heading_pattern = (
            r'\n\s*'
            r'(branch|results and dividends|going concern|principal risks and uncertainties|'
            r'financial risk management|future developments|events after reporting date|directors)\b'
        )

        next_match = re.search(next_heading_pattern, content[start:], re.IGNORECASE)

        if next_match:
            end = start + next_match.start()
            extracted = content[start:end].strip()
        else:
            extracted = content[start:start + 2500].strip()

        # Clean paragraph formatting
        extracted = re.sub(r'\n(?=[a-z])', ' ', extracted)   # join wrapped lines
        extracted = re.sub(r'\n+', '\n', extracted)
        extracted = re.sub(r' +', ' ', extracted).strip()

        if len(extracted) > 30:
            return True, extracted
        else:
            return False, None

    except Exception as e:
        return False, str(e)


def main():
    workspace_dir = Path("/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample")

    print("=" * 100)
    print("PRINCIPAL ACTIVITY EXTRACTION (FILE OUTPUT MODE)")
    print("=" * 100)

    txt_files = sorted(workspace_dir.glob("*_pl.txt")) + sorted(workspace_dir.glob("*account.txt"))
    all_files = sorted(set(txt_files))

    found_count = 0
    not_found = []

    for file_path in all_files:
        if ".ipynb_checkpoints" in str(file_path):
            continue

        file_name = file_path.name
        found, text = extract_principal_activity(file_path)

        if found:
            found_count += 1

            # Create output file name
            output_path = file_path.with_name(file_path.stem + "_principal.txt")

            with open(output_path, "w", encoding="utf-8") as out:
                out.write("Principal activities and business review\n")
                out.write(text + "\n")

            print(f"✅ Saved: {output_path.name}")

        else:
            not_found.append(file_name)
            print(f"❌ Not found: {file_name}")

    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"✅ Found: {found_count}")
    print(f"❌ Not found: {len(not_found)}")

    if not_found:
        print("\nFiles without section:")
        for fname in sorted(not_found):
            print(f"  • {fname}")


if __name__ == "__main__":
    main()