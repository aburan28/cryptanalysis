#!/usr/bin/env python3
"""Compact seed-sum subspace resultant for a target-conditioned S3 link."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
PRIOR = BASE / "n41_seed_sum_s3_bucket_norm_20261010/result.json"
ARITHMETIC = BASE / "n131_w14_s3_prefix_rank_20261010/run.py"
sys.path.insert(0, str(ARITHMETIC.parent))
import run as arithmetic  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coordinate(basis, mask):
    out = 0
    for i, value in enumerate(basis):
        if mask >> i & 1:
            out ^= value
    return out


def linearized_eval(f, coefficients, x):
    out = 0
    power = x
    for coefficient in coefficients:
        out ^= f.mul(coefficient, power)
        power = f.mul(power, power)
    return out


def independent(columns):
    pivots = {}
    output = []
    for column in columns:
        reduced = column
        while reduced:
            bit = reduced.bit_length() - 1
            if bit not in pivots:
                pivots[bit] = reduced
                output.append(column)
                break
            reduced ^= pivots[bit]
    return output


def subspace_polynomial(f, basis):
    # S_V(X) = product_{v in V}(X+v).  Adding one basis vector doubles V.
    coefficients = [1]
    for vector in basis:
        value = linearized_eval(f, coefficients, vector)
        if not value:
            raise AssertionError("dependent subspace basis")
        next_coefficients = [0] * (len(coefficients) + 1)
        for i, coefficient in enumerate(coefficients):
            next_coefficients[i] ^= f.mul(value, coefficient)
            next_coefficients[i+1] ^= f.mul(coefficient, coefficient)
        coefficients = next_coefficients
    return coefficients


def quadratic_norm_zero(f, coefficients, h0, h1, h2):
    """Test whether H(p) has a root in V, using S_V modulo H."""
    if not h2:
        if not h1:
            return not h0
        return linearized_eval(f, coefficients, f.mul(h0, f.inv(h1))) == 0
    inverse = f.inv(h2)
    lam = f.mul(h1, inverse)
    mu = f.mul(h0, inverse)
    a, b = 1, 0  # X^(2^i) = a*X+b modulo X^2+lam*X+mu.
    A = B = 0
    for coefficient in coefficients:
        A ^= f.mul(coefficient, a)
        B ^= f.mul(coefficient, b)
        a2 = f.mul(a, a)
        a, b = f.mul(a2, lam), f.mul(a2, mu) ^ f.mul(b, b)
    # Norm_{F[X]/H / F}(A*X+B); also valid when H splits or has a double root.
    return f.mul(B, B) ^ f.mul(f.mul(A, B), lam) ^ f.mul(f.mul(A, A), mu) == 0


def s3_subspace_hit(f, a, t, u2, coefficients):
    C = f.mul(a ^ f.mul(a, a), t ^ f.mul(t, t))
    D = f.mul(a ^ t, a ^ t)
    alpha = 1 ^ C
    if not alpha:
        # The first S3 polynomial is linear: b+D=0.
        b = D
        p_coefficient = f.mul(b, b) ^ b
        constant = f.mul(b, b) ^ u2
        return quadratic_norm_zero(f, coefficients, constant, p_coefficient, 0)
    m0 = D ^ f.mul(alpha, u2)
    h0 = f.mul(alpha, f.mul(m0, m0)) ^ f.mul(f.mul(C, C), m0 ^ D)
    h1 = f.mul(C, m0 ^ f.mul(C, D))
    h2 = f.mul(alpha, f.mul(D, D)) ^ f.mul(C, D) ^ D
    return quadratic_norm_zero(f, coefficients, h0, h1, h2)


def pair_x_buckets(f, rows):
    groups = {s: set() for s in range(1, 64)}
    for point, i, j in arithmetic.pair_states(f, rows):
        groups[rows[i][3] ^ rows[j][3]].add(point[0])
    if len(set.union(*groups.values())) != 978:
        raise AssertionError("frozen pair-output domain changed")
    return groups


def scalar_mul(f, scalar, point):
    result = None
    while scalar:
        if scalar & 1:
            result = arithmetic.add(f, result, point)
        point = arithmetic.add(f, point, point)
        scalar >>= 1
    return result


def half_trace(f, value):
    out = 0
    term = value
    for _ in range(21):
        out ^= term
        term = f.mul(f.mul(term, term), f.mul(term, term))
    if f.mul(out, out) ^ out != value:
        raise AssertionError("Artin-Schreier lift failed")
    return out


def source_preimages(f, rows, half_basis):
    raw = []
    for row in rows:
        u = coordinate(half_basis, row[3]) ^ row[4]
        x = 1 ^ f.inv(u)
        rhs = x ^ f.mul(f.inv(x), f.inv(x))
        y = f.mul(x, half_trace(f, rhs))
        matches = [point for point in ((x, y), (x, y ^ x))
                   if scalar_mul(f, 4, point) == tuple(row[:2])]
        if len(matches) != 1:
            raise AssertionError("fourfold source lift failed")
        raw.append([*matches[0], *row[2:]])
    return raw


def target_preimages(f, projected, inverse_four):
    subgroup = scalar_mul(f, inverse_four, projected)
    torsion = (1, 0)
    if scalar_mul(f, 4, torsion) is not None:
        raise AssertionError("order-four point changed")
    options = [arithmetic.add(f, subgroup, scalar_mul(f, j, torsion))
               for j in range(4)]
    if len(set(options)) != 4 or any(
            scalar_mul(f, 4, item) != projected for item in options):
        raise AssertionError("fourfold target fiber changed")
    return options


def main():
    output = HERE / "result.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "protocol_v3.json"
    protocol = json.loads(protocol_path.read_text())
    for name, path in (("source", Path(__file__)), ("geometry", GEOMETRY),
                       ("prior", PRIOR), ("arithmetic", ARITHMETIC)):
        if sha(path) != protocol["sha256"][name]:
            raise ValueError("frozen digest mismatch: " + name)
    f = arithmetic.Field(41, [0, 3])
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    setup_start = time.monotonic_ns()
    inverse_four = pow(4, -1, geometry["subgroup_order"])
    left_source = source_preimages(
        f, geometry["point_rows_by_unique_rotation"]["20"],
        geometry["window_basis_halftrace"][2])
    right_source = source_preimages(
        f, geometry["point_rows_by_unique_rotation"]["30"],
        geometry["window_basis_halftrace"][3])
    left = pair_x_buckets(f, left_source)
    right = pair_x_buckets(f, right_source)
    right_polynomials = {}
    subspace_checks = 0
    for s in range(1, 64):
        w = geometry["window_basis_w"][3]
        u = geometry["window_basis_halftrace"][3]
        ws = coordinate(w, s)
        us = coordinate(u, s)
        if f.mul(us, us) ^ us != ws:
            raise AssertionError("Artin-Schreier basis changed")
        image = independent([f.mul(wi, wi) ^ f.mul(ws, wi) for wi in w])
        if len(image) != 5:
            raise AssertionError("seed-sum image dimension changed")
        coefficients = subspace_polynomial(f, image)
        u2 = f.mul(us, us)
        for raw in right[s]:
            z = f.inv(raw ^ 1)
            z2 = f.mul(z, z)
            if z in (0, 1):
                raise AssertionError("exceptional pair output")
            p = f.mul(z2 ^ u2, f.inv(z2 ^ z))
            if linearized_eval(f, coefficients, p):
                raise AssertionError("exact pair output missed by subspace")
            subspace_checks += 1
        right_polynomials[s] = (u2, coefficients)
    setup_ns = time.monotonic_ns() - setup_start
    cases = []
    for kind in ("positive", "negative"):
        target_options = target_preimages(
            f, tuple(protocol[kind + "_residual"]), inverse_four)
        started = time.monotonic_ns()
        hits = []
        checked = 0
        status = "COMPLETE"
        for option_index, target in enumerate(target_options):
            raw_target = target[0]
            if raw_target == 1:
                raise AssertionError("exceptional raw target coordinate")
            t = f.inv(raw_target ^ 1)
            for left_sum in range(1, 64):
                for raw_a in sorted(left[left_sum]):
                    a = f.inv(raw_a ^ 1)
                    for right_sum in range(1, 64):
                        u2, coefficients = right_polynomials[right_sum]
                        if s3_subspace_hit(f, a, t, u2, coefficients):
                            exact = [raw_b for raw_b in right[right_sum]
                                     if arithmetic.s3(f, raw_a, raw_b, raw_target) == 0]
                            hits.append({"target_preimage": option_index,
                                         "left_sum": left_sum, "right_sum": right_sum,
                                         "a": raw_a, "exact_b": exact})
                        checked += 1
                if time.monotonic_ns() - started > protocol["case_wall_cap_seconds"] * 10**9:
                    status = "CENSORED_TIME"
                    break
            if status != "COMPLETE":
                break
        elapsed_ns = time.monotonic_ns() - started
        cases.append({"kind": kind, "status": status, "checked_left_output_right_bucket": checked,
                      "subspace_hits": len(hits), "hits": hits,
                      "online_wall_ns": elapsed_ns})
    result = {"status": "COMPLETE_DIAGNOSTIC" if all(x["status"] == "COMPLETE" for x in cases)
              else "CENSORED_DIAGNOSTIC", "proposal_id": protocol["proposal_id"],
              "candidate_id": None, "target_count": 0,
              "source_sha256": sha(Path(__file__)), "protocol_sha256": sha(protocol_path),
              "setup_ns": setup_ns, "exact_right_output_checks": subspace_checks,
              "subspace_coefficient_count": 6, "cases": cases,
              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss *
              (1 if sys.platform == "darwin" else 1024)}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "cases": [
        {"kind": x["kind"], "status": x["status"], "hits": x["subspace_hits"],
         "checked": x["checked_left_output_right_bucket"], "wall_s": round(x["online_wall_ns"]/1e9, 3)}
        for x in cases]}))


if __name__ == "__main__":
    main()
