"""
Display P&L metrics in clean formatted table like before
"""

import csv
from pathlib import Path

csv_file = Path('/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample/pl_metrics_cleaned/pl_metrics_summary.csv')

print("\n" + "="*90)
print("P&L METRICS - TURNOVER, OPERATING PROFIT, PROFIT BEFORE TAX, NET PROFIT")
print("="*90 + "\n")

# Read and display only companies with data
companies_with_data = []
with open(csv_file) as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Check if any metric has data
        has_data = any([
            row['Turnover'] and row['Turnover'] != '',
            row['Operating Profit'] and row['Operating Profit'] != '',
            row['Profit Before Tax'] and row['Profit Before Tax'] != '',
            row['Profit/Loss for Year'] and row['Profit/Loss for Year'] != ''
        ])
        if has_data:
            companies_with_data.append(row)

# Format and display
print(f"{'Company':<35} {'Turnover':>15} {'Op. Profit':>15} {'PBT':>15} {'Net Profit':>15} {'Currency':<5}")
print("-" * 90)

for row in companies_with_data:
    company = row['Filename']
    turnover = row['Turnover'] if row['Turnover'] and row['Turnover'] != '' else '—'
    op_profit = row['Operating Profit'] if row['Operating Profit'] and row['Operating Profit'] != '' else '—'
    pbt = row['Profit Before Tax'] if row['Profit Before Tax'] and row['Profit Before Tax'] != '' else '—'
    net_profit = row['Profit/Loss for Year'] if row['Profit/Loss for Year'] and row['Profit/Loss for Year'] != '' else '—'
    currency = row['Currency']
    
    # Format numbers with commas
    try:
        if turnover != '—':
            turnover = f"{int(float(turnover)):,}"
    except:
        pass
    
    try:
        if op_profit != '—':
            op_profit = f"{int(float(op_profit)):,}"
    except:
        pass
    
    try:
        if pbt != '—':
            pbt = f"{int(float(pbt)):,}"
    except:
        pass
        
    try:
        if net_profit != '—':
            net_profit = f"{int(float(net_profit)):,}"
    except:
        pass
    
    print(f"{company:<35} {turnover:>15} {op_profit:>15} {pbt:>15} {net_profit:>15} {currency:<5}")

print("-" * 90)
print(f"\n📁 CSV File: {csv_file}\n")
