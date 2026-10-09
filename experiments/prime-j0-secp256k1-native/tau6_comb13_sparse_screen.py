#!/usr/bin/env python3
"""Screen a 1024-point tau-six comb with a complete sparse top-row fallback."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import LAMBDA_TAU, affine_from_native, scalar_text
from glv_comb_comparison import glv_count
import lazy_tau_screen as curve
from redundant_tau4_screen import norm
from screen_coset_representatives import candidates
from tau6_comb_screen import comb_record, digit_stream
from width6_tau_screen import build_width_six_table


HERE = Path(__file__).resolve().parent
TRAIN_SEED = 2026100922
HOLDOUT_SEED = 2026100923
TRAIN_COUNT = 10_000
HOLDOUT_COUNT = 100_000
SPARSE_TOP_ORBITS = (0, 1, 2, 3, 4, 5, 6, 18, 19, 20, 21, 22, 23, 24,
                     25, 26, 27, 28, 29, 40, 41, 42, 43, 44, 45, 46, 47,
                     48, 49, 50, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65,
                     69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80)
MISS_SCALAR = int("291a4b1cec292deb928a94385017b681693459cc424b1a9be19f9511ff968bc7", 16)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def top_orbit(digits, table):
    top = [table[(digit[0] % 27, digit[1] % 27)][1]
           for index, digit in enumerate(digits)
           if index >= 156 and digit is not None]
    assert len(top) <= 1
    return top[0] if top else None


def selected_cost(digits, orbit, selected):
    fast = comb_record(digits, 13, 162)
    fallback = orbit is not None and orbit not in selected
    charged = comb_record(digits, 1, 162) if fallback else fast
    return fallback, charged


def freeze_selection(table, seeds):
    frequency = Counter()
    rng = random.Random(TRAIN_SEED)
    for _ in range(TRAIN_COUNT):
        scalar = rng.randrange(curve.ORDER)
        start = candidates(scalar)[0][2:4]
        orbit = top_orbit(digit_stream(start, table, 162), table)
        if orbit is not None:
            frequency[orbit] += 1
    ranked = sorted(range(81), key=lambda orbit:
                    (-frequency[orbit], norm(seeds[orbit]), orbit))
    selected = tuple(sorted(ranked[:52]))
    assert selected == SPARSE_TOP_ORBITS
    return frequency


def native_check(binary, scalars, rows, cases):
    request = "".join(scalar_text(scalar) + "\n" for scalar in scalars)
    process = subprocess.run([str(binary), "--scalar-w6-comb13-sparse-fixed"],
                             input=request, text=True, capture_output=True,
                             check=True, timeout=120)
    actual = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(actual) == len(scalars)
    for index, (scalar, output) in enumerate(zip(scalars, actual)):
        expected = rows[index]
        assert output["radix"] == "orbit-w6-comb13-sparse-fixed", index
        assert affine_from_native(output["point"]) == curve.point_multiply(
            scalar % curve.ORDER), index
        assert output["recoding_work"]["sparse_fallback"] == expected["fallback"], index
        assert output["tau_steps"] == expected["tau_steps"], index
        assert output["nonzero_digits"] == expected["mixed_additions"], index
        assert list(map(int, output["representative"])) == expected["representative"], index
        assert sum(output["orbit_counts"]) == expected["mixed_additions"], index
    assert cases == 214 and rows[-1]["fallback"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE / "tau6-comb-result.json")
    parser.add_argument("--binary", type=Path,
                        default=HERE / "target/release/eisenstein_fixed")
    parser.add_argument("--output", type=Path,
                        default=HERE / "tau6-comb13-sparse-result.json")
    args = parser.parse_args()
    source_path = args.input.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    source = json.loads(source_path.read_text())
    assert source["schema"] == 1 and source["status"] == "passed"
    assert source["universal_digit_span"] == 162 and len(source["cases"]) == 214
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    training = freeze_selection(table, seeds)
    selected = set(SPARSE_TOP_ORBITS)
    assert 12 * 81 + len(selected) == 1024
    panel_totals = {panel: Counter() for panel in
                    ("frozen_edges", "frozen_random", "holdout_random")}
    rows = []
    scalars = []
    for case in source["cases"]:
        scalar = int(case["scalar_hex"], 16)
        start = tuple(case["representative"])
        digits = digit_stream(start, table, 162)
        orbit = top_orbit(digits, table)
        fallback, charged = selected_cost(digits, orbit, selected)
        baseline = case["comb"]["12"]
        glv = glv_count(*start, 10)
        assert (start[0] + start[1] * LAMBDA_TAU - scalar) % curve.ORDER == 0
        totals = panel_totals[case["panel"]]
        totals.update({"tau13_proxy": charged["field_product_proxy"],
                       "tau12_proxy": baseline["field_product_proxy"],
                       "glv10_proxy": glv["field_product_proxy"],
                       "tau13_fallbacks": int(fallback)})
        rows.append({"index": case["index"], "panel": case["panel"],
                     "scalar_hex": case["scalar_hex"],
                     "representative": list(start), "top_orbit": orbit,
                     "fallback": fallback, "tau_steps": charged["tau_steps"],
                     "mixed_additions": charged["mixed_additions"],
                     "field_product_proxy": charged["field_product_proxy"]})
        scalars.append(scalar)
    miss_start = candidates(MISS_SCALAR)[0][2:4]
    miss_digits = digit_stream(miss_start, table, 162)
    miss_orbit = top_orbit(miss_digits, table)
    miss_fallback, miss_cost = selected_cost(miss_digits, miss_orbit, selected)
    assert miss_fallback and miss_orbit == 66
    rows.append({"representative": list(miss_start), "fallback": True,
                 "tau_steps": miss_cost["tau_steps"],
                 "mixed_additions": miss_cost["mixed_additions"]})
    scalars.append(MISS_SCALAR)
    native_check(binary, scalars, rows, 214)
    rows.pop()
    holdout = Counter()
    holdout_orbits = set()
    rng = random.Random(HOLDOUT_SEED)
    for _ in range(HOLDOUT_COUNT):
        scalar = rng.randrange(curve.ORDER)
        start = candidates(scalar)[0][2:4]
        digits = digit_stream(start, table, 162)
        orbit = top_orbit(digits, table)
        if orbit is not None:
            holdout_orbits.add(orbit)
        fallback, charged = selected_cost(digits, orbit, selected)
        holdout.update({"tau13_proxy": charged["field_product_proxy"],
                        "tau12_proxy": comb_record(digits, 12, 162)["field_product_proxy"],
                        "glv10_proxy": glv_count(*start, 10)["field_product_proxy"],
                        "fallbacks": int(fallback)})
    output = {"schema": 1, "status": "passed", "curve": "secp256k1",
              "algorithm": "sparse-top-row-tau6-comb13",
              "stored_point_entries": 1024, "full_rows": 12,
              "top_row_orbits": list(SPARSE_TOP_ORBITS),
              "selection": {"seed": TRAIN_SEED, "scalars": TRAIN_COUNT,
                            "rule": "top-52 frequency, then seed norm, then orbit id",
                            "observed_top_orbits": sum(value > 0 for value in training.values())},
              "frozen": {"cases": len(source["cases"]),
                         "panels": {panel: dict(counts) for panel, counts in panel_totals.items()},
                         "rows": rows},
              "disjoint_holdout": {"seed": HOLDOUT_SEED, "scalars": HOLDOUT_COUNT,
                                   "top_orbits_seen": len(holdout_orbits),
                                   **dict(holdout)},
              "deliberate_fallback": {"scalar_hex": hex(MISS_SCALAR),
                                      "top_orbit": miss_orbit, "verified": True},
              "native_verified_cases": len(scalars),
              "input_sha256": sha(source_path),
              "source_sha256": sha(Path(__file__)),
              "native_source_sha256": sha(HERE / "src/bin/eisenstein_fixed.rs"),
              "binary_sha256": sha(binary)}
    if args.output.exists():
        raise SystemExit("result exists; refusing overwrite")
    args.output.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": output["status"], "stored_point_entries": 1024,
                      "frozen": output["frozen"]["panels"],
                      "disjoint_holdout": output["disjoint_holdout"],
                      "result_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
