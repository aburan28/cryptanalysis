#!/usr/bin/env python3
"""Verify exact rationality membership and measure its field API work."""
from __future__ import annotations

import gzip
import hashlib
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parent.parent
BASE53 = PARENT / "bases/n53_weight3_orbits.json.gz"
BASE83 = PARENT / "bases/n83_weight5_full_orbits.json"
KEYS83 = PARENT / "bases/n83_weight5_full_point_orbits.bin"
Q1494 = PARENT / "q20261012_n83_pair_base_audit/result.json"
N83_ENUM = PARENT / "enumerate_n83_weight5_full.py"
ORBIT = ROOT / "experiments/koblitz-pair-claw-20260929/orbit_key.py"
FIELD = ROOT / "ecc2k130/codegen/field.py"
CURVES = ROOT / "ecc2k130/codegen/curves.py"
sys.path[:0] = [str(PARENT), str(PARENT / "q20261011_operation_account"),
                str(ORBIT.parent), str(FIELD.parent)]
import field  # noqa: E402
from counted_onb import CountedOnb  # noqa: E402
from curves import Curve  # noqa: E402
from enumerate_n83_weight5_full import necklaces  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def save(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def exact_predicate(onb, coords: int) -> bool:
    if coords == 0:
        return False
    x = onb.fromCoords(coords)
    return onb.trace(onb.inv(x)) == (coords.bit_count() & 1)


def freeze() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = load(HERE / "protocol.json")
    base53, base83 = load(BASE53), load(BASE83)
    for row, base in zip(protocol["instances"], (base53, base83)):
        assert base["curve"]["curve_id"] == row["curve_id"]
        fb = base["factor_base"]
        assert fb["actual_usable_points_B_before_folding"] == row[
            "factor_base_actual_B"]
        assert fb["signed_frobenius_columns"] == row[
            "factor_base_folded_columns_K"]
    assert sha(KEYS83) == base83["factor_base"]["enumerated_set_sha256"]
    save(HERE / "freeze.json", {
        "proposal_id": "Q1495", "candidate_id": None, "run_id": None,
        "files_sha256": {n: sha(HERE / n) for n in
                         ("protocol.json", "filter.py", "validate.py")},
        "base53_sha256": sha(BASE53), "base83_sha256": sha(BASE83),
        "base83_keys_sha256": sha(KEYS83),
        "q1494_result_sha256": sha(Q1494),
        "n83_enumerator_source_sha256": sha(N83_ENUM),
        "orbit_source_sha256": sha(ORBIT),
        "field_source_sha256": sha(FIELD),
        "curve_source_sha256": sha(CURVES),
    })
    print("Q1495 frozen", sha(HERE / "freeze.json")[:12])


def n53_screen(base: dict) -> dict:
    onb = field.Onb(53)
    curve = Curve(onb)
    count = rational = 0
    per_weight = {}
    for weight in range(1, 4):
        total = good = 0
        for subset in itertools.combinations(range(53), weight):
            coords = sum(1 << i for i in subset)
            x = onb.fromCoords(coords)
            assert onb.trace(x) == (weight & 1)
            accept = exact_predicate(onb, coords)
            rational_lift = curve.pointFromX(x) is not None
            assert accept == rational_lift
            total += 1
            good += accept
        per_weight[str(weight)] = {"x_masks": total, "rational_x_masks": good}
        count += total
        rational += good
    fb = base["factor_base"]
    assert count == fb["nominal_x_mask_count"] == 24_857
    assert rational == fb["geometric_rational_x_count"] == 12_031
    assert fb["geometric_point_count_before_projection"] == 2 * rational
    assert fb["actual_usable_points_B_before_folding"] == 2 * rational
    assert base["enumeration"]["projected_identity_orbits"] == 0
    assert base["enumeration"]["projected_duplicate_orbits"] == 0
    return {"x_masks": count, "rational_x_masks": rational,
            "predicate_equals_curve_lift_for_all_masks": True,
            "per_weight": per_weight}


def n83_orbit_screen(base: dict) -> dict:
    onb = field.Onb(83)
    orbit = OrbitKey(onb)
    per_weight = {str(w): {"x_orbits": 0, "rational_x_orbits": 0}
                  for w in range(1, 6)}
    for cycle_mask in necklaces(83, 5):
        weight = cycle_mask.bit_count()
        coords = sum(1 << orbit.coordinate_cycle[i]
                     for i in range(83) if cycle_mask >> i & 1)
        x = onb.fromCoords(coords)
        assert onb.trace(x) == (weight & 1)
        row = per_weight[str(weight)]
        row["x_orbits"] += 1
        row["rational_x_orbits"] += exact_predicate(onb, coords)
    archived = {str(row["weight"]): row for row in base["weight_strata"]}
    for weight, row in per_weight.items():
        assert row["x_orbits"] == archived[weight]["x_orbits"]
        assert row["rational_x_orbits"] == archived[weight][
            "rational_x_orbits"]
        assert archived[weight]["identity_projection_orbits"] == 0
        assert archived[weight]["duplicate_projection_orbits"] == 0
    total = sum(row["x_orbits"] for row in per_weight.values())
    rational = sum(row["rational_x_orbits"] for row in per_weight.values())
    fb = base["factor_base"]
    assert total == fb["raw_x_frobenius_orbits"] == 373_101
    assert rational == fb["rational_raw_x_orbits"] == 186_612
    assert rational == fb["signed_frobenius_columns"]
    assert fb["actual_usable_points_B_before_folding"] == 2 * 83 * rational
    return {"x_orbits": total, "rational_x_orbits": rational,
            "per_weight": per_weight,
            "all_rational_orbits_project_to_distinct_usable_columns": True}


def stage_cost(q1494: dict) -> dict:
    onb = CountedOnb(83)
    rows = []
    for old in q1494["rows"]:
        onb.reset_counts()
        accepted = True
        leaves_checked = 0
        for leaf in old["leaves"]:
            accepted = exact_predicate(onb, leaf["coords"])
            leaves_checked += 1
            assert accepted == leaf["exact_base_member"]
            if not accepted:
                break
        assert accepted == old["both_usable"]
        calls = onb.snapshot_counts()
        rows.append({"phase": old["phase"], "flip_count": old["flip_count"],
                     "both_usable": accepted, "leaves_checked": leaves_checked,
                     "short_filter_field_api_calls": calls,
                     "short_filter_field_api_entries": sum(calls.values()),
                     "exact_full_filter_field_api_entries": old[
                         "field_api_entries_for_base_filter"]})
    short = sum(r["short_filter_field_api_entries"] for r in rows)
    full = sum(r["exact_full_filter_field_api_entries"] for r in rows)
    assert len(rows) == 40 and sum(r["both_usable"] for r in rows) == 8
    assert short == 427 and full == 5_948
    return {"pairs": 40, "usable_pairs": 8,
            "short_filter_field_api_entries": short,
            "full_filter_field_api_entries": full,
            "full_over_short_field_api_ratio": full / short,
            "rows": rows}


def run() -> None:
    assert not (HERE / "result.json").exists()
    frozen = load(HERE / "freeze.json")
    assert all(sha(HERE / n) == h for n, h in frozen["files_sha256"].items())
    for key, path in (("base53_sha256", BASE53), ("base83_sha256", BASE83),
                      ("base83_keys_sha256", KEYS83),
                      ("q1494_result_sha256", Q1494),
                      ("n83_enumerator_source_sha256", N83_ENUM),
                      ("orbit_source_sha256", ORBIT),
                      ("field_source_sha256", FIELD),
                      ("curve_source_sha256", CURVES)):
        assert sha(path) == frozen[key]
    base53, base83, q1494 = load(BASE53), load(BASE83), load(Q1494)
    a = n53_screen(base53)
    print("Q1495 N53", a["x_masks"], a["rational_x_masks"], flush=True)
    b = n83_orbit_screen(base83)
    print("Q1495 N83", b["x_orbits"], b["rational_x_orbits"], flush=True)
    c = stage_cost(q1494)
    save(HERE / "result.json", {
        "proposal_id": "Q1495", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "source_sha256": sha(Path(__file__)),
        "n53": a, "n83": b, "n83_pair_stage_cost": c,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    })
    print("Q1495 filter", c["short_filter_field_api_entries"],
          c["full_filter_field_api_entries"],
          c["full_over_short_field_api_ratio"])


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "run"):
        raise SystemExit("usage: filter.py {freeze|run}")
    globals()[sys.argv[1]]()
