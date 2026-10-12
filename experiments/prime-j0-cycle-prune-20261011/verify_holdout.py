#!/usr/bin/env python3
"""Independently verify each scalar path, disjointness, and binary points."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "prime-j0-orbit-swap-20261011/verify_holdout.py"
SPEC = importlib.util.spec_from_file_location("cycle_holdout_reference", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
reference = parent.reference
INPUTS = HERE / "holdout-inputs.json"
BASE = ROOT / "prime-j0-orbit-swap-20261011/cover-swapped-rho0.bin"
NEW = HERE / "cover-cycle-refined.bin"

INPUT_SOURCE = HERE / "make_inputs.py"
INPUT_SPEC = importlib.util.spec_from_file_location("cycle_holdout_input_source", INPUT_SOURCE)
input_source = importlib.util.module_from_spec(INPUT_SPEC)
INPUT_SPEC.loader.exec_module(input_source)


def digest(raw):
    return sha256(raw).hexdigest()


def read_seeds(path):
    raw = path.read_bytes()
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, 67_338, 15)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    return raw, list(struct.iter_unpack("<hh", raw[offset:]))


def main():
    input_raw = INPUTS.read_bytes()
    inputs = json.loads(input_raw)
    screen = json.loads((HERE / "holdout-screen.json").read_bytes())
    path_raw = (HERE / "holdout-paths.jsonl").read_bytes()
    assert digest(input_raw) == screen["input_sha256"]
    assert digest(path_raw) == screen["certificate_sha256"]
    base_raw, base_seeds = read_seeds(BASE)
    new_raw, new_seeds = read_seeds(NEW)
    assert digest(base_raw) == screen["swapped_cover_sha256"]
    assert digest(new_raw) == screen["refined_cover_sha256"] == \
        inputs["cover_sha256"]
    for name, expected in inputs["candidate_source_sha256"].items():
        assert digest((HERE / name).read_bytes()) == expected, name
    scalars = [int(value, 16) for value in inputs["scalars_hex"]]
    assert len(scalars) == inputs["count"] == screen["cases"] == 4096
    assert digest(b"".join(value.to_bytes(32, "big") for value in scalars)) == \
        inputs["scalar_sha256"]
    reduced = {value % reference.N for value in scalars}
    assert len(reduced) == len(scalars)
    for name, expected in inputs["prior_panel_sha256"].items():
        prior_raw = input_source.prior_bytes(name)
        assert digest(prior_raw) == expected, name
        prior = {int(value, 16) % reference.N for value in
                 json.loads(prior_raw)["scalars_hex"]}
        assert reduced.isdisjoint(prior), name
    reference.verify_eigenvalue()
    seeds = {"swapped": base_seeds, "refined": new_seeds}
    lines = path_raw.splitlines()
    assert len(lines) == len(scalars)
    counts = {name: Counter() for name in seeds}
    improvements = regressions = ties = 0
    point_hash = sha256()
    for index, (scalar, line) in enumerate(zip(scalars, lines)):
        entry = json.loads(line)
        assert entry["index"] == index
        rho = {}
        for name in seeds:
            path = entry[name]
            rho[name], nonzero, terminal_norm = parent.check_path(
                path, seeds[name], scalar)
            counts[name]["active_rho"] += rho[name] != 0
            counts[name]["rho_terms"] += rho[name]
            counts[name]["nonzero_full_window"] += nonzero
            counts[name]["tau2_terms"] += sum(
                int(row[2]) != 0 and int(row[3]) == 2
                for row in path["digits"])
            counts[name]["max_terminal_norm"] = max(
                counts[name]["max_terminal_norm"], terminal_norm)
        improvements += rho["swapped"] > 0 and rho["refined"] == 0
        regressions += rho["swapped"] == 0 and rho["refined"] > 0
        ties += (rho["swapped"] > 0) == (rho["refined"] > 0)
        if index < 128:
            point = reference.group_mul(
                scalar % reference.N, (reference.GX, reference.GY))
            assert point is not None
            for coordinate in point:
                point_hash.update(coordinate.to_bytes(32, "big"))
    assert dict(counts["swapped"]) == screen["swapped"]
    assert dict(counts["refined"]) == screen["refined"]
    assert (improvements, regressions, ties) == \
        (screen["paired_activation_improvements"],
         screen["paired_activation_regressions"],
         screen["paired_activation_ties"])
    result = {"schema": 1, "status": "passed", "cases": len(lines),
              "swapped": dict(sorted(counts["swapped"].items())),
              "refined": dict(sorted(counts["refined"].items())),
              "paired_activation_improvements": improvements,
              "paired_activation_regressions": regressions,
              "binary_point_samples": 128,
              "binary_point_stream_sha256": point_hash.hexdigest(),
              "certificate_sha256": digest(path_raw),
              "verifier_sha256": digest(Path(__file__).read_bytes()),
              "reference_sha256": digest(PARENT.read_bytes())}
    (HERE / "holdout-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
