#!/usr/bin/env sage -python
"""Independently regenerate every W-mask predicate and point control."""

import argparse
from decimal import Decimal, localcontext
import hashlib
import json
from math import comb, isclose, sqrt
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"
RUNTIME = HERE / "runtime-info.json"
PRODUCER = HERE / "run.py"
SMALL_ARITY = {24: 5, 28: 4, 35: 3}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(field, ring_variable, value):
    value = int(value)
    polynomial = sum(ring_variable**j for j in range(value.bit_length())
                     if (value >> j) & 1)
    return field(polynomial)


def encode(value):
    return sum(int(coefficient) << index
               for index, coefficient in enumerate(value.polynomial().list()))


def independent_masks(domain, d, count):
    span = 2**d - 1
    accept_below = (2**256 // span) * span
    seen = set()
    counter = 0
    output = []
    while len(output) < count:
        digest = hashlib.sha256(
            (domain + "|d=" + str(d) + "|counter=" + str(counter)).encode("ascii")
        ).digest()
        counter += 1
        word = int.from_bytes(digest, "big")
        if word >= accept_below:
            continue
        mask = word % span + 1
        if mask not in seen:
            seen.add(mask)
            output.append(mask)
    return output


def absolute_trace(value):
    trace = value.parent().zero()
    conjugate = value
    for _ in range(131):
        trace += conjugate
        conjugate = conjugate**2
    assert conjugate == value and trace in (0, 1)
    return int(trace)


def independent_half_trace(value):
    answer = value.parent().zero()
    power = value
    for _ in range(66):
        answer += power
        power = power**4
    assert answer**2 + answer == value
    return answer


def recheck_point(curve, alpha, b, r, w, row):
    u = independent_half_trace(w)
    assert u not in (0, 1)
    x1 = alpha * (u + 1) / u
    x2 = alpha * u / (u + 1)
    assert encode(x1) == row["x"] and encode(x2) == row["other_x"]
    assert x1 * x2 == alpha**2
    rhs = x1 + b / x1**2
    assert absolute_trace(rhs) == 0
    z = independent_half_trace(rhs)
    point = curve([x1, x1 * z])
    negative = curve([x1, x1 * (z + 1)])
    torsion = curve([0, alpha**2])
    assert negative == -point and 2 * torsion == curve(0)
    assert (point + torsion)[0] == x2
    projected = point + point
    projected += projected
    assert projected == 4 * (point + torsion)
    assert 4 * negative == -projected
    assert projected != curve(0) and ZZ(r) * projected == curve(0)
    assert [encode(projected[0]), encode(projected[1])] == row[
        "projected_point"]
    assert row["verified"] is True


def verify(out_dir):
    started = time.perf_counter_ns()
    config = json.loads(CONFIG.read_text())
    assert sha(ROUTE) == config["route_manifest_sha256"]
    route = json.loads(ROUTE.read_text())
    summary_path = out_dir / "summary.json"
    rows_path = out_dir / "masks.jsonl"
    summary = json.loads(summary_path.read_text())
    assert summary["status"] == "stage_screen_complete"
    assert summary["kind"] == "ecc2k130_degree263_first_descendant_w_rationality_screen"
    assert summary["candidate_id"] is None
    assert summary["route_id"] == route["route_id"] == config["curve_route_id"]
    assert summary["source_curve_id"] == config["source_curve_id"]
    assert summary["target_curve_id"] == config["target_curve_id"]
    assert summary["producer_source_sha256"] == sha(PRODUCER)
    assert summary["inputs_sha256"] == {
        "CONFIG.json": sha(CONFIG), "runtime-info.json": sha(RUNTIME),
        str(ROUTE.relative_to(ROOT)): sha(ROUTE)}
    assert summary["masks_file"] == rows_path.name
    assert summary["masks_sha256"] == sha(rows_path)
    assert all(summary[key] is None for key in (
        "actual_factor_base_B", "effective_matrix_columns", "natural_relation_yield",
        "implicit_pdp_cost", "independent_relation_rank",
        "complete_index_calculus_cost", "matched_rho_cost", "speedup_over_rho"))

    polynomial_ring = PolynomialRing(GF(2), "t")
    t = polynomial_ring.gen()
    field = GF(2**131, "t", modulus=t**131 + t**13 + t**2 + t + 1)
    coeffs = [decode(field, t, value) for value in route["curve_nodes"][
        "target"]["coefficients_a1_a2_a3_a4_a6"]]
    assert coeffs[:3] == [1, 0, 0]
    b = coeffs[4] + coeffs[3]**2
    alpha = b
    for _ in range(129):
        alpha = alpha**2
    assert alpha**4 == b
    assert encode(b) == summary["normalized_descendant_b"]
    assert encode(alpha) == summary["normalized_descendant_alpha"]
    source = EllipticCurve(field, [1, 0, 0, 0, 1])
    descendant = EllipticCurve(field, [1, 0, 0, 0, b])
    r = int(route["curve_nodes"]["source"]["subgroup_order"])
    assert r == summary["subgroup_order"]
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    assert len(rows) == len(config["dimensions"]) * config["samples_per_dimension"]
    assert len(summary["cells"]) == len(config["dimensions"])
    cursor = 0
    checked_points = 0
    for d, cell in zip(config["dimensions"], summary["cells"]):
        assert cell["dimension"] == d and cell["sample_count"] == config[
            "samples_per_dimension"]
        # Rebuild every basis word as a polynomial-basis integer first, then
        # form each w by XOR. The producer adds Sage field elements instead.
        words = []
        for j in range(1, d + 1):
            power = field.gen()**j
            words.append(encode(power) ^ absolute_trace(power))
        assert len(set(words)) == d
        masks = independent_masks(config["seed_domain"], d,
                                  config["samples_per_dimension"])
        assert hashlib.sha256(b"".join(
            x.to_bytes(8, "little") for x in masks)).hexdigest() == cell[
                "masks_sha256"]
        positives = {"source": [], "descendant": []}
        counts = {"source": 0, "descendant": 0,
                  "source_only": 0, "descendant_only": 0}
        for expected_mask in masks:
            row = rows[cursor]
            cursor += 1
            assert row["dimension"] == d and row["mask"] == expected_mask
            word = 0
            for j, basis_word in enumerate(words):
                if expected_mask & (1 << j):
                    word ^= basis_word
            assert word != 0
            w = decode(field, t, word)
            assert absolute_trace(w) == 0
            inverse = 1 / w
            source_ok = bool(absolute_trace(inverse) == 0)
            descendant_ok = bool(absolute_trace(alpha * inverse) == 0)
            assert row["source"] is source_ok
            assert row["descendant"] is descendant_ok
            counts["source"] += int(source_ok)
            counts["descendant"] += int(descendant_ok)
            counts["source_only"] += int(source_ok and not descendant_ok)
            counts["descendant_only"] += int(descendant_ok and not source_ok)
            for name, active in (("source", source_ok),
                                 ("descendant", descendant_ok)):
                if active and len(positives[name]) < config[
                        "full_point_controls_per_curve_and_dimension"]:
                    positives[name].append((expected_mask, w))
        assert counts == cell["counts"]
        n = cell["sample_count"]
        delta = (counts["descendant_only"] - counts["source_only"]) / n
        discordance = (counts["descendant_only"] + counts["source_only"]) / n
        width = 1.96 * sqrt(max(0.0, discordance - delta**2) / n)
        paired = cell["paired_descendant_minus_source"]
        assert paired["descendant_only"] == counts["descendant_only"]
        assert paired["source_only"] == counts["source_only"]
        for key, expected in (("difference", delta), ("lower_95", delta - width),
                              ("upper_95", delta + width)):
            assert isclose(paired[key], expected, rel_tol=0, abs_tol=1e-15)
        threshold = float(config["material_gain_threshold"])
        decision = ("material_gain" if delta - width > threshold else
                    "no_material_gain" if delta + width < threshold else
                    "inconclusive")
        assert cell["decision"] == decision
        bound = cell["capacity"]
        m = SMALL_ARITY[d]
        b_max = 2 * (2**d - 1)
        ways = comb(b_max + m - 1, m)
        denominator = r - 1
        assert bound["dimension"] == d and bound["summands"] == m
        assert bound["projected_base_B_upper"] == b_max
        assert bound["support_numerator_upper"] == min(ways, denominator)
        assert bound["support_denominator"] == denominator
        assert bound["below_one_percent"] is (100 * ways < denominator)
        with localcontext() as context:
            context.prec = 40
            expected = Decimal(min(ways, denominator)) / Decimal(denominator)
        assert Decimal(bound["uniform_nonidentity_support_upper"]) == expected
        for name, curve, root, curve_b in (
                ("source", source, field.one(), field.one()),
                ("descendant", descendant, alpha, b)):
            archived = cell["point_controls"][name]
            assert len(archived) == len(positives[name]) == config[
                "full_point_controls_per_curve_and_dimension"]
            for (mask, w), control in zip(positives[name], archived):
                assert control["mask"] == mask
                recheck_point(curve, root, curve_b, r, w, control)
                checked_points += 1
    assert cursor == len(rows)
    receipt = {"verified": True, "row_count": cursor,
               "point_controls_verified": checked_points,
               "summary_sha256": sha(summary_path), "masks_sha256": sha(rows_path),
               "producer_source_sha256": sha(PRODUCER),
               "verifier_source_sha256": sha(Path(__file__)),
               "wall_ns": time.perf_counter_ns() - started}
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "verification output is write-once"
    receipt = verify(args.run_dir)
    with args.out.open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"verified": receipt["verified"],
                      "row_count": receipt["row_count"],
                      "point_controls_verified": receipt["point_controls_verified"]}))


if __name__ == "__main__":
    main()
