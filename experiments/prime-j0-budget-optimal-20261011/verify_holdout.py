#!/usr/bin/env python3
"""Independently check budgeted tau paths and panel disjointness."""

from collections import Counter
from hashlib import sha256
import argparse
import importlib.util
import json
from pathlib import Path
import struct
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "prime-j0-orbit-swap-20261011/verify_holdout.py"
SPEC = importlib.util.spec_from_file_location("tau_bound_verify_parent", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
reference = parent.reference
BASE = ROOT / "prime-j0-phase-optimal-20261011/cover-phase-optimal.bin"
TAU = HERE / "cover-budget-optimal.bin"


def digest(raw):
    return sha256(raw).hexdigest()


def seeds_from_cover(path, expected_count, expected_mask):
    raw = path.read_bytes()
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, expected_count, expected_mask)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    return list(struct.iter_unpack("<hh", raw[offset:]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-root", type=Path, action="append", default=[],
                        help="additional experiments root for sparse checkouts")
    args = parser.parse_args()
    input_raw = (HERE / "holdout-inputs.json").read_bytes()
    inputs = json.loads(input_raw)
    screen = json.loads((HERE / "holdout-screen.json").read_bytes())
    path_raw = (HERE / "holdout-paths.jsonl").read_bytes()
    assert digest(input_raw) == screen["input_sha256"]
    assert digest(path_raw) == screen["certificate_sha256"]
    assert digest(BASE.read_bytes()) == screen["phase_optimal_cover_sha256"]
    assert digest(TAU.read_bytes()) == screen["budget_cover_sha256"] == \
        inputs["cover_sha256"]
    for name, expected in inputs["candidate_source_sha256"].items():
        assert digest((HERE / name).read_bytes()) == expected, name
    scalars = [int(value, 16) for value in inputs["scalars_hex"]]
    assert len(scalars) == inputs["count"] == screen["cases"] == 4096
    assert digest(b"".join(value.to_bytes(32, "big") for value in scalars)) == \
        inputs["scalar_sha256"]
    reduced = {value % reference.N for value in scalars}
    assert len(reduced) == len(scalars)
    roots = [ROOT, *args.prior_root]
    for name, expected in inputs["prior_panel_sha256"].items():
        path = next((root / name for root in roots if (root / name).is_file()), None)
        prior_raw = (path.read_bytes() if path is not None else
                     subprocess.check_output(
                         ["git", "show",
                          f"{inputs['frozen_commit']}:experiments/{name}"],
                         cwd=ROOT.parent))
        assert digest(prior_raw) == expected, name
        prior = {int(value, 16) % reference.N for value in
                 json.loads(prior_raw)["scalars_hex"]}
        assert reduced.isdisjoint(prior), name
    reference.verify_eigenvalue()
    seeds = {"phase_optimal": seeds_from_cover(BASE, 73_417, 7),
             "budget_optimal": seeds_from_cover(TAU, 83_878, 7)}
    lines = path_raw.splitlines()
    assert len(lines) == len(scalars)
    counts = {name: Counter() for name in seeds}
    point_hash = sha256()
    for index, (scalar, line) in enumerate(zip(scalars, lines)):
        entry = json.loads(line)
        assert entry["index"] == index
        for name in seeds:
            path = entry[name]
            if name == "budget_optimal":
                assert all(int(row[3]) < 3 for row in path["digits"])
            rho, nonzero, terminal_norm = parent.check_path(
                path, seeds[name], scalar)
            counts[name]["active_rho"] += rho != 0
            counts[name]["rho_terms"] += rho
            counts[name]["nonzero_full_window"] += nonzero
            counts[name]["tau2_terms"] += sum(
                int(row[2]) != 0 and int(row[3]) == 2
                for row in path["digits"])
            counts[name]["max_terminal_norm"] = max(
                counts[name]["max_terminal_norm"], terminal_norm)
        if index < 128:
            point = reference.group_mul(
                scalar % reference.N, (reference.GX, reference.GY))
            assert point is not None
            for coordinate in point:
                point_hash.update(coordinate.to_bytes(32, "big"))
    assert dict(counts["phase_optimal"]) == screen["phase_optimal"]
    assert dict(counts["budget_optimal"]) == screen["budget_optimal"]
    assert counts["budget_optimal"]["rho_terms"] == 0
    result = {"schema": 1, "status": "passed", "cases": len(lines),
              "phase_optimal": dict(sorted(counts["phase_optimal"].items())),
              "budget_optimal": dict(sorted(counts["budget_optimal"].items())),
              "binary_point_samples": 128,
              "binary_point_stream_sha256": point_hash.hexdigest(),
              "certificate_sha256": digest(path_raw),
              "verifier_sha256": digest(Path(__file__).read_bytes()),
              "reference_sha256": digest(PARENT.read_bytes())}
    (HERE / "holdout-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "passed", "cases": len(lines),
                      "phase_optimal": result["phase_optimal"],
                      "budget_optimal": result["budget_optimal"]}, sort_keys=True))


if __name__ == "__main__":
    main()
