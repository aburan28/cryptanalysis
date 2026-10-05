#!/usr/bin/env python3
"""Bounded pair-table control on Q1438's exact N53/N83 factor bases."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import resource
import sys
import time
from pathlib import Path

from build_n53_base import HERE, PARENT, read_points, sha

sys.path.insert(0, str(PARENT))
from run_probe import ROOT, curves, field  # noqa: E402

sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402


PROTOCOL = HERE / "protocol.json"
RUNS = HERE / "runs"


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def workload_id(workload):
    return hashlib.sha256(canonical_json(workload)).hexdigest()[:12]


class FullBaseSampler:
    """Uniform points of the exact N83 W<=6 projected base by rejection.

    Q1438 proved every accepted raw x orbit is full length and has a unique
    projected x orbit. Uniform raw masks, rejection of nonusable x, and a
    random sign therefore give a uniform point of its complete base.
    """

    def __init__(self, onb, curve, cofactor, weight, rng):
        self.onb = onb
        self.curve = curve
        self.cofactor = cofactor
        self.rng = rng
        self.weight_counts = [math.comb(onb.m, k)
                              for k in range(1, weight + 1)]
        self.total = sum(self.weight_counts)
        self.draws = 0
        self.nonrational = 0
        self.identity_projection = 0
        self.accepted = 0
        self.certificates = {}

    def point(self):
        while True:
            self.draws += 1
            draw = self.rng.randrange(self.total)
            for weight, count in enumerate(self.weight_counts, start=1):
                if draw < count:
                    break
                draw -= count
            mask = sum(1 << j for j in self.rng.sample(range(self.onb.m),
                                                       weight))
            raw = self.curve.pointFromX(self.onb.fromCoords(mask))
            if raw is None:
                self.nonrational += 1
                continue
            projected = self.curve.mul(raw, self.cofactor)
            if projected is None:
                self.identity_projection += 1
                continue
            sign_bit = self.rng.getrandbits(1)
            if sign_bit:
                projected = self.curve.neg(projected)
            self.accepted += 1
            self.certificates.setdefault(projected, {
                "raw_normal_x_mask": mask, "sign_bit": sign_bit})
            return projected

    def certificate(self, point):
        return self.certificates[point]

    def counters(self):
        return {"raw_x_draws": self.draws,
                "nonrational_x": self.nonrational,
                "identity_projections": self.identity_projection,
                "accepted_points": self.accepted}


class IndexedBaseSampler:
    def __init__(self, points, rng):
        self.points = points
        self.rng = rng
        self.accepted = 0

    def point(self):
        self.accepted += 1
        return self.points[self.rng.randrange(len(self.points))]

    def counters(self):
        return {"indexed_draws": self.accepted,
                "accepted_points": self.accepted}

    def certificate(self, point):
        return None


def reconstruct(curve, orbit, target, zero, one, subgroup_order):
    """Replay a quotient-pair collision and require four distinct columns."""
    p0, p1, exponent0, sign0 = zero
    q0, q1, exponent1, sign1 = one
    shift = (exponent0 - exponent1) % orbit.n
    sign = sign0 * sign1
    left = [curve.frob(p0, shift), curve.frob(p1, shift)]
    if sign < 0:
        left = [curve.neg(point) for point in left]
    points = left + [q0, q1]
    columns = [orbit.canonical(point)[0] for point in points]
    if len(set(columns)) != 4:
        return None
    if not all(curve.onCurve(point) and
               curve.mul(point, subgroup_order) is None for point in points):
        raise AssertionError("collision point left declared subgroup")
    total = None
    for point in points:
        total = curve.add(total, point)
    if total != target:
        raise AssertionError("quotient collision did not replay to target")
    return {"points": [list(point) for point in points],
            "folded_column_keys": columns,
            "frobenius_shift_of_table_pair": shift,
            "sign_of_table_pair": sign}


def check_known_n53_witness(curve, orbit, base, subgroup_order):
    control = json.loads((PARENT /
        "q1439_fixed_leaf/runs/n53_control/receipt.json").read_text())[
            "model_check"]
    assert control["status"] == "verified_four_point_relation"
    target = tuple(control["public_target"])
    signed = []
    base_set = set(base)
    for row, sign in zip(control["projected_points"], control["signs"]):
        point = tuple(row)
        signed.append(curve.neg(point) if sign < 0 else point)
    assert all(point in base_set for point in signed)
    assert len({orbit.canonical(point)[0] for point in signed}) == 4
    zero_pair = curve.add(signed[0], signed[1])
    residual = curve.add(target, curve.neg(curve.add(*signed[2:])))
    assert zero_pair == residual
    _, exponent0, sign0 = orbit.canonical(zero_pair)
    _, exponent1, sign1 = orbit.canonical(residual)
    witness = reconstruct(curve, orbit, target,
                          (signed[0], signed[1], exponent0, sign0),
                          (signed[2], signed[3], exponent1, sign1),
                          subgroup_order)
    assert witness is not None
    return {"status": "pass", "four_distinct_columns": True,
            "public_target": list(target), "points": witness["points"]}


def pair_table(curve, orbit, sampler, samples):
    started = time.perf_counter_ns()
    table = {}
    identity = duplicate_keys = 0
    for _ in range(samples):
        p, q = sampler.point(), sampler.point()
        pair = curve.add(p, q)
        if pair is None:
            identity += 1
            continue
        key, exponent, sign = orbit.canonical(pair)
        if key in table:
            duplicate_keys += 1
        else:
            table[key] = (p, q, exponent, sign)
    return table, {"samples": samples, "distinct_keys": len(table),
                   "duplicate_keys": duplicate_keys,
                   "identity_pairs": identity,
                   "wall_ns": time.perf_counter_ns() - started,
                   "sampler": sampler.counters()}


def query_table(curve, orbit, sampler, table_sampler, table, target,
                subgroup_order,
                sample_cap, wall_cap_ns):
    started = time.perf_counter_ns()
    assert curve.onCurve(target) and curve.mul(target, subgroup_order) is None
    hits = rejected = identity = 0
    relation = None
    status = "sample_cap"
    attempts = 0
    for number in range(1, sample_cap + 1):
        if number == 1 or number % 1024 == 0:
            if time.perf_counter_ns() - started >= wall_cap_ns:
                status = "wall_cap"
                break
        attempts = number
        p, q = sampler.point(), sampler.point()
        pair = curve.add(p, q)
        if pair is None:
            identity += 1
            continue
        residual = curve.add(target, curve.neg(pair))
        if residual is None:
            identity += 1
            continue
        key, exponent, sign = orbit.canonical(residual)
        earlier = table.get(key)
        if earlier is None:
            continue
        hits += 1
        relation = reconstruct(curve, orbit, target, earlier,
                               (p, q, exponent, sign), subgroup_order)
        if relation is not None:
            relation["collision_proof"] = {
                "table_pair_original_points": [list(earlier[0]),
                                               list(earlier[1])],
                "query_pair_original_points": [list(p), list(q)],
                "table_pair_membership_certificates": [
                    table_sampler.certificate(earlier[0]),
                    table_sampler.certificate(earlier[1])],
                "query_pair_membership_certificates": [
                    sampler.certificate(p), sampler.certificate(q)],
                "table_pair_quotient_exponent": earlier[2],
                "table_pair_quotient_sign": earlier[3],
                "residual_quotient_exponent": exponent,
                "residual_quotient_sign": sign,
            }
            status = "verified_four_point_relation"
            break
        rejected += 1
    return {"status": status, "samples": attempts,
            "key_hits": hits, "improper_column_rejections": rejected,
            "identity_or_zero_residual_pairs": identity,
            "wall_ns": time.perf_counter_ns() - started,
            "sampler": sampler.counters(), "relation": relation}


def run(degree):
    protocol = json.loads(PROTOCOL.read_text())
    cell = protocol["cells"][str(degree)]
    output = RUNS / f"n{degree}_ordinary.json"
    assert not output.exists(), "refuse to overwrite measured cell"
    assert protocol["proposal_id"] == "Q1445"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert cell["workload_id"] == workload_id(cell["workload"])
    for name, digest in protocol["source_sha256"].items():
        assert sha(ROOT / name) == digest
    for name, digest in protocol["input_sha256"].items():
        assert sha(ROOT / name) == digest
    assert protocol["sage_runtime_info_sha256"] == sha(
        HERE / "sage_runtime_info.json")
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    base_receipt = json.loads((PARENT / f"q1438_dense_base/n{degree}_w"
                              f"{cell['weight_bound']}_base.json").read_text())
    assert cell["curve_id"] == base_receipt["curve_id"]
    assert cell["factor_base_actual_B"] == base_receipt[
        "actual_usable_points_B_before_folding"]
    assert cell["folded_columns_K"] == base_receipt[
        "signed_frobenius_columns_K"]
    assert cell["factor_base_enumerated_set_sha256"] == base_receipt[
        "enumerated_set_sha256"]
    instance = json.loads((PARENT / "q1438_dense_base/protocol.json").read_text())[
        "instances"][str(degree)]
    assert instance["curve_id"] == cell["curve_id"]
    onb = field.Onb(degree)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    target = tuple(cell["public_target"])
    subgroup_order = instance["subgroup_order"]
    setup_started = time.perf_counter_ns()
    if degree == 53:
        base = read_points()
        assert len(base) == cell["factor_base_actual_B"]
        table_sampler = IndexedBaseSampler(base, random.Random(cell["table_seed"]))
        query_sampler = IndexedBaseSampler(base, random.Random(cell["query_seed"]))
    else:
        base = None
        table_sampler = FullBaseSampler(onb, curve, instance["cofactor"],
                                        cell["weight_bound"],
                                        random.Random(cell["table_seed"]))
        query_sampler = FullBaseSampler(onb, curve, instance["cofactor"],
                                        cell["weight_bound"],
                                        random.Random(cell["query_seed"]))
    setup_ns = time.perf_counter_ns() - setup_started
    control = {"status": "pre_run_pass",
               "validation_sha256": sha(HERE / "validation.json")}
    table, table_result = pair_table(curve, orbit, table_sampler,
                                     cell["table_sample_cap"])
    result = query_table(curve, orbit, query_sampler, table_sampler,
                         table, target,
                         subgroup_order, cell["query_sample_cap"],
                         int(cell["online_wall_cap_seconds"] * 1e9))
    result["online_stage_interval"] = (
        "from target validation after table ready "
        "through verified relation or declared cap; not an ECDLP solve")
    receipt = {
        "proposal_id": "Q1445", "candidate_id": None, "run_id": None,
        "isogeny": "none", "curve_id": cell["curve_id"],
        "workload_id": cell["workload_id"],
        "protocol_sha256": sha(PROTOCOL),
        "target": list(target), "factor_base_actual_B": cell[
            "factor_base_actual_B"],
        "folded_columns_K": cell["folded_columns_K"],
        "factor_base_enumerated_set_sha256": cell[
            "factor_base_enumerated_set_sha256"],
        "factor_base_sampling": cell["factor_base_sampling"],
        "target_independent_base_load_ns": setup_ns,
        "target_independent_table": table_result,
        "ordinary_query": result,
        "known_witness_control": control,
        "verified_relation_count": int(result["relation"] is not None),
        "verified_single_target_dlp": False,
        "complete_n131_log2_work": None,
        "online_single_target_speedup": None,
        "cpu_isolation_receipt": None,
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
    }
    RUNS.mkdir(exist_ok=True)
    output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"degree": degree, "status": result["status"],
                      "table_samples": table_result["samples"],
                      "query_samples": result["samples"],
                      "query_wall_seconds": result["wall_ns"] / 1e9,
                      "verified_relations": receipt["verified_relation_count"],
                      "receipt": str(output)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    run(parser.parse_args().degree)
