#!/usr/bin/env python3
"""Compare the 64-bit recoder to the frozen periodic pair word streams."""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import tempfile

from check_periodic_pair_design import parse_trace
from make_inputs import read_fields
from make_tau_pair_fused import ZERO, catalog


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ARMS = ("tail-pair-periodic-canonical", "tail-pair-periodic-gated27")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(bench):
    _, _, contributions, _, _ = catalog()
    max_norm = max(a * a + 3 * a * b + 3 * b * b for a, b in contributions)
    assert len(contributions) == 727 and max_norm == 532
    old_path = ROOT / "periodic-pair-native-design.json"
    old = json.loads(old_path.read_text())
    csv_path = ROOT / old["raw_csv"]
    assert old["status"] == "old_design_data_native_periodic_word_comparison"
    assert all(not run["problems"] for run in old["runs"])
    assert sha256(csv_path) == old["raw_csv_sha256"]
    old_runs = {(run["curve"], run["arm"], run["chunk"]): run
                for run in old["runs"]}
    rows = list(csv.DictReader(csv_path.open(newline="")))
    assert len(rows) == 2048 and all(row["exact_match"] == "True" for row in rows)
    grouped = {}
    for row in rows:
        key = (row["curve"], row["arm"], int(row["chunk"]))
        grouped.setdefault(key, []).append(row)
    assert set(grouped) == set(old_runs) and len(grouped) == 32

    runs = []
    with tempfile.TemporaryDirectory(prefix="periodic-int64-design-") as directory:
        for curve in ("glv-j0-32", "j0-56"):
            for chunk in range(8):
                for arm in ARMS:
                    key = (curve, arm, chunk)
                    expected = grouped[key]
                    assert [int(row["index"]) for row in expected] == list(range(64))
                    scalars = [int(row["scalar"]) for row in expected]
                    scalar_path = Path(directory) / f"{curve}-{chunk}.scalars.bin"
                    scalar_path.write_bytes(struct.pack("<64Q", *scalars))
                    command = [str(bench), arm, curve, "0", str(scalar_path)]
                    process = subprocess.run(command, text=True, capture_output=True,
                                             env={**os.environ, "CA_PAIR_TRACE_WORDS": "1"},
                                             timeout=120)
                    traces, other_stderr = parse_trace(process.stderr)
                    fields = read_fields(process.stdout) if process.returncode == 0 else {}
                    prior = read_fields(old_runs[key]["stdout"])
                    problems = []
                    if process.returncode != 0 or other_stderr or len(traces) != 64:
                        problems.append("process, stderr, or trace count mismatch")
                    words = [tuple(map(int, row["expected_words"].split())) for row in expected]
                    for index, planned in enumerate(words):
                        if traces.get(index) != planned:
                            problems.append(f"word mismatch at {index}")
                    for name, wanted in (("triples", sum(max(len(w) - 1, 0) for w in words)),
                                         ("adds", sum(word != ZERO for w in words for word in w)),
                                         ("periodic_lookups", old_runs[key]["expected_lookups"]),
                                         ("periodic_accepted", old_runs[key]["expected_accepted"]),
                                         ("periodic_fallbacks", 0), ("periodic_checks", 64),
                                         ("verified", 1)):
                        if fields.get(name) != str(wanted):
                            problems.append(f"{name}: {fields.get(name)} != {wanted}")
                    for name in ("input_digest", "output_digest", "periodic_word_digest"):
                        if fields.get(name) != prior.get(name):
                            problems.append(f"{name} mismatch")
                    runs.append({"curve": curve, "arm": arm, "chunk": chunk,
                                 "scalar_sha256": sha256(scalar_path),
                                 "returncode": process.returncode,
                                 "stdout": process.stdout, "stderr": process.stderr,
                                 "problems": problems})
    result = {"schema": 1, "status": "exact_match" if
              all(not run["problems"] for run in runs) else "mismatch",
              "claim": "old-design correctness control; no CPU speed claim",
              "baseline_design_sha256": sha256(old_path),
              "baseline_word_csv_sha256": sha256(csv_path),
              "pair_contribution_count": len(contributions),
              "maximum_pair_contribution_norm": max_norm,
              "bench_sha256": sha256(bench),
              "library_build_cache_sha256": sha256(REPO / "build-cost-aware/CMakeCache.txt"),
              "host": {"system": platform.system(), "machine": platform.machine()},
              "design64_build_command": ["cc", "-O3", "-std=c11", "-DSCALARS=64",
                                         "-Iinclude", "-Isrc",
                                         "experiments/prime-j0-cost-aware-chain/bench.c",
                                         "build-cost-aware/libcryptanalysis.a", "-lm",
                                         "-lpthread", "-o",
                                         "build-cost-aware/ca_tau_chain_design64"],
              "source_sha256": {str(path.relative_to(REPO)): sha256(path)
                                for path in (Path(__file__), REPO / "src/ec_tau.c",
                                             REPO / "src/ec_tau_internal.h",
                                             REPO / "src/generated/tau_pair_fused.h",
                                             REPO / "src/generated/tau_pair_periodic.h",
                                             ROOT / "bench.c", ROOT / "make_tau_pair_fused.py")},
              "runs": runs}
    (ROOT / "periodic-pair-int64-design.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "runs": len(runs),
                      "exact_word_streams": len(rows)}, sort_keys=True))
    if result["status"] != "exact_match":
        raise RuntimeError("64-bit recoder differs from frozen design word streams")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    main(args.bench.resolve())
