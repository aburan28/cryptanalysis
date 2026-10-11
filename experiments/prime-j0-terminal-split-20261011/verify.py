#!/usr/bin/env python3
"""Independently check split-terminal scalar paths and the frozen input law."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent
REFERENCE = EXPERIMENTS / "prime-j0-carry-aware-v2-20261011/verify_holdout.py"
SPEC = importlib.util.spec_from_file_location("terminal_split_point_reference", REFERENCE)
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)
COVER = EXPERIMENTS / "prime-j0-budget-optimal-20261011/cover-budget-optimal.bin"
TERMINAL = EXPERIMENTS / "prime-j0-fused-orbit-20261011/atlas-r1024-terminal-fused-orbit.bin"
U = (193508920647619669885755136084601127231,
     238911465918039986966665730306072050094)
V = reference.V
W = (U[0] - 2 * V[0], U[1] - 2 * V[1])
METRIC_KEYS = ("point_proxy_units", "terms", "mixed_additions", "bucket_merges",
               "occupied_buckets", "tau1_active", "tau2_active", "grouped_rotations")


def digest(raw):
    return sha256(raw).hexdigest()


def cover_seeds(raw):
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == (b"LP21", 1024, 174_764, 83_878, 7)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    return list(struct.iter_unpack("<hh", raw[offset:]))


def terminal_decode(raw, pair):
    a, b = pair
    magic, bound, low, high, seed_count, pair_count, reserved = struct.unpack_from(
        "<4sHhhIIH", raw)
    assert (magic, bound, reserved) == (b"R103", 149, 0)
    assert low <= b <= high
    row_count = high - low + 1
    a_min, length, offset = struct.unpack_from("<hHI", raw, 20 + 8 * (b - low))
    assert a_min <= a < a_min + length
    code_base = 20 + 8 * row_count
    code = struct.unpack_from("<I", raw, code_base + 4 * (offset + a - a_min))[0]
    seed_id, exponent, unit = code >> 5, (code >> 3) & 3, code & 7
    assert seed_id < seed_count and exponent < 3 and unit < 6
    seeds_base = code_base + 4 * pair_count
    seed = struct.unpack_from("<hh", raw, seeds_base + 4 * seed_id)
    mapped = reference.mapped(seed, exponent)
    assert reference.unit_image(mapped, unit) == pair
    return seed_id, exponent, unit


def path_metrics(option, seeds, terminal_raw, scalar):
    path = option["path"]
    digits = path["digits"]
    assert len(digits) == 12
    terminal = tuple(map(int, path["terminal"]))
    parts = [tuple(map(int, point)) for point in option["terminal_parts"]]
    assert len(parts) in (1, 2)
    assert tuple(map(sum, zip(*parts))) == terminal
    assert all(reference.norm(point) < 149 ** 2 for point in parts)
    if len(parts) == 2:
        assert reference.norm(terminal) >= 149 ** 2
        assert all(point != (0, 0) for point in parts)
        a, b = terminal
        halves = {(x, y) for x in (a // 2, (a + 1) // 2)
                  for y in (b // 2, (b + 1) // 2)}
        assert parts[0] in halves
    else:
        assert parts[0] == terminal
    masks = [0, 0, 0]
    terms = 0
    for point in parts:
        seed_id, exponent, unit = terminal_decode(terminal_raw, point)
        if seed_id:
            terms += 1
            masks[exponent] |= 1 << (unit // 2)
    a, b = terminal
    for row in reversed(digits):
        da, db, seed_id, exponent, unit = map(int, row)
        assert 0 <= seed_id < len(seeds) and 0 <= exponent < 3 and 0 <= unit < 6
        assert (da, db) == reference.unit_image(
            reference.mapped(seeds[seed_id], exponent), unit)
        assert reference.norm((da, db)) <= 1024 ** 2
        if seed_id:
            terms += 1
            masks[exponent] |= 1 << (unit // 2)
        a, b = 1024 * a + da, 1024 * b + db
    representative = tuple(map(int, path["representative"]))
    assert (a, b) == representative
    assert (a + b * reference.LAMBDA - scalar) % reference.N == 0
    occupied = sum(bool(mask) for mask in masks)
    rotations = sum(mask.bit_count() - 1 + (0 if mask & 1 else 1)
                    for mask in masks if mask)
    mixed = terms - occupied
    merges = max(occupied - 1, 0)
    cost = 11 * mixed + 14 * merges + 6 * int(bool(masks[1])) + \
        10 * int(bool(masks[2])) + rotations
    expected = {"point_proxy_units": cost, "terms": terms,
                "mixed_additions": mixed, "bucket_merges": merges,
                "occupied_buckets": occupied,
                "tau1_active": int(bool(masks[1])),
                "tau2_active": int(bool(masks[2])),
                "grouped_rotations": rotations, "unit_masks": masks}
    assert option["metrics"] == expected
    return expected


def candidate_corners(scalar):
    scalar %= reference.N
    low_i = scalar * V[1] // reference.N
    low_j = -(scalar * W[1]) // reference.N
    corners = {
        (scalar - i * W[0] - j * V[0], -i * W[1] - j * V[1])
        for i in (low_i, low_i + 1) for j in (low_j, low_j + 1)
    }
    assert len(corners) == 4
    baseline = min(corners, key=lambda p: (reference.norm(p),
                                             max(abs(p[0]), abs(p[1])), p[0], p[1]))
    return corners, baseline


def rank(option, baseline):
    rep = tuple(option["path"]["representative"])
    parts = tuple(tuple(point) for point in option["terminal_parts"])
    return (option["metrics"]["point_proxy_units"], len(parts),
            int(rep != baseline), reference.norm(rep), rep, parts)


def main():
    input_raw = (HERE / "holdout-inputs.json").read_bytes()
    path_raw = (HERE / "holdout-paths.jsonl").read_bytes()
    inputs = json.loads(input_raw)
    screen = json.loads((HERE / "holdout-screen.json").read_bytes())
    assert digest(input_raw) == screen["input_sha256"]
    assert digest(path_raw) == screen["certificate_sha256"]
    cover_raw = COVER.read_bytes()
    terminal_raw = TERMINAL.read_bytes()
    assert digest(cover_raw) == inputs["cover_sha256"] == screen["cover_sha256"]
    assert digest(terminal_raw) == inputs["terminal_sha256"] == screen["terminal_sha256"]
    for name, expected in inputs["candidate_source_sha256"].items():
        assert digest((HERE / name).read_bytes()) == expected, name
    assert screen["source_sha256"] == digest((HERE / "replay.py").read_bytes())
    scalars = [int(value, 16) for value in inputs["scalars_hex"]]
    assert len(scalars) == inputs["count"] == screen["cases"] == 4096
    assert digest(b"".join(value.to_bytes(32, "big") for value in scalars)) == \
        inputs["scalar_sha256"]
    reduced = {value % reference.N for value in scalars}
    assert len(reduced) == len(scalars)
    for name, expected in inputs["prior_panel_sha256"].items():
        prior_raw = (EXPERIMENTS / name).read_bytes()
        assert digest(prior_raw) == expected
        prior = {int(value, 16) % reference.N for value in
                 json.loads(prior_raw)["scalars_hex"]}
        assert reduced.isdisjoint(prior), name
    reference.verify_eigenvalue()
    seeds = cover_seeds(cover_raw)
    lines = path_raw.splitlines()
    assert len(lines) == len(scalars)
    totals = {"baseline": Counter(), "selected": Counter()}
    changed = improved = selected_split = 0
    point_hash = sha256()
    for index, (scalar, line) in enumerate(zip(scalars, lines)):
        record = json.loads(line)
        assert record["index"] == index and record["baseline_option"] == 0
        assert record["recode_attempts"] == 4
        options = record["options"]
        assert options and 0 <= record["selected_option"] < len(options)
        corners, baseline_rep = candidate_corners(scalar)
        assert tuple(options[0]["path"]["representative"]) == baseline_rep
        assert all(tuple(option["path"]["representative"]) in corners
                   for option in options)
        for option in options:
            path_metrics(option, seeds, terminal_raw, scalar)
        chosen = min(range(len(options)), key=lambda i: rank(options[i], baseline_rep))
        assert record["selected_option"] == chosen
        baseline, selected = options[0], options[chosen]
        for name, option in (("baseline", baseline), ("selected", selected)):
            totals[name].update({key: option["metrics"][key] for key in METRIC_KEYS})
        selected_split += len(selected["terminal_parts"]) == 2
        changed += chosen != 0
        improved += selected["metrics"]["point_proxy_units"] < baseline["metrics"]["point_proxy_units"]
        if index < 128:
            expected = reference.group_mul(scalar % reference.N,
                                           (reference.GX, reference.GY))
            assert expected is not None
            for coordinate in expected:
                point_hash.update(coordinate.to_bytes(32, "big"))
    assert screen["recode_attempts"] == 4 * len(lines)
    assert (screen["selected_split"], screen["selected_changed"],
            screen["point_proxy_improved"]) == (selected_split, changed, improved)
    for name in totals:
        assert screen[name] == dict(totals[name]), name
    result = {"schema": 1, "status": "passed", "cases": len(lines),
              "selected_split": selected_split, "selected_changed": changed,
              "point_proxy_improved": improved,
              "baseline": dict(sorted(totals["baseline"].items())),
              "selected": dict(sorted(totals["selected"].items())),
              "binary_point_samples": 128,
              "binary_point_stream_sha256": point_hash.hexdigest(),
              "certificate_sha256": digest(path_raw),
              "verifier_sha256": digest(Path(__file__).read_bytes()),
              "reference_sha256": digest(REFERENCE.read_bytes())}
    output = HERE / "holdout-check.json"
    if output.exists():
        raise SystemExit("refusing to overwrite independent verification")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "cases", "selected_split", "point_proxy_improved",
                       "baseline", "selected")}, sort_keys=True))


if __name__ == "__main__":
    main()
