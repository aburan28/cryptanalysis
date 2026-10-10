#!/usr/bin/env python3
"""Independent Sage audit of N41 source lifts and compact bucket roots."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return sum(int(c) << i for i, c in enumerate(value.polynomial()))


def lift(F, value):
    t = F.gen()
    result = F.zero()
    i = 0
    while value:
        if value & 1:
            result += t**i
        value >>= 1
        i += 1
    return result


def coordinate(values, mask):
    return sum((values[i] for i in range(len(values)) if mask >> i & 1),
               values[0].parent().zero())


def source_points(E, F, rows, half_basis):
    out = []
    for row in rows:
        u = coordinate(half_basis, row[3]) + row[4]
        raw_x = F.one() + 1/u
        projected = E(lift(F, row[0]), lift(F, row[1]))
        candidates = [P for P in E.lift_x(raw_x, all=True) if 4*P == projected]
        if len(candidates) != 1:
            raise AssertionError("source lift is not unique")
        out.append(candidates[0])
    return out


def pair_buckets(points, rows):
    groups = {s: {} for s in range(1, 64)}
    for i, left in enumerate(points):
        for j in range(i+1, len(points)):
            if rows[i][2] == rows[j][2]:
                continue
            s = rows[i][3] ^ rows[j][3]
            total = left + points[j]
            groups[s].setdefault(encode(total[0]), []).append(total)
    return groups


def main():
    output = HERE / "sage_audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "protocol_v3.json").read_text())
    if sha(GEOMETRY) != protocol["sha256"]["geometry"]:
        raise ValueError("geometry receipt changed")
    result = json.loads((HERE / "result.json").read_text())
    if result["source_sha256"] != protocol["sha256"]["source"]:
        raise ValueError("producer receipt changed")
    binary = PolynomialRing(GF(2), "t")
    t0 = binary.gen()
    F = GF(2**41, "t", modulus=t0**41+t0**3+1)
    E = EllipticCurve(F, [1, 0, 0, 0, 1])
    ring = PolynomialRing(F, "B")
    B = ring.gen()
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    source = geometry["point_rows_by_unique_rotation"]
    bases = [[lift(F, v) for v in row] for row in geometry["window_basis_halftrace"]]
    left_points = source_points(E, F, source["20"], bases[2])
    right_points = source_points(E, F, source["30"], bases[3])
    left = pair_buckets(left_points, source["20"])
    right = pair_buckets(right_points, source["30"])
    right_polynomials = {}
    checked_outputs = 0
    for s in range(1, 64):
        us = coordinate(bases[3], s)
        ws = us**2+us
        w = [v**2+v for v in bases[3]]
        p_values = {coordinate(w, a)**2+ws*coordinate(w, a)
                    for a in range(64)}
        if len(p_values) != 32:
            raise AssertionError("seed-sum product image dimension changed")
        polynomial = ring.one()
        for p in p_values:
            polynomial *= (1+p)*B**2+p*B+us**2
        for raw_x in right[s]:
            z = 1/(lift(F, raw_x)+1)
            if polynomial(z):
                raise AssertionError("exact right output missed")
            checked_outputs += 1
        right_polynomials[s] = polynomial
    if checked_outputs != 978:
        raise AssertionError("right output census changed")
    positive_hit = result["cases"][0]["hits"][0]
    a = lift(F, positive_hit["a"])
    b = lift(F, positive_hit["exact_b"][0])
    positive = protocol["positive_residual"]
    projected = E(lift(F, positive[0]), lift(F, positive[1]))
    inverse_four = pow(4, -1, geometry["subgroup_order"])
    torsion = E(F.one(), F.zero())
    if 4*torsion != E(0):
        raise AssertionError("torsion generator changed")
    raw_target = inverse_four*projected + positive_hit["target_preimage"]*torsion
    if 4*raw_target != projected:
        raise AssertionError("target preimage changed")
    if not any(lp+rp == raw_target
               for lp in left[positive_hit["left_sum"]][positive_hit["a"]]
               for rp in right[positive_hit["right_sum"]][positive_hit["exact_b"][0]]):
        raise AssertionError("positive hit has no group lift")
    # Independently eliminate the right coordinate for the selected left output.
    z_a = 1/(a+1)
    checks = 0
    positive_gcd_sums = []
    for option in range(4):
        raw_option = inverse_four*projected + option*torsion
        z_t = 1/(raw_option[0]+1)
        C = (z_a**2+z_a)*(z_t**2+z_t)
        D = (z_a+z_t)**2
        s3 = (1+C)*B**2+C*B+D
        for s in range(1, 64):
            if s3.gcd(right_polynomials[s]).degree() > 0:
                positive_gcd_sums.append([option, s])
            checks += 1
    if positive_gcd_sums != [[positive_hit["target_preimage"],
                              positive_hit["right_sum"]]]:
        raise AssertionError("independent polynomial GCD differs from compact norm")
    audit = {"status": "PASS", "source_sha256": sha(Path(__file__)),
             "protocol_sha256": sha(HERE / "protocol_v3.json"),
             "result_sha256": sha(HERE / "result.json"),
             "geometry_sha256": sha(GEOMETRY),
             "source_lifts_checked": len(left_points)+len(right_points),
             "right_pair_outputs_checked": checked_outputs,
             "positive_group_lift": True,
             "independent_gcd_checks": checks,
             "positive_gcd_sums": positive_gcd_sums}
    with output.open("x") as stream:
        json.dump(audit, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(audit))


if __name__ == "__main__":
    main()
