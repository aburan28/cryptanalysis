#!/usr/bin/env python3
"""Compare every old-data native tau3 action to the frozen Python map."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess

from make_tau3_fused import block_pattern, build, recode
from run import representatives


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "compact-pos-inputs.json"
SCREEN = ROOT / "tau3-fused-screen.json"
OUTPUT = ROOT / "tau3-fused-native-design.json"
TRACE_DIR = ROOT / "tau3-fused-design-traces"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def fields(stdout):
    return dict(item.split("=", 1) for item in stdout.strip().split())


def expected_actions(scalar, order, lattice_lambda, digit, residue, orbit_id, orbit_unit):
    _, a, b = min(representatives(order, lattice_lambda, scalar), key=lambda row: row[0])
    sequence = recode(a, b, digit, residue)
    actions = []
    for offset in range(0, len(sequence), 6):
        padded = (sequence[offset:offset + 6] + [0] * 6)[:6]
        u = block_pattern(padded[:3])
        v = block_pattern(padded[3:])
        index = 55 * u + v
        assert orbit_id[index] < 343 and orbit_unit[index] < 6
        actions.append((orbit_id[index] << 3) | orbit_unit[index])
    return actions


def run(bench):
    fixture = json.loads(FIXTURE.read_text())
    screen = json.loads(SCREEN.read_text())
    design_rows = {row["case_id"]: row for row in screen["rows"]}
    digit, residue, _, orbit_id, orbit_unit, _ = build()
    TRACE_DIR.mkdir(exist_ok=True)
    report = {"schema": 1, "status": "old_data_exact_native_action_match",
              "source_sha256": sha256(Path(__file__).read_bytes()),
              "bench_sha256": sha256(bench.read_bytes()),
              "fixture_sha256": sha256(FIXTURE.read_bytes()),
              "screen_sha256": sha256(SCREEN.read_bytes()),
              "cpu_timing_claim": None, "rows": []}
    for case in fixture["cases"]:
        scalar_path = ROOT / case["scalar_file"]
        raw = scalar_path.read_bytes()
        if sha256(raw) != case["scalar_file_sha256"]:
            raise ValueError(f"old scalar file changed: {case['id']}")
        command = [str(bench), "tau3-fused-pos", case["curve"]["name"],
                   str(case["point_index"]), str(scalar_path)]
        env = os.environ.copy()
        env["CA_TAU3_TRACE_ACTIONS"] = "1"
        process = subprocess.run(command, env=env, text=True, capture_output=True,
                                 timeout=120, check=False)
        if process.returncode:
            raise RuntimeError((case["id"], process.returncode, process.stderr[-1000:]))
        result = fields(process.stdout)
        if (result["verified"] != "1" or
                result["input_digest"] != case["input_digest"] or
                result["output_digest"] != case["expected_output_digest"] or
                result["tau3_checks"] != "4096" or
                result["tau3_action_fallbacks"] != "0" or
                result["fallbacks"] != "0"):
            raise AssertionError((case["id"], result))
        design = design_rows[case["id"]]
        if (int(result["adds"]) != design["predicted_tau3_fused_adds"] or
                int(result["rotations"]) != design["predicted_rotations"]):
            raise AssertionError((case["id"], result, design))
        lattice_lambda = (case["curve"]["order"] - int(result["endo_lambda"])) % case[
            "curve"]["order"]
        trace_lines = process.stderr.splitlines()
        scalars = [word for (word,) in struct.iter_unpack("<Q", raw)]
        if len(trace_lines) != len(scalars) or len(scalars) != 4096:
            raise AssertionError((case["id"], len(trace_lines), len(scalars)))
        for index, (line, scalar) in enumerate(zip(trace_lines, scalars)):
            pieces = line.split(":")
            if pieces[0] != f"tau3_actions={index}":
                raise AssertionError((case["id"], index, line))
            count = int(pieces[1])
            actual = [int(value) for value in pieces[2:]]
            expected = expected_actions(scalar, case["curve"]["order"], lattice_lambda,
                                        digit, residue, orbit_id, orbit_unit)
            if count != len(actual) or actual != expected:
                raise AssertionError((case["id"], index, actual, expected))
        trace_path = TRACE_DIR / f"{case['id']}.txt.gz"
        compressed = gzip.compress(process.stderr.encode(), compresslevel=9, mtime=0)
        if trace_path.exists() and trace_path.read_bytes() != compressed:
            raise ValueError(f"changed native trace: {trace_path}")
        trace_path.write_bytes(compressed)
        report["rows"].append({"case_id": case["id"], "status": process.returncode,
                               "verified": True, "scalars": len(scalars),
                               "input_digest": result["input_digest"],
                               "output_digest": result["output_digest"],
                               "adds": int(result["adds"]),
                               "rotations": int(result["rotations"]),
                               "action_digest": result["tau3_action_digest"],
                               "trace_file": str(trace_path.relative_to(ROOT)),
                               "trace_sha256": sha256(process.stderr.encode()),
                               "trace_gzip_sha256": sha256(compressed),
                               "prep_bytes": int(result["prep_bytes"]),
                               "point_table_bytes": int(result["point_table_bytes"]),
                               "static_map_bytes": int(result["static_map_bytes"]),
                               "prep_triples": int(result["prep_triples"]),
                               "prep_tau_steps": int(result["prep_tau_steps"]),
                               "prep_adds": int(result["prep_adds"]),
                               "prep_layer_inversions": int(result["prep_layer_inversions"]),
                               "prep_verify_points": int(result["tau3_preparation_checks"])})
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "cases": len(report["rows"]),
                      "matched_actions": sum(row["scalars"] for row in report["rows"])},
                     sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    run(args.bench.resolve())
