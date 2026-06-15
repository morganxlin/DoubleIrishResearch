#!/usr/bin/env python3
"""Quick lookup tool for P&L metrics. Finds and displays extracted numbers."""

import csv
import sys
from pathlib import Path
from typing import List, Dict, Any

# Configuration
BASE_PATH = Path(__file__).resolve().parent
METRICS_FOLDER = BASE_PATH / "pl_metrics_cleaned"
CSV_FILE = METRICS_FOLDER / "pl_metrics_summary.csv"


def load_companies() -> List[Dict[str, Any]]:
    """Load and display P&L metrics."""
    try:
        companies = []
        with open(CSV_FILE) as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip if all metrics are None
                if any(
                    row.get(key) != "None"
                    for key in [
                        "Turnover",
                        "Operating Profit",
                        "Profit Before Tax",
                        "Profit/Loss for Year",
                    ]
                ):
                    companies.append(row)
        return companies
    except FileNotFoundError:
        print(f"Error: Could not find {CSV_FILE}")
        return []
    except (csv.Error, KeyError) as e:
        print(f"Error reading CSV: {e}")
        return []


def display_results(companies: List[Dict[str, Any]]) -> None:
    """Display company metrics."""
    print("\n" + "=" * 70)
    print("P&L METRICS QUICK LOOKUP")
    print("=" * 70)

    # Sort by company
    companies.sort(key=lambda x: x["Filename"])

    print(f"\n📊 Found {len(companies)} companies with data:\n")

    for i, company in enumerate(companies, 1):
        name = company["Filename"]
        currency = company["Currency"]

        print(f"{i}. {name}")
        print(f"   Currency: {currency}")

        if company.get("Turnover") != "None":
            try:
                print(f"   Turnover: {float(company['Turnover']):,.0f}")
            except ValueError:
                pass
        if company.get("Operating Profit") != "None":
            try:
                print(f"   Operating Profit: {float(company['Operating Profit']):,.0f}")
            except ValueError:
                pass
        if company.get("Profit Before Tax") != "None":
            try:
                print(f"   Profit Before Tax: {float(company['Profit Before Tax']):,.0f}")
            except ValueError:
                pass
        if company.get("Profit/Loss for Year") != "None":
            try:
                print(f"   Profit/Loss for Year: {float(company['Profit/Loss for Year']):,.0f}")
            except ValueError:
                pass
        print()


def find_pl_numbers() -> None:
    """Main function."""
    companies = load_companies()
    if not companies:
        return

    display_results(companies)

    # Show where files are
    print("=" * 70)
    print("📁 WHERE TO FIND THESE NUMBERS:\n")
    print(f"CSV (Quick View):")
    print(f"  → {CSV_FILE}")
    print(f"\nJSON (Full Data):")
    print(f"  → {METRICS_FOLDER}/all_pl_metrics.json")
    print(f"  → {METRICS_FOLDER}/*_metrics.json (individual companies)")
    print(f"\nAnalysis:")
    print(f"  → {METRICS_FOLDER}/profit_shifting_analysis.json")
    print(f"  → {METRICS_FOLDER}/profit_shifting_indicators.csv")
    print("=" * 70 + "\n")

def search_company(search_term):
    """Search for a specific company."""

    print(f"\n🔍 Searching for: {search_term}\n")

    with open(CSV_FILE) as f:
        reader = csv.DictReader(f)
        found = False
        for row in reader:
            if search_term.lower() in row['Filename'].lower():
                found = True
                print(f"✅ Found: {row['Filename']}")
                print(f"   Currency: {row['Currency']}")
                print(f"   Turnover: {row['Turnover']}")
                print(f"   Operating Profit: {row['Operating Profit']}")
                print(f"   Profit Before Tax: {row['Profit Before Tax']}")
                print(f"   Net Profit/Loss: {row['Profit/Loss for Year']}\n")
    
    if not found:
        print(f"❌ No company found with '{search_term}'\n")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Search for specific company
        search_company(sys.argv[1])
    else:
        # Show all
        find_pl_numbers()
