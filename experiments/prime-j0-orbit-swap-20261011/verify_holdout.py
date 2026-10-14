#!/usr/bin/env python3
"""Independently check every swapped digit path and the held-out input law."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REFERENCE = ROOT / "prime-j0-carry-aware-v2-20261011/verify_holdout.py"
SPEC = importlib.util.spec_from_file_location("orbit_swap_reference", REFERENCE)
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)
OLD = ROOT / "prime-j0-dual-orbit-20261011/cover-priority-rho0.bin"
NEW = HERE / "cover-swapped-rho0.bin"


def digest(raw):
    return sha256(raw).hexdigest()


def seeds_from_cover(path):
    raw = path.read_bytes()
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", 1024, 174_764, 67_338, 15)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    return list(struct.iter_unpack("<hh", raw[offset:]))


def check_path(path, seeds, scalar):
    assert len(path["digits"]) == 12
    a, b = map(int, path["terminal"])
    terminal_norm = reference.norm((a, b))
    assert terminal_norm < reference.BOUND ** 2
    rho_terms = 0
    nonzero = 0
    for row in reversed(path["digits"]):
        da, db, seed_id, map_id, unit = map(int, row)
        assert 0 <= seed_id < len(seeds) and 0 <= map_id < 4
        assert 0 <= unit < 6
        assert (da, db) == reference.unit_image(
            reference.mapped(seeds[seed_id], map_id), unit)
        assert reference.norm((da, db)) <= reference.RADIX ** 2
        a, b = reference.RADIX * a + da, reference.RADIX * b + db
        rho_terms += seed_id != 0 and map_id == 3
        nonzero += seed_id != 0
    assert (a + b * reference.LAMBDA - scalar) % reference.N == 0
    assert rho_terms == path["rho_terms"]
    return rho_terms, nonzero, terminal_norm


def main():
    input_raw = (HERE / "holdout-inputs.json").read_bytes()
    inputs = json.loads(input_raw)
    screen_raw = (HERE / "holdout-screen.json").read_bytes()
    screen = json.loads(screen_raw)
    path_raw = (HERE / "holdout-paths.jsonl").read_bytes()
    assert digest(input_raw) == screen["input_sha256"]
    assert digest(path_raw) == screen["certificate_sha256"]
    assert digest(OLD.read_bytes()) == screen["priority_cover_sha256"]
    assert digest(NEW.read_bytes()) == screen["swapped_cover_sha256"]
    assert digest(NEW.read_bytes()) == inputs["cover_sha256"]
    assert inputs["candidate_source_sha256"]["replay_holdout.py"] == \
        screen["source_sha256"]
    for name, expected in inputs["candidate_source_sha256"].items():
        assert digest((HERE / name).read_bytes()) == expected, name
    scalars = [int(value, 16) for value in inputs["scalars_hex"]]
    assert len(scalars) == inputs["count"] == screen["cases"] == 4096
    assert digest(b"".join(value.to_bytes(32, "big") for value in scalars)) == \
        inputs["scalar_sha256"]
    reduced = {value % reference.N for value in scalars}
    assert len(reduced) == len(scalars)
    for name, expected in inputs["prior_panel_sha256"].items():
        prior_raw = (ROOT / name).read_bytes()
        assert digest(prior_raw) == expected, name
        prior = {int(value, 16) % reference.N for value in
                 json.loads(prior_raw)["scalars_hex"]}
        assert reduced.isdisjoint(prior), name
    reference.verify_eigenvalue()
    seeds = {"priority": seeds_from_cover(OLD),
             "swapped": seeds_from_cover(NEW)}
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
            rho[name], nonzero, terminal_norm = check_path(
                entry[name], seeds[name], scalar)
            counts[name]["active_rho"] += rho[name] != 0
            counts[name]["rho_terms"] += rho[name]
            counts[name]["nonzero_full_window"] += nonzero
            counts[name]["max_terminal_norm"] = max(
                counts[name]["max_terminal_norm"], terminal_norm)
        improvements += rho["priority"] > 0 and rho["swapped"] == 0
        regressions += rho["priority"] == 0 and rho["swapped"] > 0
        ties += (rho["priority"] > 0) == (rho["swapped"] > 0)
        if index < 128:
            point = reference.group_mul(
                scalar % reference.N, (reference.GX, reference.GY))
            assert point is not None
            for coordinate in point:
                point_hash.update(coordinate.to_bytes(32, "big"))
    assert dict(counts["priority"]) == screen["priority"]
    assert dict(counts["swapped"]) == screen["swapped"]
    assert (improvements, regressions, ties) == \
        (screen["paired_activation_improvements"],
         screen["paired_activation_regressions"],
         screen["paired_activation_ties"])
    result = {"schema": 1, "status": "passed", "cases": len(lines),
              "priority": dict(sorted(counts["priority"].items())),
              "swapped": dict(sorted(counts["swapped"].items())),
              "paired_activation_improvements": improvements,
              "paired_activation_regressions": regressions,
              "binary_point_samples": 128,
              "binary_point_stream_sha256": point_hash.hexdigest(),
              "certificate_sha256": digest(path_raw),
              "verifier_sha256": digest(Path(__file__).read_bytes()),
              "reference_sha256": digest(REFERENCE.read_bytes())}
    (HERE / "holdout-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
