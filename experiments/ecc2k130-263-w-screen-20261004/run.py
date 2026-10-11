#!/usr/bin/env sage -python
"""Frozen paired rationality and exact capacity screen for the 263-descendant."""

import argparse
from decimal import Decimal, localcontext
import hashlib
import json
from math import comb, sqrt
from pathlib import Path
import resource
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"
RUNTIME = HERE / "runtime-info.json"
LOWER_ARITY = {24: 5, 28: 4, 35: 3}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def masks(domain, d, count):
    """Unbiased fixed-domain rejection sampler, then reject duplicate masks."""
    span = (1 << d) - 1
    limit = ((1 << 256) // span) * span
    seen = set()
    counter = 0
    while len(seen) < count:
        message = f"{domain}|d={d}|counter={counter}".encode("ascii")
        counter += 1
        candidate = int.from_bytes(hashlib.sha256(message).digest(), "big")
        if candidate >= limit:
            continue
        mask = 1 + candidate % span
        if mask not in seen:
            seen.add(mask)
            yield mask


def basis_rank(words):
    pivots = {}
    for word in words:
        value = word
        while value:
            bit = value.bit_length() - 1
            if bit not in pivots:
                pivots[bit] = value
                break
            value ^= pivots[bit]
    return len(pivots)


def half_trace(value, n=131):
    result = value
    term = value
    for _ in range((n - 1) // 2):
        term = term**4
        result += term
    assert result**2 + result == value
    return result


def point_control(curve, alpha, b, r, mask, w):
    assert w and w.trace() == 0
    u = half_trace(w)
    assert u not in (0, 1)
    x = alpha * (1 + 1 / u)
    other_x = alpha * (1 + 1 / (u + 1))
    assert x * other_x == alpha**2
    rhs = x + b / x**2
    assert rhs.trace() == 0
    z = half_trace(rhs)
    p = curve([x, x * z])
    p_neg = curve([x, x * (z + 1)])
    assert p_neg == -p
    torsion = curve([0, alpha**2])
    assert not torsion.is_zero() and 2 * torsion == curve(0)
    translated = p + torsion
    assert translated[0] == other_x
    projected = 4 * p
    assert projected == 4 * translated and 4 * p_neg == -projected
    assert not projected.is_zero() and r * projected == curve(0)
    return {"mask": mask, "x": encode(x), "other_x": encode(other_x),
            "projected_point": [encode(projected[0]), encode(projected[1])],
            "verified": True}


def paired_interval(descendant_only, source_only, n):
    delta = (descendant_only - source_only) / n
    discordance = (descendant_only + source_only) / n
    se = sqrt(max(0.0, discordance - delta * delta) / n)
    return {"difference": delta, "lower_95": delta - 1.96 * se,
            "upper_95": delta + 1.96 * se, "descendant_only": descendant_only,
            "source_only": source_only}


def capacity(d, r):
    m = LOWER_ARITY[d]
    b_max = 2 * ((1 << d) - 1)
    ways = comb(b_max + m - 1, m)
    denominator = r - 1
    with localcontext() as context:
        context.prec = 40
        ratio = str(Decimal(min(ways, denominator)) / Decimal(denominator))
    return {"dimension": d, "summands": m, "projected_base_B_upper": b_max,
            "support_numerator_upper": min(ways, denominator),
            "support_denominator": denominator,
            "uniform_nonidentity_support_upper": ratio,
            "below_one_percent": ways * 100 < denominator}


def peak_rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Darwin reports bytes; Linux reports KiB.
    import sys
    return int(value if sys.platform == "darwin" else value * 1024)


def produce(out_dir):
    started = time.perf_counter_ns()
    config = json.loads(CONFIG.read_text())
    assert digest(ROUTE) == config["route_manifest_sha256"]
    route = json.loads(ROUTE.read_text())
    assert route["route_id"] == config["curve_route_id"]
    assert route["field"]["p"] == 2 and route["field"]["n"] == 131
    assert route["field"]["defining_modulus_low_terms"] == [0, 1, 2, 13, 131]
    assert route["curve_nodes"]["source"]["curve_id"] == config["source_curve_id"]
    assert route["curve_nodes"]["target"]["curve_id"] == config["target_curve_id"]
    assert RUNTIME.exists(), "save checked Sage --runtime-info before the run"
    r = int(route["curve_nodes"]["source"]["subgroup_order"])
    assert r == int(route["curve_nodes"]["target"]["subgroup_order"])

    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "t", modulus=t**131 + t**13 + t**2 + t + 1)

    def decode(value):
        value = int(value)
        return field(sum(t**i for i in range(value.bit_length()) if value & (1 << i)))

    source = EllipticCurve(field, [1, 0, 0, 0, 1])
    target_coeffs = [decode(x) for x in route["curve_nodes"]["target"][
        "coefficients_a1_a2_a3_a4_a6"]]
    assert target_coeffs[:3] == [1, 0, 0]
    target = EllipticCurve(field, target_coeffs)
    a4, a6 = target_coeffs[3:]
    b = a6 + a4**2
    alpha = b ** (1 << 129)
    assert alpha**4 == b
    normalized = EllipticCurve(field, [1, 0, 0, 0, b])
    for name, curve in (("source", source), ("target", target)):
        node = route["curve_nodes"][name]
        g = curve([decode(x) for x in node["generator_G"]])
        assert not g.is_zero() and ZZ(r) * g == curve(0)
        if name == "target":
            g_normalized = normalized([g[0], g[1] + a4])
            assert ZZ(r) * g_normalized == normalized(0)
    setup_ns = time.perf_counter_ns() - started

    rows_path = out_dir / "masks.jsonl"
    cells = []
    with rows_path.open("x") as stream:
        for d in config["dimensions"]:
            phase_start = time.perf_counter_ns()
            basis = [field.gen()**j + field((field.gen()**j).trace())
                     for j in range(1, d + 1)]
            assert basis_rank([encode(v) for v in basis]) == d
            counts = {"source": 0, "descendant": 0, "source_only": 0,
                      "descendant_only": 0}
            controls = {"source": [], "descendant": []}
            mask_words = []
            for mask in masks(config["seed_domain"], d,
                              config["samples_per_dimension"]):
                mask_words.append(mask)
                w = field.zero()
                remaining = mask
                while remaining:
                    bit = remaining & -remaining
                    w += basis[bit.bit_length() - 1]
                    remaining ^= bit
                assert w and w.trace() == 0
                inverse = 1 / w
                source_ok = (inverse.trace() == 0)
                descendant_ok = ((alpha * inverse).trace() == 0)
                counts["source"] += int(source_ok)
                counts["descendant"] += int(descendant_ok)
                counts["source_only"] += int(source_ok and not descendant_ok)
                counts["descendant_only"] += int(descendant_ok and not source_ok)
                stream.write(json.dumps({"dimension": d, "mask": mask,
                                         "source": bool(source_ok),
                                         "descendant": bool(descendant_ok)},
                                        sort_keys=True, separators=(",", ":")) + "\n")
                if source_ok and len(controls["source"]) < config[
                        "full_point_controls_per_curve_and_dimension"]:
                    controls["source"].append(point_control(source, field.one(),
                                                            field.one(), ZZ(r), mask, w))
                if descendant_ok and len(controls["descendant"]) < config[
                        "full_point_controls_per_curve_and_dimension"]:
                    controls["descendant"].append(point_control(
                        normalized, alpha, b, ZZ(r), mask, w))
                if len(mask_words) % 256 == 0:
                    assert (time.perf_counter_ns() - started) < config[
                        "max_wall_seconds"] * 1_000_000_000, "wall cap exceeded"
                    assert peak_rss_bytes() <= config["max_peak_rss_bytes"], "RSS cap exceeded"
            assert all(len(v) == config["full_point_controls_per_curve_and_dimension"]
                       for v in controls.values())
            interval = paired_interval(counts["descendant_only"],
                                       counts["source_only"], len(mask_words))
            threshold = float(config["material_gain_threshold"])
            cells.append({"dimension": d, "sample_count": len(mask_words),
                          "masks_sha256": hashlib.sha256(b"".join(
                              x.to_bytes(8, "little") for x in mask_words)).hexdigest(),
                          "counts": counts, "paired_descendant_minus_source": interval,
                          "decision": ("material_gain" if interval["lower_95"] > threshold
                                       else "no_material_gain" if interval["upper_95"] < threshold
                                       else "inconclusive"),
                          "point_controls": controls, "capacity": capacity(d, r),
                          "phase_wall_ns": time.perf_counter_ns() - phase_start})
            stream.flush()
    summary = {
        "kind": "ecc2k130_degree263_first_descendant_w_rationality_screen",
        "status": "stage_screen_complete", "candidate_id": None,
        "route_id": route["route_id"], "source_curve_id": config["source_curve_id"],
        "target_curve_id": config["target_curve_id"], "field_degree": 131,
        "subgroup_order": r, "normalized_descendant_b": encode(b),
        "normalized_descendant_alpha": encode(alpha),
        "cells": cells, "masks_file": rows_path.name,
        "masks_sha256": digest(rows_path),
        "inputs_sha256": {"CONFIG.json": digest(CONFIG),
                          "runtime-info.json": digest(RUNTIME),
                          str(ROUTE.relative_to(ROOT)): digest(ROUTE)},
        "producer_source_sha256": digest(Path(__file__)),
        "setup_wall_ns": setup_ns,
        "total_wall_ns": time.perf_counter_ns() - started,
        "peak_rss_bytes": peak_rss_bytes(),
        "actual_factor_base_B": None, "effective_matrix_columns": None,
        "natural_relation_yield": None, "implicit_pdp_cost": None,
        "independent_relation_rank": None, "complete_index_calculus_cost": None,
        "matched_rho_cost": None, "speedup_over_rho": None,
    }
    with (out_dir / "summary.json").open("x") as stream:
        json.dump(summary, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": summary["status"],
                      "decisions": [(c["dimension"], c["decision"]) for c in cells],
                      "total_wall_ns": summary["total_wall_ns"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=False)
    try:
        produce(args.out_dir)
    except BaseException as error:
        with (args.out_dir / "failure.json").open("x") as stream:
            json.dump({"error_type": type(error).__name__, "message": str(error),
                       "source_sha256": digest(Path(__file__)),
                       "config_sha256": digest(CONFIG)}, stream, indent=2,
                      sort_keys=True)
            stream.write("\n")
        raise


if __name__ == "__main__":
    main()
