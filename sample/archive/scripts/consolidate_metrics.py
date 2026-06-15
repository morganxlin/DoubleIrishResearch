import json
from pathlib import Path

workspace = Path('/Users/morganlin/Library/CloudStorage/OneDrive-SharedLibraries-VillanovaUniversity/Brian Grant - Grant and Lin/sample')
output_folder = workspace / 'pl_metrics_cleaned'

# Load all existing metrics
all_metrics = []
for metrics_file in sorted(output_folder.glob('*_metrics.json')):
    # Skip files with "pl_metrics" or "analysis" in the name
    if 'pl_metrics' in metrics_file.name or 'analysis' in metrics_file.name or 'summary' in metrics_file.name:
        continue
    
    with open(metrics_file) as f:
        data = json.load(f)
    
    # Check if it has any actual data
    if any(data.get(k) for k in ['turnover', 'operating_profit', 'profit_before_tax', 'profit_loss_for_year']):
        all_metrics.append(data)

print(f"Found {len(all_metrics)} metrics files with data\n")

# Show summary
for m in sorted(all_metrics, key=lambda x: x['filename']):
    vals = sum(1 for v in [m.get('turnover'), m.get('operating_profit'), m.get('profit_before_tax'), m.get('profit_loss_for_year')] if v is not None)
    print(f"{m['filename'][:45]:45} | {vals}/4 metrics | Turn={str(m.get('turnover'))[:12]:12} Op={str(m.get('operating_profit'))[:12]:12}")

# Save consolidated
with open(output_folder / 'all_pl_metrics.json', 'w') as f:
    json.dump(all_metrics, f, indent=2)

print(f"\n✅ Consolidated {len(all_metrics)} metrics files")
print(f"   Saved to: all_pl_metrics.json")

# Stats
total_vals = sum(1 for m in all_metrics for v in [m.get('turnover'), m.get('operating_profit'), m.get('profit_before_tax'), m.get('profit_loss_for_year')] if v is not None)
total_possible = len(all_metrics) * 4
print(f"\nData coverage: {total_vals}/{total_possible} ({100*total_vals/total_possible:.1f}%)")
