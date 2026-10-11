#!/usr/bin/env python3
"""Verify the binary-Edwards t coordinate and enumerate its N53 W3 base."""

import argparse
import hashlib
import itertools
import json
import math
import platform
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/compact-s3-m4-20261003"
Q1419 = PARENT / "q1419_partial_pin"
sys.path[:0] = [str(HERE), str(Q1419), str(PARENT),
                str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from chain_s3 import Formula, multiplication_table, square_destinations  # noqa: E402
from chain_s3_factored import s3_link_factored  # noqa: E402
from run_cell import read_profile  # noqa: E402
from t_link import evaluate_t3, t3_link, t_of_x, x_roots_of_t  # noqa: E402

PROPOSAL = "Q20261010173300"
FREEZE = HERE / "freeze.json"
Q1419_PROTOCOL = Q1419 / "protocol.json"
WEIGHT = 3
TRIPLE_SEED = 202610101733
TRIPLES = 32


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    assert not path.exists(), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def freeze():
    protocol = load(Q1419_PROTOCOL)
    profiles = {}
    for n in (53, 83):
        profile, _, _ = read_profile(protocol, n)
        profiles[str(n)] = {
            "curve_id": profile["curve_id"],
            "generator": profile["curve"]["generator"],
            "subgroup_order_r": profile["subgroup_order_r"],
            "cofactor": profile["cofactor"],
            "ordinary_workload_id": profile["workload_id"],
            "ordinary_public_target": profile["public_target"],
            "parent_exact_base_B": profile["factor_base_actual_B"],
            "parent_exact_base_K": profile["folded_columns_K"],
            "parent_exact_base_digest": profile[
                "factor_base_enumerated_set_sha256"],
        }
    save(FREEZE, {
        "schema": "q20261010173300-freeze-v1",
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "isogeny": "none", "field_degrees": [53, 83, 131],
        "n53_t_weight_bound": WEIGHT,
        "triple_seed": TRIPLE_SEED, "triples_per_degree": TRIPLES,
        "q1419_protocol_sha256": digest(Q1419_PROTOCOL),
        "source_sha256": {name: digest(HERE / name) for name in
                          ("PROTOCOL.md", "t_link.py", "experiment.py",
                           "audit.py")},
        "reference_profiles": profiles,
    })
    print(json.dumps({"freeze_sha256": digest(FREEZE)}))


def check_freeze():
    frozen = load(FREEZE)
    assert frozen["q1419_protocol_sha256"] == digest(Q1419_PROTOCOL)
    for name, expected in frozen["source_sha256"].items():
        assert digest(HERE / name) == expected
    return frozen


def identity_controls(n, profile, seed, count):
    f = field.Onb(n)
    e = curves.Curve(f)
    G = tuple(profile["generator"])
    assert e.onCurve(G)
    two_torsion = (0, f.one())
    assert e.onCurve(two_torsion) and e.dbl(two_torsion) is None
    rng = random.Random(seed + n)
    rows = []
    started = time.monotonic()
    for index in range(count):
        a = rng.randrange(1, 1 << 20)
        b = rng.randrange(1, 1 << 20)
        P, Q = e.mul(G, a), e.mul(G, b)
        R = e.neg(e.add(P, Q))
        assert P is not None and Q is not None and R is not None
        values = [t_of_x(f, point[0]) for point in (P, Q, R)]
        assert evaluate_t3(f, *values) == 0
        assert t_of_x(f, e.neg(P)[0]) == values[0]
        assert t_of_x(f, e.add(P, two_torsion)[0]) == values[0]
        assert t_of_x(f, e.frob(P)[0]) == f.sqr(values[0])
        for value in values:
            xroots = x_roots_of_t(f, e, value)
            assert P[0] in xroots if value == values[0] else len(xroots) in (1, 2)
        rows.append({"index": index, "scalar_a": a, "scalar_b": b,
                     "t_coords": [f.toCoords(v) for v in values]})
    return {"curve_id": profile["curve_id"], "triple_count": len(rows),
            "elapsed_seconds_exploratory": time.monotonic() - started,
            "rows": rows}


def formula_shape(n, variant):
    f = field.Onb(n)
    table = multiplication_table(f)
    destinations = square_destinations(f)
    formula = Formula()
    a, b, c = ([formula.new() for _ in range(n)] for _ in range(3))
    started = time.monotonic()
    if variant == "x":
        s3_link_factored(formula, a, b, c, table, destinations)
    else:
        assert variant == "t"
        t3_link(formula, a, b, c, table, destinations,
                f.toCoords(f.one()))
    return {"n": n, "variant": variant,
            "variables": formula.variables,
            "cnf_clauses": len(formula.clauses),
            "xor_rows": len(formula.xors),
            "and_gates": len(formula.and_cache),
            "build_seconds_exploratory": time.monotonic() - started}


def canonical_x(f, x):
    values = []
    current = x
    for _ in range(f.m):
        values.append(f.toCoords(current))
        current = f.sqr(current)
    assert current == x
    assert len(set(values)) == f.m
    return min(values)


def enumerate_n53_base(profile):
    n = 53
    f = field.Onb(n)
    e = curves.Curve(f)
    torsion = (0, f.one())
    keys = set()
    metrics = {"nominal_t_masks": 0, "x_quadratic_solvable": 0,
               "rational_t_values": 0, "identity_projection": 0,
               "duplicate_projected_columns": 0,
               "torsion_pair_checks": 0, "subgroup_order_checks": 0}
    started = time.monotonic()
    for weight in range(1, WEIGHT + 1):
        for positions in itertools.combinations(range(n), weight):
            mask = sum(1 << position for position in positions)
            metrics["nominal_t_masks"] += 1
            value = f.fromCoords(mask)
            roots = x_roots_of_t(f, e, value)
            if not roots:
                continue
            assert len(roots) == 2
            metrics["x_quadratic_solvable"] += 1
            point = e.pointFromX(roots[0])
            if point is None:
                continue
            metrics["rational_t_values"] += 1
            translated = e.add(point, torsion)
            assert translated[0] == roots[1]
            metrics["torsion_pair_checks"] += 1
            projected = e.mul(point, profile["cofactor"])
            if projected is None:
                metrics["identity_projection"] += 1
                continue
            if metrics["subgroup_order_checks"] < 64:
                assert e.mul(projected, profile["subgroup_order_r"]) is None
                metrics["subgroup_order_checks"] += 1
            key = canonical_x(f, projected[0])
            if key in keys:
                metrics["duplicate_projected_columns"] += 1
            else:
                keys.add(key)
    elapsed = time.monotonic() - started
    assert metrics["nominal_t_masks"] == sum(
        math.comb(n, w) for w in range(1, WEIGHT + 1))
    packed = b"".join(value.to_bytes(7, "little")
                      for value in sorted(keys))
    path = HERE / "bases/n53_t_weight3_columns.bin"
    assert not path.exists()
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(packed)
    k = len(keys)
    return {"curve_id": profile["curve_id"], "weight_bound": WEIGHT,
            "field_degree_n": n, "actual_usable_points_B": 2*n*k,
            "folded_columns_K": k,
            "enumerated_set_encoding": "sorted canonical projected x keys, 7-byte little-endian",
            "enumerated_set_sha256": digest(path),
            "enumerated_set_bytes": len(packed),
            "geometric_point_count_before_projection": 4*metrics[
                "rational_t_values"],
            "enumeration_seconds_exploratory": elapsed,
            "metrics": metrics}


def run():
    frozen = check_freeze()
    output = HERE / "run.json"
    assert not output.exists()
    protocol = load(Q1419_PROTOCOL)
    profiles = {}
    for n in (53, 83):
        profile, _, _ = read_profile(protocol, n)
        assert profile["curve_id"] == frozen["reference_profiles"][str(n)][
            "curve_id"]
        profiles[n] = frozen["reference_profiles"][str(n)]
    base = enumerate_n53_base(profiles[53])
    controls = [identity_controls(n, profiles[n], frozen["triple_seed"],
                                  frozen["triples_per_degree"])
                for n in (53, 83)]
    shapes = [formula_shape(n, variant)
              for n in frozen["field_degrees"] for variant in ("x", "t")]
    usage = resource.getrusage(resource.RUSAGE_SELF)
    save(output, {"schema": "q20261010173300-run-v1",
                  "proposal_id": PROPOSAL, "candidate_id": None,
                  "run_id": None, "isogeny": "none",
                  "freeze_sha256": digest(FREEZE),
                  "n53_t_base": base, "identity_controls": controls,
                  "formula_shapes": shapes,
                  "peak_process_rss_raw": usage.ru_maxrss,
                  "peak_process_rss_unit": "bytes" if platform.system() == "Darwin"
                                           else "kilobytes"})
    print(json.dumps({"status": "RECORDED", "n53_B": base[
        "actual_usable_points_B"], "n53_K": base["folded_columns_K"],
        "run_sha256": digest(output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "run"))
    action = parser.parse_args().action
    if action == "freeze":
        freeze()
    elif action == "check":
        check_freeze(); print("PASS: freeze")
    else:
        run()
