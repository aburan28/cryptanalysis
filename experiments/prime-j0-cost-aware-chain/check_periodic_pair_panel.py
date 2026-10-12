#!/usr/bin/env python3
"""Run the frozen paired periodic-atlas operation panel sequentially."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from make_inputs import read_fields


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
REFERENCE = "tail-pair-periodic-canonical"
CANDIDATE = "tail-pair-periodic-gated27"
TIMEOUT_SECONDS = 120


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(bench):
    fixture_path = ROOT / "periodic-pair-native-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    assert fixture["status"] == "frozen_periodic_pair_native_disjoint_fixture"
    assert len(fixture["cases"]) == 8
    rows = []
    for case_index, case in enumerate(fixture["cases"]):
        scalar_path = ROOT / case["scalar_file"]
        assert sha256(scalar_path) == case["scalar_file_sha256"]
        order = (REFERENCE, CANDIDATE) if case_index % 2 == 0 else (CANDIDATE, REFERENCE)
        for position, arm in enumerate(order):
            command = [str(bench), arm, case["curve"]["name"],
                       str(case["point_index"]), str(scalar_path)]
            try:
                process = subprocess.run(command, text=True, capture_output=True,
                                         timeout=TIMEOUT_SECONDS)
                status = "exited"
                returncode = process.returncode
                stdout, stderr = process.stdout, process.stderr
            except subprocess.TimeoutExpired as exc:
                status = "timeout"
                returncode = None
                stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else \
                    (exc.stdout or "")
                stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else \
                    (exc.stderr or "")
            fields = read_fields(stdout) if returncode == 0 else {}
            failures = []
            if status != "exited" or returncode != 0:
                failures.append(f"status={status} returncode={returncode}")
            if fields:
                for key, expected in (("curve", case["curve"]["name"]),
                                      ("point_index", str(case["point_index"])),
                                      ("count", "4096"),
                                      ("input_digest", case["input_digest"]),
                                      ("output_digest", case["expected_output_digest"]),
                                      ("point_entries", "726"),
                                      ("tail_complete_preparation_checks", "726"),
                                      ("periodic_checks", "4096"),
                                      ("rotations", "0"), ("verified", "1")):
                    if fields.get(key) != expected:
                        failures.append(f"{key}: {fields.get(key)} != {expected}")
            elif returncode == 0:
                failures.append("missing benchmark fields")
            score = (10 * int(fields["triples"]) + 16 * int(fields["adds"])) \
                if fields and not failures else None
            rows.append({"case_id": case["id"], "curve": case["curve"]["name"],
                         "point_index": case["point_index"], "arm": arm,
                         "case_run_position": position, "command": command,
                         "status": status, "returncode": returncode,
                         "stdout": stdout, "stderr": stderr, "failures": failures,
                         "verified": not failures,
                         "weighted_group_score": score,
                         "online_ms_exploratory": fields.get("online_ms"),
                         "triples": int(fields["triples"]) if score is not None else None,
                         "adds": int(fields["adds"]) if score is not None else None,
                         "periodic_lookups": int(fields["periodic_lookups"])
                         if score is not None else None,
                         "periodic_accepted": int(fields["periodic_accepted"])
                         if score is not None else None,
                         "periodic_fallbacks": int(fields["periodic_fallbacks"])
                         if score is not None else None})
    pairs = []
    for case in fixture["cases"]:
        pair = {row["arm"]: row for row in rows if row["case_id"] == case["id"]}
        reference, candidate = pair[REFERENCE], pair[CANDIDATE]
        passed = (reference["verified"] and candidate["verified"] and
                  candidate["weighted_group_score"] < reference["weighted_group_score"])
        pairs.append({"case_id": case["id"], "verified": reference["verified"] and
                      candidate["verified"], "operation_gate_pass": passed,
                      "reference_score": reference["weighted_group_score"],
                      "candidate_score": candidate["weighted_group_score"],
                      "saved_score": (reference["weighted_group_score"] -
                                      candidate["weighted_group_score"])
                      if reference["weighted_group_score"] is not None and
                         candidate["weighted_group_score"] is not None else None})
    source_paths = [Path(__file__), ROOT / "bench.c", ROOT / "make_periodic_pair_native.py",
                    ROOT / "make_periodic_pair_inputs.py",
                    ROOT / "check_periodic_pair_inputs.py",
                    REPO / "src/ec_tau.c", REPO / "src/ec_tau_internal.h",
                    REPO / "src/generated/tau_pair_periodic.h", REPO / "CMakeLists.txt"]
    result = {"schema": 1, "status": "native_operation_gate_pass" if
              all(pair["operation_gate_pass"] for pair in pairs) else
              "native_operation_gate_fail",
              "cpu_timing_claim": None, "isolated_receipt": None,
              "online_interval": "first scalar reduction through last affine output, including both recoders and gate in candidate",
              "timeout_seconds_per_arm": TIMEOUT_SECONDS,
              "host_exploratory": {"system": platform.system(), "machine": platform.machine(),
                                   "processor": platform.processor()},
              "protocol_freeze_commit": "e4178e1e02393ae33bd01b98af2243cb011c17cb",
              "build_cache_sha256": sha256(REPO / "build-cost-aware/CMakeCache.txt"),
              "fixture_sha256": sha256(fixture_path),
              "bench_sha256": sha256(bench),
              "source_sha256": {str(path.relative_to(REPO)): sha256(path)
                                for path in source_paths},
              "rows": rows, "pairs": pairs}
    path = ROOT / "periodic-pair-native-panel.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "cases": len(pairs),
                      "passed": sum(pair["operation_gate_pass"] for pair in pairs)},
                     sort_keys=True))
    if result["status"] != "native_operation_gate_pass":
        raise RuntimeError("native operation panel retained a failed case")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    run(args.bench.resolve())
