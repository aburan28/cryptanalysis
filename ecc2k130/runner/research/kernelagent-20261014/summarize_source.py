"""Summarize sampled PC stalls from a retained Nsight source page receipt."""

import csv
import hashlib
import io
import json
from pathlib import Path
import sys


def main(receipt_name: str, output_name: str) -> None:
    receipt_path = Path(receipt_name)
    output_path = Path(output_name)
    if output_path.exists():
        raise FileExistsError(output_path)
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    if receipt.get("outcome") != "profiled":
        raise ValueError("source summary requires a completed profile")

    sass_rows = list(csv.reader(io.StringIO(receipt["source_sass"]["output"])))
    header = sass_rows[1]
    if header[0:4] != ["Address", "Source", "Warp Stall Sampling (All Samples)",
                       "Warp Stall Sampling (Not-issued Samples)"]:
        raise ValueError("unexpected SASS source page")
    entries = [dict(zip(header, row)) for row in sass_rows[2:]
               if len(row) == len(header) and row[0].startswith("0x")]
    if not entries:
        raise ValueError("SASS source page has no instructions")

    locations: dict[str, set[tuple[str, int]]] = {}
    current_file = ""
    current_line = 0
    for row in csv.reader(io.StringIO(receipt["source_cuda_sass"]["output"])):
        if len(row) >= 2 and row[0] == "File Path":
            current_file, current_line = row[1], 0
        elif row and row[0].isdigit():
            current_line = int(row[0])
        if len(row) > 2 and row[2].startswith("0x") and current_line:
            locations.setdefault(row[2], set()).add((current_file, current_line))

    reasons = [name for name in header if name.endswith("(Not Issued)")]
    count = lambda value: int(value) if value.isdigit() else 0
    total = sum(count(row["Warp Stall Sampling (Not-issued Samples)"]) for row in entries)
    reason_totals = {name: sum(count(row[name]) for row in entries) for name in reasons}
    if sum(reason_totals.values()) != total:
        raise ValueError("stall reason totals differ from not-issued samples")
    ranked = sorted(entries,
                    key=lambda row: count(row["Warp Stall Sampling (Not-issued Samples)"]),
                    reverse=True)
    summary = {
        "receipt": str(receipt_path),
        "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "ncu_report_sha256": receipt["ncu_report_sha256"],
        "instruction_count": len(entries),
        "not_issued_sample_count": total,
        "reason_totals": reason_totals,
        "top_instructions": [
            {"address": row["Address"], "sass": row["Source"].strip(),
             "not_issued_samples": count(row["Warp Stall Sampling (Not-issued Samples)"]),
             "reasons": {name: count(row[name]) for name in reasons if count(row[name])},
             "source_locations": [{"file": file, "line": line}
                                  for file, line in sorted(locations.get(row["Address"], set()))]}
            for row in ranked[:25]
        ],
    }
    output_path.write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: summarize_source.py receipt.json summary.json")
    main(sys.argv[1], sys.argv[2])
