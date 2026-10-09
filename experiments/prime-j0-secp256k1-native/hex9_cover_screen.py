#!/usr/bin/env python3
"""Independently score the reduced Eisenstein lattice and replay native points."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import affine_from_native, scalar_text
import lazy_tau_screen as curve
from screen_coset_representatives import LAMBDA_TAU, N, U, V, candidates, round_div
from tau6_comb13_sparse_screen import SPARSE_TOP_ORBITS, top_orbit
from tau6_comb_screen import comb_record, digit_stream
from width6_tau_screen import build_width_six_table

HERE = Path(__file__).resolve().parent
W = (U[0] - 2 * V[0], U[1] - 2 * V[1])
SEED = 2026100961
COUNT = 10_000
NATIVE_RANDOM = 256
NATIVE_REPAIRS = 64


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(pair):
    a, b = pair
    return a * a + 3 * a * b + 3 * b * b


def hex_choices(scalar):
    center_w = round_div(scalar * V[1], N)
    center_v = round_div(-scalar * W[1], N)
    rows = []
    for dw in range(-1, 2):
        for dv in range(-1, 2):
            i, j = center_w + dw, center_v + dv
            a = scalar - i * W[0] - j * V[0]
            b = -i * W[1] - j * V[1]
            assert (a + b * LAMBDA_TAU - scalar) % N == 0
            rows.append((norm((a, b)), max(abs(a), abs(b)), a, b))
    return sorted(rows)


def four_corner_norm(scalar):
    floor_w = scalar * V[1] // N
    floor_v = -scalar * W[1] // N
    return min(norm((scalar - i * W[0] - j * V[0], -i * W[1] - j * V[1]))
               for i in (floor_w, floor_w + 1) for j in (floor_v, floor_v + 1))


def score_pair(a, b, table, selected):
    try:
        digits = digit_stream((a, b), table, 162)
    except AssertionError:
        return None
    orbit_id = top_orbit(digits, table)
    repair = orbit_id is not None and orbit_id not in selected
    record = comb_record(digits, 13, 162)
    return {"representative": [a, b], "top_repaired": repair,
            "tau_steps": record["tau_steps"],
            "mixed_additions": record["mixed_additions"] + int(repair),
            "field_product_proxy": record["field_product_proxy"] + 11 * int(repair)}


def score(scalar, table, selected):
    old = candidates(scalar)
    hex_rows = hex_choices(scalar)
    assert len(old) == 25 and len(hex_rows) == 9
    assert norm((old[0][2], old[0][3])) == hex_rows[0][0]
    assert four_corner_norm(scalar) == old[0][0]
    cache = {}

    def evaluate(rows):
        attempts = []
        for rank, row in enumerate(rows):
            pair = (row[2], row[3])
            if pair not in cache:
                cache[pair] = score_pair(*pair, table, selected)
            record = cache[pair]
            if record is not None:
                attempts.append({"rank": rank, **record})
        assert attempts and attempts[0]["rank"] == 0
        return attempts[0], min(attempts, key=lambda item: (item["field_product_proxy"], item["rank"])), len(attempts)

    nearest, cover25, _ = evaluate(old)
    _, hex9, valid = evaluate(hex_rows)
    assert hex9["field_product_proxy"] <= nearest["field_product_proxy"]
    return nearest, cover25, hex9, valid


def check_native(binary, scalars, expected):
    request = "".join(scalar_text(value) + "\n" for value in scalars)
    process = subprocess.run([str(binary), "--scalar-w6-comb13-hex9-fixed"],
                             input=request, text=True, capture_output=True,
                             check=True, timeout=300)
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    for index, (scalar, (winner, valid), row) in enumerate(zip(scalars, expected, rows)):
        assert row["radix"] == "orbit-w6-comb13-hex9-fixed", index
        assert affine_from_native(row["point"]) == curve.point_multiply(scalar % N), index
        assert list(map(int, row["representative"])) == winner["representative"], index
        assert row["tau_steps"] == winner["tau_steps"], index
        assert row["nonzero_digits"] == winner["mixed_additions"], index
        work = row["recoding_work"]
        assert work["top_repaired"] == winner["top_repaired"], index
        assert work["coset_rank"] == winner["rank"], index
        assert work["valid_representatives"] == valid, index
        assert work["attempted_representatives"] == 9, index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "hex9-cover-result.json")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("result exists; refusing overwrite")
    binary = args.binary.resolve(strict=True)
    assert norm(W) == norm(V) == norm((W[0] + V[0], W[1] + V[1])) == N
    source_path = HERE / "tau6-comb13-cover25-result.json"
    source = json.loads(source_path.read_text())
    assert source["status"] == "passed" and source["retained_affine_points"] == 1024
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    selected = set(SPARSE_TOP_ORBITS)
    assert len(selected) == 52

    frozen = Counter()
    frozen_rows = []
    native_scalars = []
    native_expected = []
    for row in source["frozen"]["rows"]:
        scalar = int(row["scalar_hex"], 16)
        nearest, cover25, winner, valid = score(scalar, table, selected)
        assert nearest["field_product_proxy"] == row["nearest_cover_proxy"]
        assert cover25["field_product_proxy"] == row["selected"]["field_product_proxy"]
        frozen.update({"cases": 1, "nearest_cover_proxy": nearest["field_product_proxy"],
                       "cover25_proxy": cover25["field_product_proxy"],
                       "hex9_proxy": winner["field_product_proxy"],
                       "hex9_repairs": int(winner["top_repaired"])})
        frozen_rows.append({"scalar_hex": row["scalar_hex"], "panel": row["panel"],
                            "hex9": winner, "valid_representatives": valid})
        native_scalars.append(scalar)
        native_expected.append((winner, valid))

    deliberate = int(source["deliberate_fallback"]["scalar_hex"], 16)
    deliberate_nearest, deliberate_cover25, deliberate_hex9, deliberate_valid = score(
        deliberate, table, selected)
    native_scalars.append(deliberate)
    native_expected.append((deliberate_hex9, deliberate_valid))

    rng = random.Random(SEED)
    holdout = Counter()
    ranks = Counter()
    repaired_native = 0
    for index in range(COUNT):
        scalar = rng.randrange(N)
        nearest, cover25, winner, valid = score(scalar, table, selected)
        holdout.update({"cases": 1, "nearest_cover_proxy": nearest["field_product_proxy"],
                        "cover25_proxy": cover25["field_product_proxy"],
                        "hex9_proxy": winner["field_product_proxy"],
                        "hex9_repairs": int(winner["top_repaired"]),
                        "hex9_non_nearest": int(winner["rank"] != 0),
                        "valid_representatives": valid})
        ranks[winner["rank"]] += 1
        if index < NATIVE_RANDOM or (winner["top_repaired"] and repaired_native < NATIVE_REPAIRS):
            native_scalars.append(scalar)
            native_expected.append((winner, valid))
            if index >= NATIVE_RANDOM:
                repaired_native += 1
    check_native(binary, native_scalars, native_expected)
    result = {"schema": 1, "status": "passed", "scheme": "reduced-hexagonal-lattice-hex9-cover",
              "retained_affine_points": 1024, "attempted_representatives_per_scalar": 9,
              "basis": {"W": list(map(str, W)), "V": list(map(str, V)),
                        "norm_W": str(norm(W)), "norm_V": str(norm(V)),
                        "norm_W_plus_V": str(norm((W[0] + V[0], W[1] + V[1])))},
              "frozen": {"totals": dict(frozen), "rows": frozen_rows},
              "deliberate_fallback": {"scalar_hex": hex(deliberate),
                                      "nearest_cover": deliberate_nearest,
                                      "cover25": deliberate_cover25,
                                      "hex9": deliberate_hex9,
                                      "valid_representatives": deliberate_valid},
              "disjoint_holdout": {"seed": SEED, **dict(holdout),
                                   "chosen_rank_counts": dict(ranks)},
              "native_verified_cases": len(native_scalars),
              "source_result_sha256": sha(source_path), "source_sha256": sha(Path(__file__)),
              "native_source_sha256": sha(HERE / "src/bin/eisenstein_fixed.rs"),
              "binary_sha256": sha(binary),
              "curve_reference_sha256": sha(HERE / "lazy_tau_screen.py")}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "frozen": result["frozen"]["totals"],
                      "disjoint_holdout": result["disjoint_holdout"],
                      "native_verified_cases": result["native_verified_cases"],
                      "result_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
