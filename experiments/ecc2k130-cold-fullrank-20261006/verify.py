#!/usr/bin/env python3
"""Independent polynomial-basis group, relation, rank, and timing replay."""
import argparse
import gzip
import hashlib
import json
import platform
from pathlib import Path


def file_bytes(path):
    if path.exists():
        return path.read_bytes()
    return gzip.decompress(path.with_suffix(path.suffix + ".gz").read_bytes())


def records(path):
    return [json.loads(line) for line in file_bytes(path).splitlines() if line.strip()]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def only(items, kind, fixture_index=None):
    result = [x for x in items if x.get("kind") == kind and (fixture_index is None or x.get("fixture_index") == fixture_index)]
    if len(result) != 1:
        raise AssertionError((kind, fixture_index, len(result)))
    return result[0]


def field(n, terms):
    modulus = (1 << n) | sum(1 << int(t) for t in terms)
    mask = (1 << n) - 1

    def reduce(a):
        while a.bit_length() > n:
            a ^= modulus << (a.bit_length() - n - 1)
        return a

    def mul(a, b):
        z = 0
        while b:
            if b & 1:
                z ^= a
            b >>= 1
            a <<= 1
            if a & (1 << n):
                a ^= modulus
        return z & mask

    def inv(a):
        if not a:
            raise ZeroDivisionError
        u, v, g1, g2 = a, modulus, 1, 0
        while u != 1:
            if not u:
                raise ZeroDivisionError("field modulus reducible")
            shift = u.bit_length() - v.bit_length()
            if shift < 0:
                u, v = v, u
                g1, g2 = g2, g1
                shift = -shift
            u ^= v << shift
            g1 ^= g2 << shift
        return reduce(g1)

    def squaremod(a):
        z = 0
        bit = 0
        while a:
            if a & 1:
                z |= 1 << (2 * bit)
            a >>= 1
            bit += 1
        return reduce(z)

    def gcd(a, b):
        while b:
            a, b = b, remainder(a, b)
        return a

    def remainder(a, b):
        while a.bit_length() >= b.bit_length():
            a ^= b << (a.bit_length() - b.bit_length())
        return a

    # Prime-degree Rabin test; all three frozen field degrees are prime.
    assert all(n % d for d in range(2, int(n**0.5)+1))
    x = 2
    irreducible = gcd(squaremod(x) ^ x, modulus) == 1
    y = x
    for _ in range(n):
        y = squaremod(y)
    irreducible = irreducible and y == x
    return mul, inv, irreducible, modulus


def curve_ops(mul_f, inv_f):
    def on_curve(P):
        if P is None:
            return True
        x, y = P
        return (mul_f(y, y) ^ mul_f(x, y)) == (mul_f(mul_f(x, x), x) ^ 1)

    def add(P, Q):
        if P is None:
            return Q
        if Q is None:
            return P
        x1, y1 = P
        x2, y2 = Q
        if x1 == x2:
            if y1 ^ y2 == x1:
                return None
            if y1 != y2 or x1 == 0:
                raise AssertionError("invalid equal-x points")
            lam = x1 ^ mul_f(y1, inv_f(x1))
            x3 = mul_f(lam, lam) ^ lam
            y3 = mul_f(x1, x1) ^ mul_f(lam ^ 1, x3)
            return x3, y3
        lam = mul_f(y1 ^ y2, inv_f(x1 ^ x2))
        x3 = mul_f(lam, lam) ^ lam ^ x1 ^ x2
        y3 = mul_f(lam, x1 ^ x3) ^ x3 ^ y1
        return x3, y3

    def scalar(k, P):
        R = None
        while k:
            if k & 1:
                R = add(R, P)
            P = add(P, P)
            k >>= 1
        return R

    return on_curve, add, scalar


def rank_replay(rows, modulus):
    pivots = {}
    full_at = None
    for i, receipt in enumerate(rows, 1):
        v = [int(x) % modulus for x in receipt["sparse_row"]]
        for col in sorted(pivots):
            if v[col]:
                multiple = v[col]
                p = pivots[col]
                v = [(x - multiple*y) % modulus for x, y in zip(v, p)]
        if any(v):
            col = next(j for j, x in enumerate(v) if x)
            scale = pow(v[col], -1, modulus)
            pivots[col] = [(x*scale) % modulus for x in v]
        if len(pivots) != int(receipt["rank_after"]):
            raise AssertionError(("rank_after", i, len(pivots), receipt["rank_after"]))
        if len(pivots) == len(v) and full_at is None:
            full_at = i
    return len(pivots), full_at


def is_prime_u64(n):
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, shifts = n - 1, 0
    while not d & 1:
        d >>= 1
        shifts += 1
    for base in (2, 325, 9375, 28178, 450775, 9780504, 1795265022):
        a = base % n
        if not a:
            continue
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(shifts - 1):
            x = x*x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def koblitz_a0_order(n):
    # #E(F2)=4 by direct enumeration; trace t1=-1, t0=2.
    t0, t1 = 2, -1
    for _ in range(2, n + 1):
        t0, t1 = t1, -t1 - 2*t0
    return (1 << n) + 1 - t1


def verify_signed_frobenius_base(points, n, mul_f, scalar, r, expected_orbits):
    remaining = set(points)
    point_set = set(points)
    orbits = 0
    while remaining:
        representative = min(remaining)
        assert scalar(r, representative) is None
        member = representative
        orbit = set()
        for _ in range(n):
            orbit.add(member)
            orbit.add((member[0], member[1] ^ member[0]))
            member = (mul_f(member[0], member[0]), mul_f(member[1], member[1]))
        assert member == representative and orbit <= point_set
        remaining.difference_update(orbit)
        orbits += 1
    assert orbits == expected_orbits
    return orbits


def verify_cell(run, n):
    decision = json.loads((run / f"n{n}-decision.json").read_text())
    direct_resource = json.loads((run / f"n{n}-direct.resource.json").read_text())
    build = json.loads((run / "BUILD.json").read_text())
    assert decision["direct"] == direct_resource
    assert direct_resource["binary_sha256"] == build["binary_hashes"]["rank"]
    assert direct_resource["rss_cap_bytes"] == 17179869184
    assert sha(file_bytes(run / f"n{n}-direct.stderr.txt")) == direct_resource["stderr_sha256"]
    direct_raw = file_bytes(run / f"n{n}-direct.stdout.jsonl")
    assert sha(direct_raw) == direct_resource["stdout_sha256"]
    base = {"n": n, "producer_status": decision["status"], "direct_resource": {k: direct_resource[k] for k in ("exit_code", "timed_out", "memory_cap_exceeded", "rss_monitor_error", "whole_process_wall_ms", "child_peak_rss_bytes", "peak_sampled_rss_bytes")}, "direct_stdout_sha256": sha(direct_raw), "candidate_id": None, "controlled_speedup": None}
    if decision["status"] == "DIRECT_FAILED":
        assert n == 53 and direct_resource["timed_out"] and direct_resource["exit_code"] == -9
        assert not direct_raw and not (run / f"n{n}-rho.resource.json").exists()
        base["status"] = "CENSORED_DIRECT_TIMEOUT_NO_TARGET"
        return base
    direct = records(run / f"n{n}-direct.stdout.jsonl")
    rho_resource = json.loads((run / f"n{n}-rho.resource.json").read_text())
    assert decision["rho"] == rho_resource
    assert rho_resource["binary_sha256"] == build["binary_hashes"]["rho"]
    assert rho_resource["rss_cap_bytes"] == 17179869184
    assert sha(file_bytes(run / f"n{n}-rho.stderr.txt")) == rho_resource["stderr_sha256"]
    rho_raw = file_bytes(run / f"n{n}-rho.stdout.jsonl")
    assert sha(rho_raw) == rho_resource["stdout_sha256"]
    rho = only(records(run / f"n{n}-rho.stdout.jsonl"), "rho_public_fixture")
    factor = only(direct, "point_defined_factor_base")
    pre = only(direct, "relation_rank_summary", 0)
    target = only(direct, "relation_rank_summary", 1)
    mul_f, inv_f, irreducible, field_modulus = field(n, rho["field_modulus_low_terms"])
    on_curve, add, scalar = curve_ops(mul_f, inv_f)
    G = tuple(rho["generator"])
    Q0 = tuple(pre["published_q"])
    Q1 = tuple(target["published_q"])
    r = int(rho["subgroup_order"])
    points = [tuple(P) for P in factor["factor_base_point_coordinates"]]
    assert len(points) == factor["factor_base_points"] == target["factor_base_points"]
    assert len(points) == len(set(points))
    assert all(on_curve(P) for P in points)
    assert irreducible and on_curve(G) and on_curve(Q0) and on_curve(Q1)
    assert is_prime_u64(r)
    assert koblitz_a0_order(n) == r * int(factor["cofactor"])
    assert scalar(r, G) is None
    independently_checked_orbits = verify_signed_frobenius_base(points, n, mul_f, scalar, r, factor["orbit_columns"])
    assert scalar(int(pre["recovered_fixture_scalar"]), G) == Q0
    assert scalar(int(target["recovered_fixture_scalar"]), G) == Q1
    assert scalar(int(rho["recovered_fixture_scalar"]), G) == Q1
    assert rho["published_q"] == target["published_q"] and rho["verified"]
    relations = [x for x in direct if x.get("kind") == "relation_rank_receipt"]
    relation_counts = {}
    ranks = {}
    for summary, Q in ((pre, Q0), (target, Q1)):
        rows_ = [x for x in relations if x["fixture_seed"] == summary["fixture_seed"]]
        assert len(rows_) == summary["admitted_relations"]
        logs = pre["factor_base_log_solution"]
        assert len(logs) + 1 == summary["matrix_columns"]
        for receipt in rows_:
            indices = receipt["factor_point_indices"]
            L = None
            for index in indices:
                L = add(L, points[index])
            R = add(scalar(int(receipt["coefficient_a"]), G), scalar(int(receipt["coefficient_b"]), Q))
            assert L == R, (n, summary["fixture_index"], receipt["accepted_relation"], "group")
            values = receipt["sparse_row"]
            assert len(values) == len(logs)+1
            left = sum(int(a)*int(b) for a,b in zip(values[:-1],logs)) + int(values[-1])*int(summary["recovered_fixture_scalar"])
            assert left % r == int(receipt["coefficient_a"]) % r, (n, summary["fixture_index"], receipt["accepted_relation"], "linear")
        rank, full_at = rank_replay(rows_, r)
        assert rank == summary["terminal_rank"] and full_at == summary["full_rank_at_relation"]
        relation_counts[str(summary["fixture_index"])] = len(rows_)
        ranks[str(summary["fixture_index"])] = rank
    points_digest = sha(json.dumps(points, separators=(",", ":")).encode())
    online = target["target_online_phase_ms"]
    raw_phase_sum = sum(float(v) for v in online.values())
    assert abs(raw_phase_sum - target["target_online_wall_ms"]) < 1e-6
    # Producer source lines 2284 and 2851-2920 show collection_ms spans LA
    # and solution validation. The published online phase re-adds both.
    overlap = target["linear_solve_ms"] + target["solution_validation_ms"]
    online_exclusive = target["target_online_wall_ms"] - overlap
    assert abs(online_exclusive - (target["fixture_setup_ms"] + target["collection_ms"] + target["reference_validation_ms"])) < 1e-6
    pre_exclusive = pre["fixture_setup_ms"] + pre["collection_ms"] + pre["reference_validation_ms"]
    cold_exclusive = target["curve_setup_ms"] + target["setup_ms"] + pre_exclusive + online_exclusive
    assert rho["published_fixture_scalar"] == target["published_fixture_scalar"]
    rho_online = rho["walk_ms"] + rho["validation_ms"]
    online_exclusive_phases = {
        "target_query": target["fixture_setup_ms"],
        "target_pdp": target["collection_ms"] - target["linear_solve_ms"] - target["solution_validation_ms"],
        "target_relation_check": target["reference_validation_ms"],
        "target_descent": 0.0,
        "target_recovery_check": overlap,
    }
    assert abs(sum(online_exclusive_phases.values()) - online_exclusive) < 1e-6
    cold_exclusive_phases = {
        "curve_setup": target["curve_setup_ms"],
        "factor_base_construction": factor["base_construction_ms"],
        "support_index": factor["support_index_ms"],
        "other_shared_setup": target["setup_ms"] - factor["base_construction_ms"] - factor["support_index_ms"],
        "precompute_query": pre["fixture_setup_ms"],
        "precompute_pdp_and_incremental_rank": pre["collection_ms"] - pre["linear_solve_ms"] - pre["solution_validation_ms"],
        "precompute_final_la": pre["linear_solve_ms"],
        "precompute_solution_check": pre["solution_validation_ms"],
        "precompute_relation_check": pre["reference_validation_ms"],
        **online_exclusive_phases,
    }
    assert abs(sum(cold_exclusive_phases.values()) - cold_exclusive) < 1e-6
    base.update({
        "status": "PASS_INDEPENDENT_GROUP_ROW_RANK_SCALAR_REPLAY",
        "field_modulus": field_modulus,
        "factor_base_points": len(points),
        "factor_base_point_list_sha256": points_digest,
        "factor_base_representative_hash": factor["base_hash"],
        "orbit_columns": factor["orbit_columns"],
        "independently_checked_subgroup_orbits": independently_checked_orbits,
        "curve_order_by_trace_recurrence": koblitz_a0_order(n),
        "subgroup_order_prime_verified": True,
        "matrix_columns": pre["matrix_columns"],
        "relations_by_fixture": relation_counts,
        "replayed_rank_by_fixture": ranks,
        "public_target": list(Q1),
        "recovered_scalar": target["recovered_fixture_scalar"],
        "rho_resource": {k: rho_resource[k] for k in ("exit_code", "timed_out", "memory_cap_exceeded", "rss_monitor_error", "whole_process_wall_ms", "child_peak_rss_bytes")},
        "rho_stdout_sha256": sha(rho_raw),
        "timing_exploratory_ms": {
            "curve_setup": target["curve_setup_ms"],
            "factor_base_and_support_index": target["setup_ms"],
            "full_rank_log_preparation_exclusive": pre_exclusive,
            "online_target_as_published_with_overlap": target["target_online_wall_ms"],
            "online_overlap_linear_solve_and_validation": overlap,
            "online_target_exclusive_corrected": online_exclusive,
            "cold_one_target_exclusive_corrected": cold_exclusive,
            "rho_online": rho_online,
        },
        "online_exclusive_phase_ms": online_exclusive_phases,
        "cold_exclusive_phase_ms": cold_exclusive_phases,
        "timing_overlap_note": "Published target_pdp=collection_ms spans linear solve and solution validation; published target_recovery_check adds those same durations again. Exclusive online removes that overlap. A finer exclusive split requires producer instrumentation.",
    })
    return base


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    result = {"schema_version": 1, "method": "independent pure-Python GF(2^n) group law; every base point on-curve, every relation group and modular-row replay, independent rank, scalar replay", "platform": platform.platform(), "cells": [verify_cell(args.run_dir, n) for n in (37, 41, 53)]}
    result["status"] = "PASS_WITH_CENSORED_N53" if [x["status"] for x in result["cells"]] == ["PASS_INDEPENDENT_GROUP_ROW_RANK_SCALAR_REPLAY"]*2+["CENSORED_DIRECT_TIMEOUT_NO_TARGET"] else "FAIL"
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(result["status"])
    if result["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
