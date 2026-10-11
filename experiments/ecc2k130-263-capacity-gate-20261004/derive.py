#!/usr/bin/env python3
"""Derive exact ECC2K-130 subgroup-support and orbit-column floors."""

import argparse
from hashlib import sha256
import json
from math import comb
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"
SCREEN = ROOT / "experiments/ecc2k130-263-w-screen-20261004/evidence/run-r2/summary.json"
PROTOCOL_COMMIT = "41348c06286beec8d7f35c4556883224ed438eaf"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def minimum_base(r, m, numerator, denominator):
    needed = ((r - 1) * numerator + denominator - 1) // denominator
    lower, upper = 0, 1
    while comb(upper + m - 1, m) < needed:
        upper *= 2
    while lower + 1 < upper:
        middle = (lower + upper) // 2
        if comb(middle + m - 1, m) >= needed:
            upper = middle
        else:
            lower = middle
    assert comb(upper + m - 2, m) < needed
    assert comb(upper + m - 1, m) >= needed
    return upper, needed


def derive():
    if not __debug__:
        raise RuntimeError("exact-input assertions must remain enabled")
    config = json.loads(CONFIG.read_text())
    assert config["schema"] == "ecc2k130_263_capacity_gate_config/v1"
    assert digest(ROUTE) == config["route_manifest_sha256"]
    assert digest(SCREEN) == config["w_screen_summary_sha256"]
    route = json.loads(ROUTE.read_text())
    screen = json.loads(SCREEN.read_text())
    assert route["route_id"] == config["route_id"]
    assert route["field"]["p"] == 2
    assert route["field"]["n"] == config["field_degree"] == 131
    assert route["curve_nodes"]["source"]["curve_id"] == config["source_curve_id"]
    assert route["curve_nodes"]["target"]["curve_id"] == config["target_curve_id"]
    endomorphism = route["endomorphism"]
    assert (endomorphism["source_order_conductor"],
            endomorphism["target_order_conductor"],
            endomorphism["ell"]) == (1, 263, 263)
    r = int(route["curve_nodes"]["source"]["subgroup_order"])
    assert r == int(route["curve_nodes"]["target"]["subgroup_order"])
    assert r > 4 and r % 2 == 1
    residue_bytes = (r.bit_length() + 7) // 8

    rows = []
    for m in config["m_values"]:
        assert 3 <= m <= 8
        for threshold in config["support_thresholds"]:
            numerator = threshold["numerator"]
            denominator = threshold["denominator"]
            assert 0 < numerator <= denominator
            b, needed = minimum_base(r, m, numerator, denominator)
            ways_before = comb(b + m - 2, m)
            ways_at = comb(b + m - 1, m)
            sign_columns = (b + 1) // 2
            orbit_columns = (b + 261) // 262
            rows.append({
                "summands": m,
                "threshold_numerator": numerator,
                "threshold_denominator": denominator,
                "threshold_required_multisets": str(needed),
                "minimum_actual_B": b,
                "multisets_at_B_minus_one": str(ways_before),
                "multisets_at_B": str(ways_at),
                "sign_only_columns_floor": sign_columns,
                "sign_frobenius_columns_floor_if_orbit_closed": orbit_columns,
                "sign_only_log_vector_bytes_floor": sign_columns * residue_bytes,
                "orbit_closed_log_vector_bytes_floor": orbit_columns * residue_bytes,
            })

    old_cells = {cell["dimension"]: cell for cell in screen["cells"]}
    w_cases = []
    for case in config["w_cases"]:
        d, m = case["dimension"], case["summands"]
        b_max = 2 * ((1 << d) - 1)
        ways = comb(b_max + m - 1, m)
        capped = min(ways, r - 1)
        if d in old_cells and old_cells[d]["capacity"]["summands"] == m:
            old = old_cells[d]["capacity"]
            assert old["projected_base_B_upper"] == b_max
            assert old["support_numerator_upper"] == capped
            assert old["support_denominator"] == r - 1
        w_cases.append({
            "dimension": d,
            "summands": m,
            "projected_base_B_upper": b_max,
            "uniform_support_numerator_upper": str(capped),
            "uniform_support_denominator": str(r - 1),
            "below_one_percent": ways * 100 < r - 1,
            "upper_bound_is_saturated_at_one": ways >= r - 1,
            "reproduces_frozen_screen": d in old_cells and old_cells[d]["capacity"]["summands"] == m,
        })

    return {
        "schema": "ecc2k130_263_capacity_gate/v1",
        "status": "exact_counting_complete",
        "candidate_id": None,
        "route_id": route["route_id"],
        "source_curve_id": config["source_curve_id"],
        "target_curve_id": config["target_curve_id"],
        "source_endomorphism_order_conductor": 1,
        "target_endomorphism_order_conductor": 263,
        "subgroup_order": str(r),
        "subgroup_residue_bytes": residue_bytes,
        "protocol_commit": PROTOCOL_COMMIT,
        "source_main_commit": config["source_main_commit"],
        "input_sha256": {
            "CONFIG.json": digest(CONFIG),
            "route_manifest": digest(ROUTE),
            "w_screen_summary": digest(SCREEN),
            "derive.py": digest(Path(__file__)),
        },
        "rows": rows,
        "w_cases": w_cases,
        "natural_pdp_yield": None,
        "verified_relation_rank": None,
        "online_wall_time": None,
        "cold_wall_time": None,
        "verified_logarithm": None,
        "rho_ratio": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = derive()
    with args.out.open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "rows": len(result["rows"]),
                      "w_cases": len(result["w_cases"])}))


if __name__ == "__main__":
    main()
