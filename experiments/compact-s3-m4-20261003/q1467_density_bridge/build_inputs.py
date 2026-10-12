#!/usr/bin/env python3
"""Build exact density-matched chained-S3 inputs at N53 and N83."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))

from chain_s3 import Formula, multiplication_table, square_destinations  # noqa: E402
from chain_s3_factored import s3_link_factored  # noqa: E402
from chain_s3_multitarget import choose_target_x  # noqa: E402
from enumerate_q1413_projected_x import canonical_rotation  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402
from q1419_partial_pin.run_cell import pin_bits  # noqa: E402
from q1420_root_theory.build_formula import convert_to_cnf  # noqa: E402
from q1423_target_coupled.target_inputs import encode_targets  # noqa: E402
from q1425_reverse_pair.relax_control import serialize_cnf  # noqa: E402
from q1438_dense_base.build_formula import encode_map  # noqa: E402
from run_probe import curves, field, sha  # noqa: E402

BRIDGE = HERE / "protocol.json"
OUTPUT = HERE / "inputs"
CASES = ("n53_planted", "n53_planted_unpinned", "n53_ordinary",
         "n83_planted", "n83_planted_unpinned", "n83_ordinary")
SEEDS = {53: 1467053, 83: 1467083}


def canonical_digest(record: dict) -> str:
    raw = json.dumps(record, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def base(n: int) -> dict:
    if n == 53:
        record = json.loads((HERE / "n53_w3_26_orbits.json").read_text())
        return {
            "B": record["actual_usable_points_B_before_folding"],
            "K": record["selected_projected_columns_K"],
            "digest": record["selected_projected_orbit_keys_digest_sha256"],
            "allowed": [int(x, 16) for x in record[
                "allowed_raw_x_masks_onb_hex"]],
            "weight": 3,
        }
    record = json.loads((PARENT /
        "runs/n83_q1413_projected_x_w4.json").read_text())
    return {
        "B": record["actual_usable_points_B_before_folding"],
        "K": record["signed_frobenius_columns_K"],
        "digest": record["enumerated_set_sha256"],
        "allowed": None, "weight": 4,
    }


def planted(n: int, fb: dict, cofactor: int) -> tuple[list[int], dict]:
    rng = random.Random(SEEDS[n])
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    candidates = fb["allowed"]
    for _ in range(1000):
        leaves, projected_keys = [], set()
        for _leaf in range(4):
            for _attempt in range(10000):
                if candidates is None:
                    positions = rng.sample(range(n), fb["weight"])
                    mask = sum(1 << j for j in positions)
                else:
                    mask = rng.choice(candidates)
                point = curve.pointFromX(onb.fromCoords(mask))
                if point is None:
                    continue
                projected = curve.mul(point, cofactor)
                if projected is None:
                    continue
                key = canonical_rotation(orbit.cycle_bits(projected[0]), n)
                if key in projected_keys:
                    continue
                leaves.append((mask, point, key))
                projected_keys.add(key)
                break
            else:
                raise RuntimeError("planted leaf search exhausted")
        left = curve.add(leaves[0][1], leaves[1][1])
        right = curve.add(leaves[2][1], leaves[3][1])
        total = curve.add(left, right)
        if left is None or right is None or total is None:
            continue
        public = curve.mul(total, cofactor)
        if public is None:
            continue
        target_x = int(onb.toCoords(total[0]))
        return [target_x], {
            "seed": SEEDS[n],
            "raw_leaf_x_masks_onb_hex": [format(row[0], "x")
                                              for row in leaves],
            "projected_orbit_keys_onb_hex": [format(row[2], "x")
                                                  for row in leaves],
            "raw_pair_midpoint_x_onb_hex": [
                format(int(onb.toCoords(left[0])), "x"),
                format(int(onb.toCoords(right[0])), "x")],
            "raw_target_x_onb_hex": format(target_x, "x"),
            "public_target": [int(public[0]), int(public[1])],
        }
    raise RuntimeError("planted group sum search exhausted")


def ordinary(n: int) -> tuple[list[int], list[int], str]:
    source = PARENT / f"q1455_joint_tail/runs/n{n}_ordinary/targets.txt"
    lines = source.read_text().splitlines()
    assert lines[0].startswith(f"Q1423TARGETS1 {n} ")
    targets = [int(x, 16) for x in lines[1:]]
    assert int(lines[0].split()[2]) == len(targets)
    receipt = json.loads((PARENT /
        f"q1466_leaf_rotation/runs/n{n}_ordinary/receipt.json").read_text())
    return targets, receipt["public_target"], receipt["workload_id"]


def make_case(name: str):
    assert name in CASES
    n = 53 if "n53" in name else 83
    role = "ordinary" if name.endswith("ordinary") else "planted"
    bridge = json.loads(BRIDGE.read_text())
    profile = next(p for p in bridge["profiles"] if p["degree_n"] == n)
    fb = base(n)
    assert fb["B"] == profile["factor_base_actual_B"]
    assert fb["K"] == profile["folded_columns_K"]
    if n == 83:
        assert fb["digest"] == profile["enumerated_set_sha256"]
    else:
        assert profile["enumerated_set_sha256"] is None
    cofactor = 428 if n == 53 else 4
    if role == "ordinary":
        targets, public, workload_id = ordinary(n)
        fixture = None
    else:
        targets, fixture = planted(n, fb, cofactor)
        public = fixture["public_target"]
        workload_record = {
            "curve_id": profile["curve_id"],
            "subgroup_order": profile["subgroup_order"],
            "public_target": public,
            "raw_target_x_onb_hex": [format(x, "x") for x in targets],
            "input_law": "four_distinct_base_orbit_points_planted",
            "seed": SEEDS[n], "target_count": 1,
            "cache_state": "cold",
        }
        workload_id = canonical_digest(workload_record)
    onb = field.Onb(n)
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(4)]
    mids = [[formula.new() for _ in range(n)] for _ in range(2)]
    for bits in leaves:
        formula.at_most(bits, fb["weight"])
        formula.clauses.append(bits[:])
        if fb["allowed"] is not None:
            selectors = [formula.new() for _ in fb["allowed"]]
            formula.clauses.append(selectors)
            for selector, mask in zip(selectors, fb["allowed"]):
                for j, bit in enumerate(bits):
                    formula.clauses.append([
                        -selector, bit if mask >> j & 1 else -bit])
    target, target_selector = choose_target_x(formula, n, targets)
    table = multiplication_table(onb)
    destinations = square_destinations(onb)
    s3_link_factored(formula, leaves[0], leaves[1], mids[0],
                     table, destinations)
    s3_link_factored(formula, leaves[2], leaves[3], mids[1],
                     table, destinations)
    s3_link_factored(formula, mids[0], mids[1], target,
                     table, destinations)
    if fixture is not None and name.endswith("_planted"):
        for bits, hex_mask in zip(leaves, fixture[
                "raw_leaf_x_masks_onb_hex"]):
            pin_bits(formula, bits, int(hex_mask, 16))
    meta = {
        "proposal_id": "Q1467", "candidate_id": None,
        "isogeny": "none", "degree_n": n, "curve_id": profile["curve_id"],
        "case": name, "input_role": role,
        "leaves_pinned": bool(fixture is not None and
                              name.endswith("_planted")),
        "normal_basis_weight_bound": fb["weight"],
        "factor_base_actual_B": fb["B"],
        "folded_columns_K": fb["K"],
        "factor_base_enumerated_set_sha256": fb["digest"],
        "public_target": public, "workload_id": workload_id,
        "target_preimage_x_count": len(targets),
        "leaf_variables": leaves, "pair_mid_variables": mids,
        "target_selector_variables": target_selector,
        "planted_fixture": fixture,
    }
    variables, clauses = convert_to_cnf(formula)
    cnf = serialize_cnf(variables, clauses)
    varmap = encode_map(meta)
    target_bytes = encode_targets(n, targets)
    return cnf, varmap, target_bytes, meta, variables, clauses, formula


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case", choices=CASES)
    args = parser.parse_args()
    bridge = json.loads(BRIDGE.read_text())
    assert bridge["source_sha256"]["select_n53_base.py"] == sha(
        HERE / "select_n53_base.py")
    assert bridge["input_sha256"] == {
        path: sha(ROOT / path) for path in bridge["input_sha256"]}
    for name in ((args.case,) if args.case else CASES):
        cnf, varmap, targets, meta, variables, clauses, _ = make_case(name)
        folder = OUTPUT / name
        files = {
            "system.cnf.gz": gzip.compress(cnf, mtime=0),
            "variables.txt": varmap,
            "targets.txt": targets,
            "meta.json": (json.dumps(meta, indent=2, sort_keys=True) +
                          "\n").encode("utf-8"),
        }
        if args.check:
            assert all((folder / leaf).read_bytes() == data
                       for leaf, data in files.items())
        else:
            assert not folder.exists(), "refuse overwrite"
            folder.mkdir(parents=True)
            for leaf, data in files.items():
                (folder / leaf).write_bytes(data)
        print(json.dumps({"case": name, "B": meta["factor_base_actual_B"],
                          "K": meta["folded_columns_K"],
                          "variables": variables, "clauses": len(clauses),
                          "cnf_sha256": hashlib.sha256(cnf).hexdigest(),
                          "workload_id": meta["workload_id"]}), flush=True)


if __name__ == "__main__":
    main()
