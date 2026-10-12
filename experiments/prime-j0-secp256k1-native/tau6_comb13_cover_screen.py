#!/usr/bin/env python3
"""Verify an additive two-sum cover for omitted sparse tau13 top digits."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import affine_from_native, scalar_text
import lazy_tau_screen as curve
from redundant_tau4_screen import orbit
from screen_coset_representatives import candidates
from tau6_comb13_sparse_screen import SPARSE_TOP_ORBITS, top_orbit
from tau6_comb_screen import comb_record, digit_stream
from width6_tau_screen import build_width_six_table


HERE = Path(__file__).resolve().parent
HOLDOUT_SEED = 2026100932
HOLDOUT_COUNT = 100_000
NATIVE_RANDOM = 256


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def additive_cover(seeds, selected):
    images = [(orbit_id, power, sign, value)
              for orbit_id in selected
              for power, pair in enumerate(orbit(seeds[orbit_id])[::2])
              for sign, value in ((1, pair), (-1, (-pair[0], -pair[1])))]
    pairs = {}
    for left in images:
        for right in images:
            digit = (left[3][0] + right[3][0], left[3][1] + right[3][1])
            rank = (left[1] + right[1], left[:3], right[:3])
            if digit not in pairs or rank < pairs[digit][0]:
                pairs[digit] = (rank, left[:3], right[:3])
    missing = [(orbit_id, digit) for orbit_id, seed in enumerate(seeds)
               if orbit_id not in selected for digit in orbit(seed)]
    assert len(missing) == 174
    assert all(digit in pairs for _, digit in missing)
    for orbit_id, digit in missing:
        _, left, right = pairs[digit]
        assert left[0] in selected and right[0] in selected
    return {"missing_orbits": 29, "covered_digit_images": len(missing),
            "selected_top_orbits": len(selected)}


def score(digits, table, selected):
    orbit_id = top_orbit(digits, table)
    repair = orbit_id is not None and orbit_id not in selected
    fast = comb_record(digits, 13, 162)
    baseline = comb_record(digits, 1, 162) if repair else fast
    covered = {"tau_steps": fast["tau_steps"],
               "mixed_additions": fast["mixed_additions"] + int(repair),
               "field_product_proxy": fast["field_product_proxy"] + 11 * int(repair),
               "top_repaired": repair}
    return baseline, covered


def check_native(binary, scalars, expected):
    request = "".join(scalar_text(value) + "\n" for value in scalars)
    process = subprocess.run([str(binary), "--scalar-w6-comb13-cover-fixed"],
                             input=request, text=True, capture_output=True,
                             check=True, timeout=180)
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    for index, (scalar, answer, row) in enumerate(zip(scalars, expected, rows)):
        assert row["radix"] == "orbit-w6-comb13-cover-fixed", index
        assert affine_from_native(row["point"]) == curve.point_multiply(
            scalar % curve.ORDER), index
        assert row["tau_steps"] == answer["tau_steps"], index
        assert row["nonzero_digits"] == answer["mixed_additions"], index
        assert row["recoding_work"]["top_repaired"] == answer["top_repaired"], index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        default=HERE / "tau6-comb13-cover-result.json")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("result exists; refusing overwrite")
    binary = args.binary.resolve(strict=True)
    source_path = HERE / "tau6-comb13-sparse-result.json"
    source = json.loads(source_path.read_text())
    assert source["schema"] == 1 and source["status"] == "passed"
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    selected = set(SPARSE_TOP_ORBITS)
    assert selected == set(source["top_row_orbits"])
    cover_proof = additive_cover(seeds, selected)

    panels = {name: Counter() for name in
              ("frozen_edges", "frozen_random", "holdout_random")}
    frozen_rows = []
    native_scalars = []
    native_expected = []
    for row in source["frozen"]["rows"]:
        scalar = int(row["scalar_hex"], 16)
        digits = digit_stream(tuple(row["representative"]), table, 162)
        baseline, covered = score(digits, table, selected)
        assert baseline["field_product_proxy"] == row["field_product_proxy"]
        assert baseline["tau_steps"] == row["tau_steps"]
        assert row["fallback"] == covered["top_repaired"]
        panels[row["panel"]].update({"cases": 1,
                                     "baseline_proxy": baseline["field_product_proxy"],
                                     "cover_proxy": covered["field_product_proxy"],
                                     "top_repairs": int(covered["top_repaired"])})
        frozen_rows.append({"index": row["index"], "panel": row["panel"],
                            "scalar_hex": row["scalar_hex"],
                            "baseline_proxy": baseline["field_product_proxy"],
                            "cover_proxy": covered["field_product_proxy"],
                            "top_repaired": covered["top_repaired"]})
        native_scalars.append(scalar)
        native_expected.append(covered)

    miss = int(source["deliberate_fallback"]["scalar_hex"], 16)
    miss_digits = digit_stream(candidates(miss)[0][2:4], table, 162)
    miss_baseline, miss_cover = score(miss_digits, table, selected)
    assert miss_cover["top_repaired"]
    native_scalars.append(miss)
    native_expected.append(miss_cover)

    rng = random.Random(HOLDOUT_SEED)
    holdout = Counter()
    for index in range(HOLDOUT_COUNT):
        scalar = rng.randrange(curve.ORDER)
        digits = digit_stream(candidates(scalar)[0][2:4], table, 162)
        baseline, covered = score(digits, table, selected)
        holdout.update({"cases": 1,
                        "baseline_proxy": baseline["field_product_proxy"],
                        "cover_proxy": covered["field_product_proxy"],
                        "top_repairs": int(covered["top_repaired"])})
        if index < NATIVE_RANDOM or covered["top_repaired"]:
            native_scalars.append(scalar)
            native_expected.append(covered)
    check_native(binary, native_scalars, native_expected)
    result = {
        "schema": 1,
        "status": "passed",
        "algorithm": "additive-two-sum-terminal-cover-tau13",
        "curve": "secp256k1",
        "retained_affine_points": 1024,
        "cover_proof": cover_proof,
        "frozen": {"cases": len(frozen_rows),
                   "panels": {name: dict(counts) for name, counts in panels.items()},
                   "rows": frozen_rows},
        "deliberate_fallback": {"scalar_hex": hex(miss),
                                "baseline": {"tau_steps": miss_baseline["tau_steps"],
                                             "mixed_additions": miss_baseline["mixed_additions"],
                                             "field_product_proxy": miss_baseline["field_product_proxy"]},
                                "cover": miss_cover},
        "disjoint_holdout": {"seed": HOLDOUT_SEED, **dict(holdout)},
        "native_verified_cases": len(native_scalars),
        "source_result_sha256": sha(source_path),
        "source_sha256": sha(Path(__file__)),
        "native_source_sha256": sha(HERE / "src/bin/eisenstein_fixed.rs"),
        "binary_sha256": sha(binary),
        "curve_reference_sha256": sha(HERE / "lazy_tau_screen.py"),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "cover_proof": cover_proof,
                      "disjoint_holdout": result["disjoint_holdout"],
                      "deliberate_fallback": result["deliberate_fallback"],
                      "native_verified_cases": result["native_verified_cases"],
                      "result_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
