#!/usr/bin/env python3
"""Paired full/compact positional replay on the frozen disjoint fixture."""

import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "compact-pos-inputs.json"
OUTPUT = ROOT / "compact-pos-panel.json"
FULL_POINT_BYTES = 64 * 2 * 9 * 32


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(stdout):
    return dict(token.split("=", 1) for token in stdout.strip().split())


def arm(bench, case, mode):
    command = [str(bench), mode, case["curve"]["name"], str(case["point_index"]),
               str(ROOT / case["scalar_file"])]
    try:
        process = subprocess.run(command, capture_output=True, text=True,
                                 timeout=120, check=False)
        row = {"case_id": case["id"], "mode": mode,
               "exit_code": process.returncode, "stdout": process.stdout,
               "stderr": process.stderr, "timed_out": False}
    except subprocess.TimeoutExpired as error:
        row = {"case_id": case["id"], "mode": mode,
               "exit_code": None,
               "stdout": (error.stdout or b"").decode(errors="replace"),
               "stderr": (error.stderr or b"").decode(errors="replace"),
               "timed_out": True}
    if row["exit_code"] == 0:
        parsed = fields(row["stdout"])
        row["fields"] = parsed
        row["verified"] = (
            parsed.get("verified") == "1"
            and parsed.get("curve") == case["curve"]["name"]
            and parsed.get("point_index") == str(case["point_index"])
            and parsed.get("count") == "4096"
            and parsed.get("input_digest") == case["input_digest"]
            and parsed.get("output_digest") == case["expected_output_digest"]
            and parsed.get("base_x") == case["base_x"]
            and parsed.get("base_y") == case["base_y"]
        )
    else:
        row["verified"] = False
    return row


def run(bench):
    fixture = json.loads(FIXTURE.read_text())
    assert fixture["status"] == "frozen_compact_pos_disjoint_fixture"
    result = {"schema": 1, "status": "exploratory_correctness_and_operation_gate",
              "protocol": "COMPACT_POSITIONAL.md",
              "runner_sha256": sha256(Path(__file__)),
              "fixture_sha256": sha256(FIXTURE), "bench_sha256": sha256(bench),
              "host_exploratory": {"system": platform.system(),
                                   "machine": platform.machine()},
              "isolated_receipt": None, "cpu_timing_claim": None,
              "full_point_table_bytes": FULL_POINT_BYTES,
              "rows": [], "pairs": []}
    for index, case in enumerate(fixture["cases"]):
        scalar_path = ROOT / case["scalar_file"]
        if sha256(scalar_path) != case["scalar_file_sha256"]:
            raise ValueError(f"changed frozen scalar file: {case['id']}")
        order = ("pos-global", "pos-compact") if index % 2 == 0 else (
            "pos-compact", "pos-global")
        arms = {}
        for mode in order:
            arms[mode] = arm(bench, case, mode)
            result["rows"].append(arms[mode])
        full = arms["pos-global"]
        compact = arms["pos-compact"]
        passed = full["verified"] and compact["verified"]
        if passed:
            f, c = full["fields"], compact["fields"]
            passed = (all(f[key] == c[key] for key in
                          ("adds", "rotations", "output_inversions"))
                      and int(c["fallbacks"]) == 0
                      and int(c["point_table_bytes"]) * 3 <= FULL_POINT_BYTES
                      and int(c["prep_triples"]) * 3 <= int(f["prep_triples"])
                      and int(c["prep_layer_inversions"]) == 1
                      and int(f["prep_layer_inversions"]) == 1)
        result["pairs"].append({"case_id": case["id"], "verified": full["verified"]
                                and compact["verified"], "gate_pass": passed,
                                "full_adds": int(full["fields"]["adds"]) if full["verified"] else None,
                                "compact_adds": int(compact["fields"]["adds"]) if compact["verified"] else None,
                                "compact_point_table_bytes": int(compact["fields"]["point_table_bytes"])
                                if compact["verified"] else None,
                                "compact_fallbacks": int(compact["fields"]["fallbacks"])
                                if compact["verified"] else None})
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["pairs"], indent=2))
    if not all(pair["gate_pass"] for pair in result["pairs"]):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    run(args.bench.resolve())
