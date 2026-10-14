#!/usr/bin/env python3
"""Independently replay doubled-map paths and 128 secp256k1 points."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / "prime-j0-cycle-compression-20261011"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reference_path = ROOT / "prime-j0-carry-aware-v2-20261011/verify_holdout.py"
reference = load("doubled_holdout_curve_reference", reference_path)
independent_path = ROOT / "prime-j0-dual-orbit-20261011/verify_cover.py"
independent = load("doubled_holdout_orbit_reference", independent_path)
inputs_source = load("doubled_holdout_input_reference",
                     ROOT / "prime-j0-cycle-prune-20261011/make_inputs.py")


def digest(raw):
    return sha256(raw).hexdigest()


def cover(raw, mask):
    magic, radix, classes, count, actual_mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, actual_mask) == \
        (b"LP21", 1024, 174_764, 67_338, mask)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    codes = struct.unpack_from(f"<{classes}I", raw, 20)
    seeds = list(struct.iter_unpack("<hh", raw[offset:]))
    return codes, seeds


def check_path(path, codes, seeds, scalar, canonical, node_index):
    assert len(path["digits"]) == 12
    a, b = map(int, path["terminal"])
    terminal_norm = reference.norm((a, b))
    assert terminal_norm < reference.BOUND ** 2
    rho = doubled = nonzero = 0
    for row in reversed(path["digits"]):
        da, db, seed_id, map_id, unit = map(int, row)
        assert 0 <= seed_id < len(seeds) and 0 <= map_id <= 4
        assert 0 <= unit < 6
        pair = seeds[seed_id]
        mapped = (pair[0] + pair[0], pair[1] + pair[1]) \
            if map_id == 4 else reference.mapped(pair, map_id)
        assert (da, db) == reference.unit_image(mapped, unit)
        assert reference.norm((da, db)) <= reference.RADIX ** 2
        a, b = reference.RADIX * a + da, reference.RADIX * b + db
        rho += int(seed_id != 0 and map_id == 3)
        doubled += int(seed_id != 0 and map_id == 4)
        nonzero += int(seed_id != 0)
    assert (a + b * reference.LAMBDA - scalar) % reference.N == 0
    for row in path["digits"]:
        da, db, seed_id, map_id, _ = map(int, row)
        ra, rb = a % 1024, b % 1024
        target = node_index[canonical[ra * 1024 + rb]]
        code = codes[target]
        assert (seed_id, map_id) == (code >> 4, code & 15)
        assert (da % 1024, db % 1024) == (ra, rb)
        a, b = (a - da) // 1024, (b - db) // 1024
    assert [a, b] == path["terminal"]
    assert (rho, doubled) == (path["rho_terms"], path["double_terms"])
    return rho, doubled, nonzero, terminal_norm


def signed_mul(k, point):
    result = reference.group_mul(abs(k), point)
    if k < 0 and result is not None:
        return result[0], (-result[1]) % reference.P
    return result


def point_from_path(path, bases, tau_bases):
    total = None
    pairs = [(int(row[0]), int(row[1])) for row in path["digits"]]
    pairs.append(tuple(map(int, path["terminal"])))
    assert len(pairs) == 13
    for index, (a, b) in enumerate(pairs):
        term = reference.group_add(signed_mul(a, bases[index]),
                                   signed_mul(b, tau_bases[index]))
        total = reference.group_add(total, term)
    return total


def add_counts(counts, rho, doubled, nonzero, terminal_norm):
    counts["active_rho"] += int(rho != 0)
    counts["active_double"] += int(doubled != 0)
    counts["rho_terms"] += rho
    counts["double_terms"] += doubled
    counts["nonzero_full_window"] += nonzero
    counts["max_terminal_norm"] = max(
        counts["max_terminal_norm"], terminal_norm)


def main():
    input_raw = (HERE / "holdout-inputs.json").read_bytes()
    screen_raw = (HERE / "holdout-screen.json").read_bytes()
    path_raw = (HERE / "holdout-paths.jsonl").read_bytes()
    inputs, screen = json.loads(input_raw), json.loads(screen_raw)
    assert digest(input_raw) == screen["input_sha256"]
    assert digest(path_raw) == screen["certificate_sha256"]
    for name, expected in inputs["candidate_source_sha256"].items():
        assert digest((HERE / name).read_bytes()) == expected, name
    old_raw = (BASE / "cover-cycle-compressed.bin").read_bytes()
    new_raw = (HERE / "cover-doubled.bin").read_bytes()
    assert digest(old_raw) == screen["parent_cover_sha256"]
    assert digest(new_raw) == screen["cover_sha256"] == inputs["cover_sha256"]
    old_codes, old_seeds = cover(old_raw, 15)
    new_codes, new_seeds = cover(new_raw, 31)
    assert old_seeds == new_seeds
    scalars = [int(value, 16) for value in inputs["scalars_hex"]]
    assert len(scalars) == inputs["count"] == screen["cases"] == 4_096
    assert digest(b"".join(value.to_bytes(32, "big") for value in scalars)) == \
        inputs["scalar_sha256"]
    reduced = {value % reference.N for value in scalars}
    assert len(reduced) == len(scalars)
    for name, expected in inputs["prior_panel_sha256"].items():
        raw = inputs_source.prior_bytes(name)
        assert digest(raw) == expected, name
        assert reduced.isdisjoint(int(value, 16) % reference.N for value in
                                  json.loads(raw)["scalars_hex"]), name
    reference.verify_eigenvalue()
    canonical, nodes = independent.orbit_partition()
    node_index = {node: index for index, node in enumerate(nodes)}
    generator = (reference.GX, reference.GY)
    tau_generator = reference.group_mul(reference.LAMBDA, generator)
    bases, tau_bases = [generator], [tau_generator]
    for _ in range(12):
        bases.append(reference.group_mul(1024, bases[-1]))
        tau_bases.append(reference.group_mul(1024, tau_bases[-1]))
    lines = path_raw.splitlines()
    assert len(lines) == len(scalars)
    totals = {name: Counter() for name in ("parent", "doubled", "adaptive")}
    selection = Counter()
    point_hash = sha256()
    for index, (scalar, line) in enumerate(zip(scalars, lines)):
        entry = json.loads(line)
        assert entry["index"] == index
        old = entry["parent"]
        new = entry["doubled"]
        expected_choice = "parent" if new["rho_terms"] and new["double_terms"] \
            else "doubled"
        assert entry["adaptive"] == expected_choice
        selection[expected_choice] += 1
        checked = {}
        for name, path, codes, seeds in (
                ("parent", old, old_codes, old_seeds),
                ("doubled", new, new_codes, new_seeds),
                ("adaptive", entry[expected_choice],
                 old_codes if expected_choice == "parent" else new_codes,
                 old_seeds if expected_choice == "parent" else new_seeds)):
            checked[name] = check_path(
                path, codes, seeds, scalar, canonical, node_index)
            add_counts(totals[name], *checked[name])
        if index < 128:
            point = reference.group_mul(scalar % reference.N, generator)
            assert point is not None
            assert point_from_path(old, bases, tau_bases) == point
            assert point_from_path(new, bases, tau_bases) == point
            for coordinate in point:
                point_hash.update(coordinate.to_bytes(32, "big"))
    assert {name: dict(value) for name, value in totals.items()} == screen["counts"]
    assert dict(selection) == screen["adaptive_selection"]
    result = {"schema": 1, "status": "passed", "cases": len(lines),
              "source_sha256": digest(Path(__file__).read_bytes()),
              "reference_sha256": digest(reference_path.read_bytes()),
              "orbit_reference_sha256": digest(independent_path.read_bytes()),
              "input_sha256": digest(input_raw),
              "cover_sha256": digest(new_raw),
              "certificate_sha256": digest(path_raw),
              "screen_sha256": digest(screen_raw),
              "counts": screen["counts"],
              "adaptive_selection": dict(selection),
              "binary_point_cases": 128,
              "binary_point_stream_sha256": point_hash.hexdigest()}
    (HERE / "holdout-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
