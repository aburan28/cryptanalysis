#!/usr/bin/env python3
"""Run the frozen paired compact-width4 versus fused-width3 panel."""

import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "tau3-fused-inputs.json"
OUTPUT = ROOT / "tau3-fused-panel.json"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def fields(stdout):
    tokens = [item.split("=", 1) for item in stdout.strip().split()]
    if any(len(token) != 2 for token in tokens):
        raise ValueError("malformed benchmark fields")
    parsed = dict(tokens)
    if len(parsed) != len(tokens):
        raise ValueError("duplicate benchmark field")
    return parsed


def int_field(row, key):
    try:
        return int(row.get("fields", {})[key])
    except (KeyError, TypeError, ValueError):
        return None


def timeout_text(value):
    return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")


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
        row = {"case_id": case["id"], "mode": mode, "exit_code": None,
               "stdout": timeout_text(error.stdout),
               "stderr": timeout_text(error.stderr),
               "timed_out": True}
    except OSError as error:
        row = {"case_id": case["id"], "mode": mode, "exit_code": None,
               "stdout": "", "stderr": str(error), "timed_out": False}
    if row["exit_code"] == 0:
        try:
            parsed = fields(row["stdout"])
        except ValueError as error:
            row["parse_error"] = str(error)
            row["verified"] = False
            return row
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
    assert fixture["status"] == "frozen_tau3_fused_disjoint_fixture"
    receipt = {"schema": 1, "status": "exploratory_correctness_and_operation_gate",
               "protocol": "TAU3_FUSED_POSITIONAL.md",
               "runner_sha256": sha256(Path(__file__).read_bytes()),
               "fixture_sha256": sha256(FIXTURE.read_bytes()),
               "bench_sha256": sha256(bench.read_bytes()),
               "ec_tau_source_sha256": sha256((ROOT.parents[1] / "src/ec_tau.c").read_bytes()),
               "header_sha256": sha256((ROOT.parents[1] / "src/generated/tau3_fused.h").read_bytes()),
               "host_exploratory": {"system": platform.system(),
                                    "machine": platform.machine()},
               "isolated_receipt": None, "cpu_timing_claim": None,
               "online_interval": "first target scalar reduction after point preparation through final affine output",
               "rows": [], "pairs": []}
    for index, case in enumerate(fixture["cases"]):
        path = ROOT / case["scalar_file"]
        if sha256(path.read_bytes()) != case["scalar_file_sha256"]:
            raise ValueError(f"changed frozen scalar file: {case['id']}")
        order = ("pos-compact", "tau3-fused-pos") if index % 2 == 0 else (
            "tau3-fused-pos", "pos-compact")
        arms = {}
        for mode in order:
            arms[mode] = arm(bench, case, mode)
            receipt["rows"].append(arms[mode])
        control = arms["pos-compact"]
        candidate = arms["tau3-fused-pos"]
        verified = control["verified"] and candidate["verified"]
        expected_entries = 1372 if case["curve"]["name"] == "glv-j0-32" else 2401
        control_adds = int_field(control, "adds")
        candidate_adds = int_field(candidate, "adds")
        passed = (verified and control_adds is not None and candidate_adds is not None
                  and candidate_adds < control_adds
                  and int_field(candidate, "fallbacks") == 0
                  and int_field(candidate, "tau3_action_fallbacks") == 0
                  and int_field(candidate, "tau3_checks") == 4096
                  and int_field(candidate, "tau3_preparation_checks") == expected_entries
                  and int_field(candidate, "point_entries") == expected_entries
                  and int_field(candidate, "point_table_bytes") == expected_entries * 32
                  and int_field(candidate, "output_inversions") is not None
                  and int_field(candidate, "output_inversions") == int_field(control, "output_inversions"))
        receipt["pairs"].append({"case_id": case["id"], "verified": verified,
                                 "gate_pass": passed,
                                 "control_adds": control_adds,
                                 "candidate_adds": candidate_adds,
                                 "candidate_rotations": int_field(candidate, "rotations"),
                                 "candidate_fallbacks": int_field(candidate, "fallbacks")})
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt["pairs"], indent=2))
    if not all(pair["gate_pass"] for pair in receipt["pairs"]):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    run(args.bench.resolve())
