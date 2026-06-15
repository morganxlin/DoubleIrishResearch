#!/usr/bin/env python3
"""Compare extracted P&L metrics against statement-block reference values."""

from pathlib import Path
import json
import re

from extract_pl_metrics_v2 import (
    extract_pl_metrics,
    extract_statement_source_text,
    find_best_statement_block,
    extract_metrics_from_statement_block,
    infer_year_from_stem,
)


def main() -> None:
    workspace = Path(__file__).resolve().parent
    pl_files = sorted(workspace.glob("*_pl.txt"))

    mismatches = []
    for pl_path in pl_files:
        stem = pl_path.stem.replace("_pl", "")
        json_path = workspace / f"{stem}.json"
        extracted = extract_pl_metrics(pl_path)
        ref = extract_metrics_from_statement_block(
            extract_statement_source_text(json_path), stem
        )
        block = find_best_statement_block(extract_statement_source_text(json_path))
        has_block = bool(block)

        for key in (
            "turnover",
            "operating_profit",
            "profit_before_tax",
            "profit_loss_for_year",
        ):
            ex = extracted.get(key)
            rf = ref.get(key)
            if rf is not None and ex != rf:
                mismatches.append(
                    {
                        "file": pl_path.name,
                        "metric": key,
                        "extracted": ex,
                        "statement_block": rf,
                        "has_block": has_block,
                    }
                )
            elif rf is None and ex is not None and has_block:
                # extracted from fallback when block had value path failed
                if not any(
                    f"{key}: statement-block" in n for n in extracted.get("raw_data", [])
                ):
                    mismatches.append(
                        {
                            "file": pl_path.name,
                            "metric": key,
                            "extracted": ex,
                            "statement_block": None,
                            "note": "fallback only",
                            "has_block": has_block,
                        }
                    )

    print(f"Checked {len(pl_files)} files, {len(mismatches)} issues\n")
    for m in mismatches:
        print(
            f"{m['file']:50} {m['metric']:22} "
            f"extracted={m.get('extracted')} ref={m.get('statement_block')} "
            f"{m.get('note', '')}"
        )

    out = workspace / "pl_metrics_cleaned" / "audit_mismatches.json"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w") as f:
        json.dump(mismatches, f, indent=2)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
