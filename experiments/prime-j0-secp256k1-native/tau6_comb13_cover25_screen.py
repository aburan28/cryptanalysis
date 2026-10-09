#!/usr/bin/env python3
"""Replay fixed-width 25-coset tau comb against independent secp256k1 points."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import affine_from_native, scalar_text
import lazy_tau_screen as curve
from screen_coset_representatives import candidates
from tau6_comb13_sparse_screen import SPARSE_TOP_ORBITS, top_orbit
from tau6_comb_screen import comb_record, digit_stream
from width6_tau_screen import build_width_six_table

HERE = Path(__file__).resolve().parent
SEED = 2026100945
COUNT = 10_000
NATIVE_RANDOM = 256
NATIVE_REPAIRS = 64


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(scalar, table, selected):
    attempts = []
    for rank, (_, _, a, b, _, _) in enumerate(candidates(scalar)):
        try:
            digits = digit_stream((a, b), table, 162)
        except AssertionError:
            continue
        orbit_id = top_orbit(digits, table)
        repair = orbit_id is not None and orbit_id not in selected
        record = comb_record(digits, 13, 162)
        attempts.append({"rank": rank, "representative": [a, b],
                         "top_repaired": repair, "tau_steps": record["tau_steps"],
                         "mixed_additions": record["mixed_additions"] + int(repair),
                         "field_product_proxy": record["field_product_proxy"] + 11 * int(repair)})
    assert attempts and attempts[0]["rank"] == 0
    winner = min(attempts, key=lambda row: (row["field_product_proxy"], row["rank"]))
    assert winner["field_product_proxy"] <= attempts[0]["field_product_proxy"]
    return attempts[0], winner, len(attempts)


def check_native(binary, scalars, expected):
    request = "".join(scalar_text(value) + "\n" for value in scalars)
    process = subprocess.run([str(binary), "--scalar-w6-comb13-cover25-fixed"],
                             input=request, text=True, capture_output=True,
                             check=True, timeout=300)
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    for index, (scalar, (winner, valid), row) in enumerate(zip(scalars, expected, rows)):
        assert row["radix"] == "orbit-w6-comb13-cover25-fixed", index
        assert affine_from_native(row["point"]) == curve.point_multiply(scalar % curve.ORDER), index
        assert list(map(int, row["representative"])) == winner["representative"], index
        assert row["tau_steps"] == winner["tau_steps"], index
        assert row["nonzero_digits"] == winner["mixed_additions"], index
        work = row["recoding_work"]
        assert work["top_repaired"] == winner["top_repaired"], index
        assert work["coset_rank"] == winner["rank"], index
        assert work["valid_representatives"] == valid, index
        assert work["attempted_representatives"] == 25, index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "tau6-comb13-cover25-result.json")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("result exists; refusing overwrite")
    binary = args.binary.resolve(strict=True)
    previous = HERE / "tau6-comb13-cover-result.json"
    source = json.loads(previous.read_text())
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
        baseline, winner, valid = score(scalar, table, selected)
        assert baseline["field_product_proxy"] == row["cover_proxy"]
        frozen.update({"cases": 1, "nearest_cover_proxy": baseline["field_product_proxy"],
                       "cover25_proxy": winner["field_product_proxy"],
                       "selected_non_nearest": int(winner["rank"] != 0),
                       "selected_repairs": int(winner["top_repaired"])})
        frozen_rows.append({"scalar_hex": row["scalar_hex"], "panel": row["panel"],
                            "nearest_cover_proxy": baseline["field_product_proxy"],
                            "selected": winner, "valid_representatives": valid})
        native_scalars.append(scalar)
        native_expected.append((winner, valid))

    deliberate = int(source["deliberate_fallback"]["scalar_hex"], 16)
    deliberate_base, deliberate_winner, deliberate_valid = score(deliberate, table, selected)
    assert deliberate_base["top_repaired"]
    native_scalars.append(deliberate)
    native_expected.append((deliberate_winner, deliberate_valid))

    rng = random.Random(SEED)
    holdout = Counter()
    rank_counts = Counter()
    repaired_native = 0
    for index in range(COUNT):
        scalar = rng.randrange(curve.ORDER)
        baseline, winner, valid = score(scalar, table, selected)
        holdout.update({"cases": 1, "nearest_cover_proxy": baseline["field_product_proxy"],
                        "cover25_proxy": winner["field_product_proxy"],
                        "selected_repairs": int(winner["top_repaired"]),
                        "selected_non_nearest": int(winner["rank"] != 0),
                        "valid_representatives": valid})
        rank_counts[winner["rank"]] += 1
        if index < NATIVE_RANDOM or (winner["top_repaired"] and repaired_native < NATIVE_REPAIRS):
            native_scalars.append(scalar)
            native_expected.append((winner, valid))
            if winner["top_repaired"] and index >= NATIVE_RANDOM:
                repaired_native += 1
    check_native(binary, native_scalars, native_expected)
    result = {"schema": 1, "status": "passed",
              "algorithm": "fixed-width-25-coset-additive-cover-tau13",
              "curve": "secp256k1", "retained_affine_points": 1024,
              "attempted_representatives_per_scalar": 25,
              "selection_metric": "5*tau_steps + 11*mixed_additions including top repair",
              "frozen": {"cases": len(frozen_rows), "totals": dict(frozen), "rows": frozen_rows},
              "deliberate_fallback": {"scalar_hex": hex(deliberate),
                                      "nearest_cover": deliberate_base,
                                      "selected": deliberate_winner,
                                      "valid_representatives": deliberate_valid},
              "disjoint_holdout": {"seed": SEED, **dict(holdout),
                                   "chosen_rank_counts": dict(rank_counts)},
              "native_verified_cases": len(native_scalars),
              "source_result_sha256": sha(previous),
              "source_sha256": sha(Path(__file__)),
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
