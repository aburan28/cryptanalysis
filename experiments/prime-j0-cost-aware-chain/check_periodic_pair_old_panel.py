#!/usr/bin/env python3
"""Retain paired native periodic-atlas diagnostics on old design data."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from make_inputs import read_fields


ROOT = Path(__file__).resolve().parent
ARMS = ("tail-pair-periodic-canonical", "tail-pair-periodic-gated27")


def main(bench):
    fixture_path = ROOT / "tail-pair-fused-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    rows = []
    for case_index in (0, 4):
        case = fixture["cases"][case_index]
        path = ROOT / case["scalar_file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == case["scalar_file_sha256"]
        for arm in (ARMS if case_index == 0 else tuple(reversed(ARMS))):
            command = [str(bench), arm, case["curve"]["name"], "0", str(path)]
            process = subprocess.run(command, text=True, capture_output=True)
            fields = read_fields(process.stdout) if process.returncode == 0 else {}
            row = {"curve": case["curve"]["name"], "arm": arm,
                   "command": command, "returncode": process.returncode,
                   "stdout": process.stdout, "stderr": process.stderr,
                   "verified": process.returncode == 0 and fields.get("verified") == "1",
                   "online_ms_exploratory": fields.get("online_ms"),
                   "weighted_group_score": None, "periodic_lookups": None,
                   "periodic_accepted": None, "periodic_fallbacks": None}
            if row["verified"]:
                assert fields["input_digest"] == case["input_digest"]
                assert fields["output_digest"] == case["expected_output_digest"]
                row["weighted_group_score"] = (10 * int(fields["triples"]) +
                                               16 * int(fields["adds"]))
                for key in ("periodic_lookups", "periodic_accepted", "periodic_fallbacks"):
                    row[key] = int(fields[key])
            rows.append(row)
    repo = ROOT.parents[1]
    sources = [Path(__file__), ROOT / "bench.c", ROOT / "make_periodic_pair_native.py",
               repo / "src/ec_tau.c", repo / "src/ec_tau_internal.h",
               repo / "src/generated/tau_pair_periodic.h"]
    result = {"schema": 1, "status": "old_design_data_native_periodic_diagnostic_only",
              "cpu_timing_claim": None, "isolated_receipt": None,
              "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
              "bench_sha256": hashlib.sha256(bench.read_bytes()).hexdigest(),
              "source_sha256": {str(path.relative_to(repo)):
                                hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in sources},
              "rows": rows}
    output = ROOT / "periodic-pair-native-old-panel.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not all(row["verified"] for row in rows):
        raise RuntimeError("native periodic diagnostic retained a failed row")
    for curve in ("glv-j0-32", "j0-56"):
        pair = {row["arm"]: row for row in rows if row["curve"] == curve}
        assert pair[ARMS[1]]["weighted_group_score"] < pair[ARMS[0]]["weighted_group_score"]
    print(json.dumps({"status": result["status"], "rows": len(rows)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    main(args.bench.resolve())
