import json
from pathlib import Path

workspace = Path('.')
json_files = sorted(workspace.glob('*.json'))

print(f"Found {len(json_files)} JSON files\n")

for json_file in json_files[:3]:
    print(f"\n=== {json_file.name} ===")
    try:
        with open(json_file) as f:
            data = json.load(f)
        
        # Collect all text
        all_text = ''
        for page in data.get('pages', []):
            for block in page.get('blocks', []):
                for line in block.get('lines', []):
                    for span in line.get('spans', []):
                        all_text += span.get('text', '') + ' '
        
        # Print first 500 chars to see structure
        print("First 500 chars of text:")
        print(all_text[:500])
        print(f"\nTotal text length: {len(all_text)}")
        
        # Check for financial keywords
        keywords = ['turnover', 'revenue', 'operating', 'profit', 'loss', 'year']
        found = [k for k in keywords if k in all_text.lower()]
        print(f"Keywords found: {found}")
        
    except Exception as e:
        print(f"Error: {e}")
