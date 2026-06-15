#!/usr/bin/env python3
"""Extract Principal Activity section from each document with more flexible matching."""

import re
from pathlib import Path
from typing import Tuple, Optional

# Configuration
WORKSPACE_DIR = Path(
    "/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-Villanova"
    "University/Brian Grant - Grant and Lin/sample"
)
OUTPUT_DIR = WORKSPACE_DIR / "principal_activity_outputs"


def extract_principal_activity(file_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Extract the Principal Activity section from a text file.
    Handles OCR errors and various formats.

    Returns:
        Tuple of (found, text)
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Try multiple patterns to catch different variations
        patterns = [
            r"principal\s+[a-z0-9]+[a-z0-9]*tiv[a-z0-9]*",  # principal activity/activit/etc
            r"principal\s+act[iIl1]{1,2}v[i1]t[i1][ey]?",  # OCR: ac1iviry, actvity
            r"(?:principal\s+)?operations?\s+(?:of\s+)?the\s+company",  # operations
            r"principal\s+business",  # variation
        ]

        match = None
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                break

        if not match:
            return False, None

        # Get position after the match
        start_pos = match.end()

        # Skip the rest of the line (could have comma or other text)
        remaining = content[start_pos:]

        # Find the next line that starts with a capital letter (new section)
        lines = remaining.split("\n")

        extracted_lines = []
        for i, line in enumerate(lines):
            # Skip empty lines at the start
            if i == 0 and not line.strip():
                continue

            # Check if this looks like a new section heading
            line_stripped = line.strip()

            if line_stripped and i > 0:
                # If line starts with capital letter and contains common section words
                if re.match(r"[A-Z][a-z]", line_stripped):
                    # Check if it's likely a section header
                    if any(
                        keyword in line_stripped
                        for keyword in [
                            "Business",
                            "Performance",
                            "Risks",
                            "Directors",
                            "Financial",
                            "Going",
                            "Dividend",
                            "Results",
                            "Strategy",
                            "Subsequent",
                            "Report",
                        ]
                    ):
                        break

            if line_stripped or extracted_lines:  # Skip leading empty lines
                extracted_lines.append(line.rstrip())

            # Stop if we have many lines (avoid extracting too much)
            if len(extracted_lines) > 25:
                break

        text = "\n".join(extracted_lines).strip()

        if len(text) > 30:
            return True, text
        else:
            return False, None
    except (IOError, OSError) as e:
        return False, str(e)

def main() -> None:
    """Main function to extract and save principal activity."""
    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("=" * 100)
    print("PRINCIPAL ACTIVITY EXTRACTION")
    print("=" * 100)
    print(f"Output directory: {OUTPUT_DIR}\n")

    # Get all text files
    txt_files = sorted(WORKSPACE_DIR.glob("*_pl.txt")) + sorted(
        WORKSPACE_DIR.glob("*account.txt")
    )

    all_files = sorted(set(txt_files))

    found_count = 0
    not_found = []

    for file_path in all_files:
        # Skip checkpoint files
        if ".ipynb_checkpoints" in str(file_path):
            continue

        file_name = file_path.name
        found, text = extract_principal_activity(file_path)

        if found:
            found_count += 1

            # Create output filename
            output_filename = (
                file_name.replace(" ", "_").replace(".txt", "_principal_activity.txt")
            )
            output_path = OUTPUT_DIR / output_filename

            # Write to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"PRINCIPAL ACTIVITY SECTION\n")
                f.write(f"{'='*100}\n")
                f.write(f"Source: {file_name}\n")
                f.write(f"{'='*100}\n\n")
                f.write(text)

            print(f"✅ {file_name}")
            print(f"   → Saved to: {output_filename}\n")
        else:
            not_found.append(file_name)

    print(f"\n{'='*100}")
    print(f"SUMMARY")
    print(f"{'='*100}")
    print(f"✅ Found and saved Principal Activity from: {found_count} files")
    print(f"❌ Not found in: {len(not_found)} files")

    if not_found:
        print(f"\nFiles without Principal Activity section:")
        for fname in sorted(not_found):
            print(f"  • {fname}")

if __name__ == "__main__":
    main()
