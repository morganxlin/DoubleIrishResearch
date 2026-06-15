import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

# Configuration
WORKSPACE_PATH = Path(
    "/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-Villanova"
    "University/Brian Grant - Grant and Lin/sample"
)


def find_pl_table(lines: List[str]) -> Dict[str, Optional[float]]:
    """Find and extract the complete P&L table from lines"""
    results = {}
    
    # Search through all lines for financial metrics
    for line in lines:
        line_lower = line.lower()
        line_clean = line.strip()
        
        if not line_clean:
            continue
        
        # Extract numbers - get all of them
        all_numbers = re.findall(r'([\d,\.]+)(?:\s|$)', line)
        numbers = []
        for n in all_numbers:
            try:
                v = float(n.replace(',', ''))
                if v >= 0.1:  # Filter out tiny numbers
                    numbers.append(v)
            except ValueError:
                pass
        
        if not numbers:
            continue
        
        # Turnover / Revenue
        if any(kw in line_lower for kw in ['turnover', 'revenue', 'sales revenue', 'net sales', 'total revenue']):
            if 'turnover' not in results:
                # Filter out years (1000-2100)
                valid_numbers = [n for n in numbers if n < 1000 or n > 2100]
                if valid_numbers:
                    results['turnover'] = max(valid_numbers)
                elif numbers:
                    results['turnover'] = max(numbers)
        
        # Operating profit
        elif 'operating' in line_lower and any(kw in line_lower for kw in ['profit', 'income']):
            if 'operating_profit' not in results:
                results['operating_profit'] = max(numbers)
        
        # Profit before tax
        elif any(kw in line_lower for kw in ['profit before tax', 'loss before tax', 'ebt', 'pbt']):
            if 'profit_before_tax' not in results:
                results['profit_before_tax'] = max(numbers)
        
        # Profit/Loss for year
        elif any(kw in line_lower for kw in ['profit for the financial year', 'loss for the financial year', 'profit for the year', 'loss for the year']):
            if 'profit_loss_for_year' not in results:
                # Get the number, but filter out years (1000-2100)
                valid_nums = [n for n in numbers if n < 1000 or n > 2100]
                if valid_nums:
                    results['profit_loss_for_year'] = max(valid_nums)
                elif numbers:
                    results['profit_loss_for_year'] = max(numbers)
    
    return results

# Process all files
output_folder = WORKSPACE_PATH / "pl_metrics_cleaned"
output_folder.mkdir(exist_ok=True)

all_metrics = []

print("\n" + "=" * 120)
print("EXTRACTING P&L METRICS - IMPROVED TABLE PARSING")
print("=" * 120 + "\n")

for file_path in sorted(WORKSPACE_PATH.glob("*_pl.txt")):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except (IOError, OSError) as e:
        print(f"Warning: Could not read {file_path}: {e}")
        continue
    
    lines = content.split('\n')
    
    # Determine currency
    currency = 'Unknown'
    if '$' in content:
        currency = 'USD'
    elif '€' in content:
        currency = 'EUR'
    elif '£' in content:
        currency = 'GBP'
    
    # Extract metrics
    metrics_dict = find_pl_table(lines)
    
    if metrics_dict:
        metrics = {
            'filename': file_path.stem,
            'currency': currency,
            'turnover': metrics_dict.get('turnover'),
            'operating_profit': metrics_dict.get('operating_profit'),
            'profit_before_tax': metrics_dict.get('profit_before_tax'),
            'profit_loss_for_year': metrics_dict.get('profit_loss_for_year'),
        }
        
        all_metrics.append(metrics)
        
        # Save individual JSON
        with open(output_folder / f"{metrics['filename']}_pl_table.json", 'w') as f:
            json.dump(metrics, f, indent=2)
        
        # Show results
        vals_found = sum(1 for v in [metrics['turnover'], metrics['operating_profit'], metrics['profit_before_tax'], metrics['profit_loss_for_year']] if v)
        if vals_found > 0:
            print(f"✓ {file_path.name[:50]:50} | {vals_found} metrics found")
            if metrics['turnover']:
                print(f"    Turnover: {metrics['turnover']:>15,.0f}")
            if metrics['operating_profit']:
                print(f"    Operating Profit: {metrics['operating_profit']:>15,.0f}")
            if metrics['profit_before_tax']:
                print(f"    Profit Before Tax: {metrics['profit_before_tax']:>15,.0f}")
            if metrics['profit_loss_for_year']:
                print(f"    Profit/Loss for Year: {metrics['profit_loss_for_year']:>15,.0f}")

# Save consolidated
with open(output_folder / 'all_pl_metrics.json', 'w') as f:
    json.dump(all_metrics, f, indent=2)

# Save CSV
with open(output_folder / 'pl_metrics_summary.csv', 'w') as f:
    w = csv.writer(f)
    w.writerow(['Filename', 'Currency', 'Turnover', 'Operating Profit', 'Profit Before Tax', 'Profit/Loss for Year'])
    for m in all_metrics:
        w.writerow([m['filename'], m['currency'], m['turnover'], m['operating_profit'], m['profit_before_tax'], m['profit_loss_for_year']])

print("\n" + "=" * 120)
print(f"✅ EXTRACTED AND SAVED: {len(all_metrics)} files")
print(f"   Output: {output_folder}")
print("=" * 120 + "\n")
