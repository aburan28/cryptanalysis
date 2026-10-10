#!/usr/bin/env python3
"""Double-sided reciprocal S3 bucket resultant on the exact N41 curve."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE))
import run_n41_disjoint_s5_sat as old

INPUT = HERE / "input.json"
PROTOCOL = HERE / "protocol.json"
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
R = 549756390943


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def peak_rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def frob(field, point, power):
    x, y = point
    for _ in range(power):
        x, y = field.mul(x, x), field.mul(y, y)
    return x, y


def pow2(field, value, power):
    for _ in range(power):
        value = field.mul(value, value)
    return value


def source_context():
    data = json.loads(GEOMETRY.read_text())["n41"]
    f = old.Field(41, [0, 3])
    curve = old.Curve(f, 0)
    basis = data["window_basis_w"][0]
    halves = data["window_basis_halftrace"][0]
    rows = data["point_rows_by_unique_rotation"]["0"]
    subgroup = {(row[3], row[5]): tuple(row[:2]) for row in rows}
    columns = {row[3]: row[2] for row in rows}
    assert len(subgroup) == 64 and len(columns) == 32
    rotations = [20, 30]
    atom_bases = [[pow2(f, value, rotation) for value in basis]
                  for rotation in rotations]
    atom_states = []
    for rotation, atom_basis in zip(rotations, atom_bases):
        slot = {}
        for mask, sign in sorted(subgroup):
            u = old.coordinate(halves, mask)
            raw_x = 1 ^ f.inv(u)
            lifts = [point for point in old.points_with_x(curve, raw_x)
                     if curve.mul(4, point) == subgroup[(mask, sign)]]
            assert len(lifts) == 1
            source = frob(f, lifts[0], rotation)
            atom = curve.add(source, frob(f, source, 1))
            assert atom is not None and atom[0] != 0
            assert f.inv(atom[0]) == old.coordinate(atom_basis, mask)
            assert curve.mul(R, curve.mul(4, atom)) is None
            slot[(mask, sign)] = {"point": atom, "column": columns[mask]}
        atom_states.append(slot)
    return f, curve, data, rotations, atom_bases, atom_states


def pair_states(f, curve, slot):
    states = {s: [] for s in range(1, 64)}
    exceptional = 0
    for i, ((mask_a, sign_a), a) in enumerate(sorted(slot.items())):
        for (mask_b, sign_b), b in sorted(slot.items())[i+1:]:
            if a["column"] == b["column"]:
                continue
            point = curve.add(a["point"], b["point"])
            if point is None or point[0] == 0:
                exceptional += 1
                continue
            s = mask_a ^ mask_b
            assert s != 0
            states[s].append({"point": point, "masks": [mask_a, mask_b],
                              "signs": [sign_a, sign_b],
                              "columns": [a["column"], b["column"]],
                              "reciprocal": f.inv(point[0])})
    return states, exceptional


def quadratic_resultant(a, b, c, d, e, f):
    """Resultant of aX²+bX+c and dX²+eX+f in characteristic two."""
    return (a*f+d*c)**2 + a*b*f*e + b*b*d*f + b*c*d*e + a*c*e*e


def target_preimages(f, curve, subgroup_target):
    assert curve.on_curve(subgroup_target) and curve.mul(R, subgroup_target) is None
    core = curve.mul(pow(4, -1, R), subgroup_target)
    torsion = (1, 0)
    point = None
    out = []
    for _ in range(4):
        raw = curve.add(core, point)
        assert raw is not None and raw[0] != 0 and curve.mul(4, raw) == subgroup_target
        out.append(raw)
        point = curve.add(point, torsion)
    assert len(set(out)) == 4 and point is None
    return out


def polynomial_setup(f, atom_bases, pair_lists):
    binary = PolynomialRing(GF(2), "t")
    t = binary.gen()
    field = GF(2**41, "a", modulus=t**41+t**3+1)
    ring = PolynomialRing(field, "C")
    C = ring.gen()
    to_field = field.from_integer
    buckets = []
    polys = []
    degrees = []
    for side, basis in enumerate(atom_bases):
        values = [old.coordinate(basis, mask) for mask in range(64)]
        side_buckets = {}
        side_polys = {}
        side_degrees = {}
        for s in range(1, 64):
            products = sorted({f.mul(values[a], values[a ^ s]) for a in range(64)})
            assert len(products) == 32
            sw = values[s]
            polynomial = ring.one()
            for p in products:
                P = to_field(p)
                polynomial *= (field.one() + P**2)*C**2 + P*C + to_field(f.mul(sw, sw))
            side_buckets[s] = products
            side_polys[s] = polynomial
            side_degrees[s] = int(polynomial.degree())
        for s, rows in pair_lists[side].items():
            for row in rows:
                assert side_polys[s](to_field(row["reciprocal"])) == 0
        buckets.append(side_buckets)
        polys.append(side_polys)
        degrees.append(side_degrees)
    return field, ring, C, buckets, polys, degrees


def verify_quadratic_resultant(field, ring, C, right_products, right_sw, q):
    Xring = PolynomialRing(field, "X")
    X = Xring.gen()
    checks = 0
    for p in right_products[:8]:
        a = field.one() + field.from_integer(p)**2
        b = field.from_integer(p)
        c = field.from_integer(right_sw)**2
        for cv in [field.zero(), field.one(), field.from_integer(0x12345)]:
            d = field.one() + (cv*q)**2
            e = cv*q
            h = (cv+q)**2
            expected = (a*X**2+b*X+c).resultant(d*X**2+e*X+h)
            assert expected == quadratic_resultant(a,b,c,d,e,h)
            checks += 1
    return checks


def make_right_resultants(field, ring, C, buckets, basis, q):
    to_field = field.from_integer
    d = ring.one() + (C*q)**2
    e = C*q
    h = (C+q)**2
    result = {}
    for s in range(1, 64):
        sw = old.coordinate(basis, s)
        c = to_field(sw)**2
        polynomial = ring.one()
        for p in buckets[s]:
            P = to_field(p)
            a = field.one() + P**2
            polynomial *= quadratic_resultant(a, P, c, d, e, h)
        result[s] = polynomial
    return result


def exact_bucket_hit(curve, target, left, right):
    table = {}
    for state in right:
        table.setdefault(state["point"], []).append(state)
    for a in left:
        needed = curve.add(target, curve.neg(a["point"]))
        for b in table.get(needed, []):
            if len(set(a["columns"] + b["columns"])) != 4:
                continue
            return {"left_masks": a["masks"], "left_signs": a["signs"],
                    "right_masks": b["masks"], "right_signs": b["signs"],
                    "columns": a["columns"] + b["columns"],
                    "left_point": list(a["point"]), "right_point": list(b["point"]),
                    "raw_sum": list(target)}
    return None


def run_case(name, target, f, curve, field, ring, C, buckets, polys,
             atom_bases, pair_lists, protocol):
    output = HERE / f"{name}_result.json"
    if output.exists():
        raise FileExistsError(output)
    start = time.monotonic_ns()
    raw_targets = target_preimages(f, curve, target)
    target_preimage_ns = time.monotonic_ns() - start
    hits = []
    polynomial_degrees = []
    checked = 0
    status = "COMPLETE"
    resultant_ns = gcd_ns = replay_ns = 0
    algebraic_hits = 0
    for lift_index, raw_target in enumerate(raw_targets):
        q = field.from_integer(f.inv(raw_target[0]))
        begin = time.monotonic_ns()
        right = make_right_resultants(field, ring, C, buckets[1], atom_bases[1], q)
        resultant_ns += time.monotonic_ns() - begin
        polynomial_degrees.append({"lift_index": lift_index,
                                   "right_resultant_degrees": sorted(set(int(v.degree()) for v in right.values()))})
        for s in range(1, 64):
            left_poly = polys[0][s]
            for t in range(1, 64):
                begin = time.monotonic_ns()
                common = left_poly.gcd(right[t])
                gcd_ns += time.monotonic_ns() - begin
                checked += 1
                if common.degree() > 0:
                    algebraic_hits += 1
                    begin = time.monotonic_ns()
                    witness = exact_bucket_hit(curve, raw_target,
                                               pair_lists[0][s], pair_lists[1][t])
                    replay_ns += time.monotonic_ns() - begin
                    hits.append({"lift_index": lift_index, "left_sum_mask": s,
                                 "right_sum_mask": t,
                                 "gcd_degree": int(common.degree()),
                                 "exact_witness": witness})
                if peak_rss() >= protocol["rss_cap_bytes"]:
                    status = "MEMORY_CAP"
                    break
                if time.monotonic_ns() - start >= protocol["case_wall_cap_seconds"]*10**9:
                    status = "CENSORED_TIME"
                    break
            if status != "COMPLETE":
                break
        if status != "COMPLETE":
            break
    result = {"kind": name, "status": status, "candidate_id": None,
              "target": list(target), "target_preimages": [list(p) for p in raw_targets],
              "checked_bucket_pairs": checked, "algebraic_hits": algebraic_hits,
              "exact_hits": sum(h["exact_witness"] is not None for h in hits),
              "hits": hits, "right_resultant_degrees": polynomial_degrees,
              "phase_ns": {"target_preimages": target_preimage_ns,
                           "right_resultants": resultant_ns, "bucket_pair_gcd": gcd_ns,
                           "exact_group_replay": replay_ns,
                           "total": time.monotonic_ns() - start},
              "peak_rss_bytes": peak_rss(), "protocol_sha256": sha(PROTOCOL)}
    save(output, result)
    return result


def main():
    protocol = json.loads(PROTOCOL.read_text())
    inputs = json.loads(INPUT.read_text())
    assert protocol["status"] == "FROZEN_BEFORE_RUN"
    sources = {"run": Path(__file__), "freeze": HERE / "freeze.py",
               "input": INPUT, "geometry": GEOMETRY,
               "base": Path(old.__file__),
               "pair_oracle": BASE.parent / "koblitz-polynomial-w-pair-20260925/pair_oracle.py",
               "runtime": HERE / "sage_runtime_info.json",
               "public": BASE / "n41_adjacent_pairpair/public_target.json"}
    assert {name: sha(path) for name, path in sources.items()} == protocol["source_sha256"]
    f, curve, geometry, rotations, atom_bases, atoms = source_context()
    assert rotations == inputs["rotations"]
    pair_lists = []
    exceptionals = []
    setup_start = time.monotonic_ns()
    for slot in atoms:
        states, count = pair_states(f, curve, slot)
        pair_lists.append(states)
        exceptionals.append(count)
    field, ring, C, buckets, polys, degrees = polynomial_setup(f, atom_bases, pair_lists)
    setup_ns = time.monotonic_ns() - setup_start
    positive = tuple(inputs["positive_subgroup_target"])
    public = tuple(inputs["public_subgroup_target"])
    assert public == tuple(geometry["public_target_q"])
    witness = inputs["positive_witness"]
    selected = [atoms[side][(mask, sign)]["point"]
                for side, pair in enumerate([witness[:2], witness[2:]])
                for mask, sign in pair]
    raw_sum = None
    for point in selected:
        raw_sum = curve.add(raw_sum, point)
    assert raw_sum == tuple(inputs["positive_raw_sum"])
    assert curve.mul(4, raw_sum) == positive
    all_cases = []
    for name, target in [("positive", positive), ("public", public)]:
        result = run_case(name, target, f, curve, field, ring, C, buckets,
                          polys, atom_bases, pair_lists, protocol)
        all_cases.append({"kind": name, "status": result["status"],
                          "algebraic_hits": result["algebraic_hits"],
                          "exact_hits": result["exact_hits"],
                          "phase_ns": result["phase_ns"],
                          "receipt_sha256": sha(HERE / f"{name}_result.json")})
    audit_checks = verify_quadratic_resultant(field, ring, C, buckets[1][1],
                                               old.coordinate(atom_bases[1], 1),
                                               field.from_integer(f.inv(target_preimages(f, curve, positive)[0][0])))
    aggregate = {"status": "COMPLETE" if all(x["status"] == "COMPLETE" for x in all_cases)
                 else "PARTIAL", "candidate_id": None,
                 "field_degree": 41, "subgroup_order": R, "rotations": rotations,
                 "actual_factor_base_points_B": 128,
                 "folded_columns_K": len(set(x["column"] for x in atoms[0].values())),
                 "pair_states_by_side": [sum(len(rows) for rows in side.values()) for side in pair_lists],
                 "exceptional_pair_states": exceptionals,
                 "bucket_polynomial_degrees": [sorted(set(side.values())) for side in degrees],
                 "quadratic_resultant_identity_checks": audit_checks,
                 "reusable_setup_ns": setup_ns,
                 "peak_rss_bytes": peak_rss(),
                 "cases": all_cases, "source_sha256": sha(Path(__file__)),
                 "input_sha256": sha(INPUT), "protocol_sha256": sha(PROTOCOL)}
    save(HERE / "result.json", aggregate)
    print(json.dumps({key: value for key, value in aggregate.items() if key not in ("cases",)}, indent=2))
    print(json.dumps({"cases": all_cases}, indent=2))


if __name__ == "__main__":
    main()
