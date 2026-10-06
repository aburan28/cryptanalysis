#!/usr/bin/env python3
"""Run the frozen paired full-digit mixed-tail operation panel sequentially."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from make_inputs import read_fields


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
UNIT = "tail-pair-mixed-radix"
FULL = "tail-pair-mixed-full-digits"
TIMEOUT_SECONDS = 120
FIXTURE_SHA256 = "fb7661410d765073239759d4e87c660d6e17c4baad345f9fd5804b41a56a6991"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(bench):
    fixture_path = ROOT / "mixed-full-inputs.json"
    assert sha256(fixture_path) == FIXTURE_SHA256
    fixture = json.loads(fixture_path.read_text())
    assert fixture["status"] == "frozen_mixed_full_disjoint_fixture"
    assert len(fixture["cases"]) == 8
    rows = []
    for case_index, case in enumerate(fixture["cases"]):
        scalar_path = ROOT / case["scalar_file"]
        assert sha256(scalar_path) == case["scalar_file_sha256"]
        order = (UNIT, FULL) if case_index % 2 == 0 else (FULL, UNIT)
        for position, arm in enumerate(order):
            command = [str(bench), arm, case["curve"]["name"],
                       str(case["point_index"]), str(scalar_path)]
            try:
                process = subprocess.run(command, text=True, capture_output=True,
                                         timeout=TIMEOUT_SECONDS)
                status, returncode = "exited", process.returncode
                stdout, stderr = process.stdout, process.stderr
            except subprocess.TimeoutExpired as exc:
                status, returncode = "timeout", None
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
                                      ("mixed_checks", "4096"),
                                      ("mixed_fallbacks", "0"),
                                      ("prep_bytes", "24336"),
                                      ("point_table_bytes", "23232"),
                                      ("static_map_bytes", "99853"),
                                      ("rotations", "0"), ("verified", "1")):
                    if fields.get(key) != expected:
                        failures.append(f"{key}: {fields.get(key)} != {expected}")
            elif returncode == 0:
                failures.append("missing benchmark fields")
            counts = {}
            if fields and not failures:
                for key in ("triples", "tau_steps", "doubles", "adds"):
                    try:
                        counts[key] = int(fields[key])
                    except (KeyError, ValueError):
                        failures.append(f"invalid {key}")
            score = (10 * counts["triples"] + 6 * counts["tau_steps"] +
                     8 * counts["doubles"] + 16 * counts["adds"]) if not failures else None
            rows.append({"case_id": case["id"], "curve": case["curve"]["name"],
                         "point_index": case["point_index"], "arm": arm,
                         "case_run_position": position, "command": command,
                         "status": status, "returncode": returncode,
                         "stdout": stdout, "stderr": stderr, "failures": failures,
                         "verified": not failures, "weighted_group_score": score,
                         "online_ms_exploratory": fields.get("online_ms"),
                         "counts": counts if not failures else None})
    pairs = []
    for case in fixture["cases"]:
        group = {row["arm"]: row for row in rows if row["case_id"] == case["id"]}
        unit, full = group[UNIT], group[FULL]
        verified = unit["verified"] and full["verified"]
        passed = verified and full["weighted_group_score"] < unit["weighted_group_score"]
        pairs.append({"case_id": case["id"], "verified": verified,
                      "operation_gate_pass": passed,
                      "unit_score": unit["weighted_group_score"],
                      "full_score": full["weighted_group_score"],
                      "saved_score": (unit["weighted_group_score"] -
                                      full["weighted_group_score"])
                      if unit["weighted_group_score"] is not None and
                         full["weighted_group_score"] is not None else None})
    source_paths = [Path(__file__), ROOT / "bench.c", ROOT / "make_mixed_full_inputs.py",
                    ROOT / "check_mixed_full_inputs.py", ROOT / "screen_mixed_full_digits.py",
                    ROOT / "mixed-full-digits-screen.json", REPO / "src/ec_tau.c",
                    REPO / "src/ec_tau_internal.h",
                    REPO / "src/generated/tau_pair_mixed_full_digits.h", REPO / "CMakeLists.txt"]
    frozen_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                   text=True, capture_output=True, check=True).stdout.strip()
    result = {"schema": 1, "status": "native_operation_gate_pass" if
              all(pair["operation_gate_pass"] for pair in pairs) else
              "native_operation_gate_fail",
              "cpu_timing_claim": None, "isolated_receipt": None,
              "online_interval": "first scalar reduction through last affine output, including recoding, map reads, group operations, conversion, and storage",
              "timeout_seconds_per_arm": TIMEOUT_SECONDS,
              "host_exploratory": {"system": platform.system(), "machine": platform.machine(),
                                   "processor": platform.processor()},
              "protocol_freeze_commit": "ef9aef0e",
              "implementation_commit": "27943663",
              "fixture_runner_commit": frozen_commit,
              "fixture_sha256": sha256(fixture_path),
              "build_cache_sha256": sha256(REPO / "build-cost-aware/CMakeCache.txt"),
              "bench_sha256": sha256(bench),
              "source_sha256": {str(path.relative_to(REPO)): sha256(path)
                                for path in source_paths},
              "rows": rows, "pairs": pairs}
    output = ROOT / "mixed-full-native-panel.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "cases": len(pairs),
                      "passed": sum(pair["operation_gate_pass"] for pair in pairs)},
                     sort_keys=True))
    if result["status"] != "native_operation_gate_pass":
        raise RuntimeError("full-digit operation panel retained a failed case")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    run(args.bench.resolve())
