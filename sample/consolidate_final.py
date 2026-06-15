import json
from pathlib import Path
from typing import Dict, List, Any

# Configuration
WORKSPACE_PATH = Path(__file__).resolve().parent
OUTPUT_FOLDER = WORKSPACE_PATH / "pl_metrics_cleaned"


def load_existing_metrics() -> Dict[str, Any]:
    """Load existing high-quality metrics files."""
    existing_metrics = {}
    for metrics_file in sorted(OUTPUT_FOLDER.glob("*_metrics.json")):
        if any(
            name in metrics_file.name
            for name in ["pl_metrics", "table", "summary", "analysis"]
        ):
            continue

        try:
            with open(metrics_file) as f:
                data = json.load(f)
            key = data.get("filename", metrics_file.stem)
            existing_metrics[key] = data
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load {metrics_file}: {e}")

    return existing_metrics


def load_table_metrics() -> List[Dict[str, Any]]:
    """Load newly extracted table data."""
    try:
        with open(OUTPUT_FOLDER / "all_pl_metrics.json") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error: Could not load table metrics: {e}")
        return []


def merge_metrics(
    existing_metrics: Dict[str, Any], table_metrics: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Merge existing and newly extracted metrics."""
    final_metrics = []
    seen = set()

    for m in table_metrics:
        fname = m["filename"]
        if fname in seen:
            continue
        seen.add(fname)

        # Start with existing high-quality data
        if fname in existing_metrics:
            final = existing_metrics[fname].copy()
        else:
            final = {
                "filename": fname,
                "currency": m["currency"],
                "turnover": None,
                "operating_profit": None,
                "profit_before_tax": None,
                "profit_loss_for_year": None,
            }

        # Merge in table data where missing
        for key in [
            "turnover",
            "operating_profit",
            "profit_before_tax",
            "profit_loss_for_year",
        ]:
            if final.get(key) is None and m.get(key) is not None:
                final[key] = m[key]

        final_metrics.append(final)

    return final_metrics


def save_final_metrics(final_metrics: List[Dict[str, Any]]) -> None:
    """Save final consolidated data."""
    with open(OUTPUT_FOLDER / "all_pl_metrics_final.json", "w") as f:
        json.dump(final_metrics, f, indent=2)


def print_summary(final_metrics: List[Dict[str, Any]]) -> None:
    """Print summary of consolidated metrics."""
    print("\n" + "=" * 120)
    print("FINAL CONSOLIDATED P&L METRICS")
    print("=" * 120)
    print(
        f"\n{'Filename':<45} | {'Turn':>12} | {'Op Profit':>12} | "
        f"{'PBT':>12} | {'PFY':>12} | Currency"
    )
    print("-" * 120)

    for m in sorted(final_metrics, key=lambda x: x["filename"]):
        turn = f"{m['turnover']:.0f}" if m["turnover"] else "None"
        op = f"{m['operating_profit']:.0f}" if m["operating_profit"] else "None"
        pbt = f"{m['profit_before_tax']:.0f}" if m["profit_before_tax"] else "None"
        pfy = (
            f"{m['profit_loss_for_year']:.0f}"
            if m["profit_loss_for_year"]
            else "None"
        )

        print(
            f"{m['filename']:<45} | {turn:>12} | {op:>12} | "
            f"{pbt:>12} | {pfy:>12} | {m['currency']}"
        )

    # Show statistics
    total_files = len(final_metrics)
    with_data = sum(
        1
        for m in final_metrics
        if any(
            m.get(k)
            for k in [
                "turnover",
                "operating_profit",
                "profit_before_tax",
                "profit_loss_for_year",
            ]
        )
    )
    turn_count = sum(1 for m in final_metrics if m["turnover"])
    op_count = sum(1 for m in final_metrics if m["operating_profit"])
    pbt_count = sum(1 for m in final_metrics if m["profit_before_tax"])
    pfy_count = sum(1 for m in final_metrics if m["profit_loss_for_year"])

    print("\n" + "=" * 120)
    print("✅ SUMMARY STATISTICS")
    print("=" * 120)
    print(f"Total files: {total_files}")
    print(f"Files with data: {with_data}")
    print(f"Turnover values: {turn_count}")
    print(f"Operating Profit values: {op_count}")
    print(f"Profit Before Tax values: {pbt_count}")
    print(f"Profit/Loss for Year values: {pfy_count}")
    print(
        f"\nTotal data points: {turn_count + op_count + pbt_count + pfy_count} / "
        f"{total_files * 4}"
    )
    print("=" * 120 + "\n")


def main() -> None:
    """Main function to consolidate metrics."""
    existing_metrics = load_existing_metrics()
    table_metrics = load_table_metrics()

    if not table_metrics:
        print("Error: No table metrics found. Exiting.")
        return

    final_metrics = merge_metrics(existing_metrics, table_metrics)
    save_final_metrics(final_metrics)
    print_summary(final_metrics)


if __name__ == "__main__":
    main()
