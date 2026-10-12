#!/usr/bin/env python3
"""Screen three equivalent lattice representatives for the sparse tau13 comb."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import affine_from_native, scalar_text
from screen_coset_representatives import candidates
from tau6_comb13_sparse_screen import SPARSE_TOP_ORBITS, top_orbit
from tau6_comb_screen import comb_record, digit_stream
from width6_tau_screen import build_width_six_table
import lazy_tau_screen as curve


HERE = Path(__file__).resolve().parent
SEED = 2026100926
COUNT = 10_000
NATIVE_RANDOM = 256


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(scalar, table, selected):
    choices = candidates(scalar)
    attempts = []
    for rank, (_, _, a, b, _, _) in enumerate(choices[:3]):
        try:
            digits = digit_stream((a, b), table, 162)
        except AssertionError:
            attempts.append(None)
            continue
        orbit = top_orbit(digits, table)
        fallback = orbit is not None and orbit not in selected
        record = comb_record(digits, 1 if fallback else 13, 162)
        attempts.append({"rank": rank, "representative": [a, b],
                         "fallback": fallback, "tau_steps": record["tau_steps"],
                         "mixed_additions": record["mixed_additions"],
                         "field_product_proxy": record["field_product_proxy"]})
    assert attempts[0] is not None
    winner = min((item for item in attempts if item is not None),
                 key=lambda item: (item["field_product_proxy"], item["rank"]))
    return attempts[0], winner, sum(item is not None for item in attempts)


def check_native(binary, scalars, scored):
    request = "".join(scalar_text(scalar) + "\n" for scalar in scalars)
    process = subprocess.run([str(binary), "--scalar-w6-comb13-coset3-fixed"],
                             input=request, text=True, capture_output=True,
                             check=True, timeout=180)
    actual = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(actual) == len(scalars)
    for index, (scalar, expected, output) in enumerate(zip(scalars, scored, actual)):
        chosen, valid = expected
        assert output["radix"] == "orbit-w6-comb13-coset3-fixed", index
        assert affine_from_native(output["point"]) == curve.point_multiply(
            scalar % curve.ORDER), index
        assert list(map(int, output["representative"])) == chosen["representative"], index
        assert output["tau_steps"] == chosen["tau_steps"], index
        assert output["nonzero_digits"] == chosen["mixed_additions"], index
        work = output["recoding_work"]
        assert work["sparse_fallback"] == chosen["fallback"], index
        assert work["coset_rank"] == chosen["rank"], index
        assert work["valid_representatives"] == valid, index
        assert work["attempted_representatives"] == 3, index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        default=HERE / "tau6-comb13-coset-result.json")
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

    panel_totals = defaultdict(Counter)
    frozen_rows = []
    native_scalars = []
    native_scores = []
    for row in source["frozen"]["rows"]:
        scalar = int(row["scalar_hex"], 16)
        baseline, winner, valid = score(scalar, table, selected)
        assert baseline["representative"] == row["representative"]
        assert baseline["field_product_proxy"] == row["field_product_proxy"]
        assert baseline["fallback"] == row["fallback"]
        assert winner["field_product_proxy"] <= baseline["field_product_proxy"]
        panel = row["panel"]
        panel_totals[panel].update({
            "cases": 1,
            "baseline_proxy": baseline["field_product_proxy"],
            "coset3_proxy": winner["field_product_proxy"],
            "baseline_fallbacks": int(baseline["fallback"]),
            "coset3_fallbacks": int(winner["fallback"]),
            "selected_non_nearest": int(winner["rank"] != 0),
        })
        frozen_rows.append({"index": row["index"], "panel": panel,
                            "scalar_hex": row["scalar_hex"],
                            "baseline_proxy": baseline["field_product_proxy"],
                            "selected": winner, "valid_representatives": valid})
        native_scalars.append(scalar)
        native_scores.append((winner, valid))

    miss = int(source["deliberate_fallback"]["scalar_hex"], 16)
    miss_baseline, miss_winner, miss_valid = score(miss, table, selected)
    assert miss_baseline["fallback"]
    native_scalars.append(miss)
    native_scores.append((miss_winner, miss_valid))

    rng = random.Random(SEED)
    holdout = Counter()
    rank_counts = Counter()
    valid_counts = Counter()
    for index in range(COUNT):
        scalar = rng.randrange(curve.ORDER)
        baseline, winner, valid = score(scalar, table, selected)
        assert winner["field_product_proxy"] <= baseline["field_product_proxy"]
        holdout.update({"cases": 1,
                        "baseline_proxy": baseline["field_product_proxy"],
                        "coset3_proxy": winner["field_product_proxy"],
                        "baseline_fallbacks": int(baseline["fallback"]),
                        "coset3_fallbacks": int(winner["fallback"])})
        rank_counts[winner["rank"]] += 1
        valid_counts[valid] += 1
        if index < NATIVE_RANDOM:
            native_scalars.append(scalar)
            native_scores.append((winner, valid))
    check_native(binary, native_scalars, native_scores)

    result = {
        "schema": 1,
        "status": "passed",
        "algorithm": "three-shortest-coset-representatives-sparse-tau13",
        "curve": "secp256k1",
        "retained_affine_points": 1024,
        "attempted_representatives_per_scalar": 3,
        "selection_metric": "5*tau_steps + 11*mixed_additions, including complete sparse fallback",
        "frozen": {"cases": len(frozen_rows), "panels": {k: dict(v) for k, v in panel_totals.items()},
                   "rows": frozen_rows},
        "deliberate_fallback": {"scalar_hex": hex(miss),
                                "baseline": miss_baseline,
                                "selected": miss_winner,
                                "valid_representatives": miss_valid},
        "disjoint_holdout": {"seed": SEED, **dict(holdout),
                             "chosen_rank_counts": dict(rank_counts),
                             "valid_representative_counts": dict(valid_counts)},
        "native_verified_cases": len(native_scalars),
        "source_result_sha256": sha(source_path),
        "source_sha256": sha(Path(__file__)),
        "native_source_sha256": sha(HERE / "src/bin/eisenstein_fixed.rs"),
        "binary_sha256": sha(binary),
        "curve_reference_sha256": sha(HERE / "lazy_tau_screen.py"),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "disjoint_holdout": result["disjoint_holdout"],
                      "frozen_panels": result["frozen"]["panels"],
                      "native_verified_cases": result["native_verified_cases"],
                      "result_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
