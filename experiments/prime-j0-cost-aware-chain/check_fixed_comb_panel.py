#!/usr/bin/env python3
"""Replay frozen inputs against binary comb and the older positional tau table."""

import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "mixed-full-inputs.json"
PRIOR = HERE / "mixed-full-native-panel.json"
OUTPUT = HERE / "fixed-comb9-panel.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(stdout):
    return dict(item.split("=", 1) for item in stdout.strip().split())


def run(bench):
    fixture = json.loads(FIXTURE.read_text())
    prior = json.loads(PRIOR.read_text())
    prior_pairs = {pair["case_id"]: pair for pair in prior["pairs"]}
    result = {
        "schema": 1,
        "status": "exploratory_correctness_and_operation_control",
        "methods": ["fixed-comb9", "pos-global"],
        "protocol": "fixed width 9; depth ceil(bitlength(order-1)/9); 512 slots including identity",
        "source_sha256": sha256(Path(__file__)),
        "bench_sha256": sha256(bench),
        "fixture_sha256": sha256(FIXTURE),
        "prior_panel_sha256": sha256(PRIOR),
        "host_exploratory": {"system": platform.system(), "machine": platform.machine()},
        "isolated_receipt": None,
        "cpu_timing_claim": None,
        "online_interval": "first scalar multiplication after precomputation through last affine output",
        "rows": [],
    }
    for case in fixture["cases"]:
        scalar_file = HERE / case["scalar_file"]
        if sha256(scalar_file) != case["scalar_file_sha256"]:
            raise ValueError(f"frozen scalar hash mismatch: {case['id']}")
        command = [str(bench), "fixed-comb9", case["curve"]["name"],
                   str(case["point_index"]), str(scalar_file)]
        try:
            process = subprocess.run(command, capture_output=True, text=True,
                                     timeout=120, check=False)
            row = {"case_id": case["id"], "exit_code": process.returncode,
                   "stdout": process.stdout, "stderr": process.stderr,
                   "timed_out": False}
        except subprocess.TimeoutExpired as error:
            row = {"case_id": case["id"], "exit_code": None,
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
                and parsed.get("point_entries") == "512"
            )
            row["comb_score"] = (8 * int(parsed["doubles"]) +
                                  16 * int(parsed["adds"]))
            row["full_digit_score"] = prior_pairs[case["id"]]["full_score"]
            row["operation_gate_pass"] = (row["verified"] and
                                          row["comb_score"] < row["full_digit_score"])
        else:
            row["verified"] = False
            row["comb_score"] = None
            row["full_digit_score"] = prior_pairs[case["id"]]["full_score"]
            row["operation_gate_pass"] = False
        positional_command = [str(bench), "pos-global", case["curve"]["name"],
                              str(case["point_index"]), str(scalar_file)]
        try:
            positional = subprocess.run(positional_command, capture_output=True, text=True,
                                        timeout=120, check=False)
            pos = {"exit_code": positional.returncode, "stdout": positional.stdout,
                   "stderr": positional.stderr, "timed_out": False}
        except subprocess.TimeoutExpired as error:
            pos = {"exit_code": None,
                   "stdout": (error.stdout or b"").decode(errors="replace"),
                   "stderr": (error.stderr or b"").decode(errors="replace"),
                   "timed_out": True}
        if pos["exit_code"] == 0:
            parsed = fields(pos["stdout"])
            pos["fields"] = parsed
            pos["verified"] = (
                parsed.get("verified") == "1"
                and parsed.get("curve") == case["curve"]["name"]
                and parsed.get("point_index") == str(case["point_index"])
                and parsed.get("count") == "4096"
                and parsed.get("input_digest") == case["input_digest"]
                and parsed.get("output_digest") == case["expected_output_digest"]
                and parsed.get("base_x") == case["base_x"]
                and parsed.get("base_y") == case["base_y"]
            )
            pos["score"] = 16 * int(parsed["adds"]) + int(parsed["rotations"])
        else:
            pos["verified"] = False
            pos["score"] = None
        row["pos_global"] = pos
        result["rows"].append(row)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    summary = [{"case_id": row["case_id"], "comb_score": row["comb_score"],
                "full_digit_score": row["full_digit_score"],
                "pos_global_score": row["pos_global"]["score"],
                "verified": row["verified"] and row["pos_global"]["verified"]}
               for row in result["rows"]]
    print(json.dumps(summary, indent=2))
    if not all(row["operation_gate_pass"] and row["pos_global"]["verified"]
               for row in result["rows"]):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    run(args.bench.resolve())
