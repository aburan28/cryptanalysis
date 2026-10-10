#!/usr/bin/env python3
"""Exact W7/W18 zero-sum triple geometry and N41 public join input."""

import hashlib
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SCREEN = GOAL / "n131_w18_four_pairs/screen.json"
RUNTIME = HERE / "sage_runtime_info.json"
N41_ROTATIONS = (0, 10, 20, 30)
N41_ORDER = 549756390943
N131_ORDER = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    return sum(int(c) << i for i, c in enumerate(value.polynomial().list()))


def half_trace(value, n):
    result = value.parent().zero()
    for _ in range((n + 1) // 2):
        result += value
        value = value**4
    return result


def valid_masks(field, t, dimension):
    basis = [field(t**i) for i in range(1, dimension + 1)]
    valid = bytearray((1 << dimension) // 8)
    count = 0
    value = field.zero()
    for index in range(1, 1 << dimension):
        bit = (index & -index).bit_length() - 1
        value += basis[bit]
        mask = index ^ (index >> 1)
        if (1 / value).trace() == 0:
            valid[mask >> 3] |= 1 << (mask & 7)
            count += 1
    return valid, count


def allowed(valid, mask):
    return bool(valid[mask >> 3] & (1 << (mask & 7)))


def fwht(values):
    values = list(values)
    size = len(values)
    step = 1
    while step < size:
        for start in range(0, size, 2 * step):
            for i in range(start, start + step):
                a, b = values[i], values[i + step]
                values[i], values[i + step] = a + b, a - b
        step *= 2
    return values


def triple_count(valid, dimension):
    size = 1 << dimension
    spectral = fwht(int(allowed(valid, i)) for i in range(size))
    ordered = sum(value**3 for value in spectral) // size
    assert ordered % 6 == 0
    return ordered // 6, max(abs(value) for value in spectral[1:]), spectral[0]


def symbolic_quartic():
    ring = PolynomialRing(GF(2), names=("s", "p", "z"))
    s, p, z = ring.gens()
    q = p*p + p*(s + 1)
    right = (s*s + s)*(z*z + z)
    a, b, c = q + 1, q, s*s
    d, e, f = right + 1, right, (s + z)**2
    value = (a*f + c*d)**2 + (a*e + b*d)*(b*f + c*e)
    assert len(value.dict()) == 21 and value.degree(z) == 4
    assert value.coefficient({z: 3}) == p*s*(s + 1)*(s + p + 1)
    return value, [list(exponents) for exponents in sorted(value.dict())]


def main():
    outputs = [HERE / name for name in ("geometry_result.json", "input_public.txt",
                                      "input_control.txt", "control_witness.json",
                                      "n131_valid_mask_bits.bin")]
    if any(path.exists() for path in outputs):
        raise FileExistsError("preserve first zero-sum triple geometry")
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    screen = json.loads(SCREEN.read_text())
    assert screen["n41"]["public_target_q"] == [1458168294740, 1672312028033]
    assert screen["n131"]["rational_source_seeds"] == 131307
    started = time.monotonic_ns()
    polynomial = PolynomialRing(GF(2), "t")
    t = polynomial.gen()
    f41 = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    f131 = GF(2**131, name="t", modulus=t**131 + t**13 + t**2 + t + 1)
    valid41, count41 = valid_masks(f41, t, 7)
    valid131, count131 = valid_masks(f131, t, 18)
    assert count41 == 63 and count131 == 131307
    (HERE / "n131_valid_mask_bits.bin").write_bytes(valid131)
    n41_count, n41_walsh_max, _ = triple_count(valid41, 7)
    n131_count, n131_walsh_max, _ = triple_count(valid131, 18)
    shapes = sorted({tuple(sorted((a, b, a ^ b)))
                     for a in range(1, 1 << 7) if allowed(valid41, a)
                     for b in range(a + 1, 1 << 7)
                     if allowed(valid41, b) and allowed(valid41, a ^ b)})
    assert n41_count == len(shapes) == 317
    curve = EllipticCurve(f41, [1, 0, 0, 0, 1])
    one_rotation = {}
    source_u = {}
    for mask in range(1, 1 << 7):
        if not allowed(valid41, mask):
            continue
        w = sum((f41(t**(i + 1)) for i in range(7) if mask >> i & 1),
                f41.zero())
        u = half_trace(w, 41)
        assert u*u + u == w and u not in (0, 1)
        raw = curve.lift_x(1 + 1 / u, all=True)
        assert len(raw) == 2
        source_u[mask] = u
        one_rotation[mask] = [(4 * point, point) for point in raw]

    def frob(point, steps):
        for _ in range(steps):
            point = curve(point[0]**2, point[1]**2)
        return point

    def point_key(point):
        return encode(point[0]), encode(point[1])

    def canonical(point):
        best = None
        current = point
        for _ in range(41):
            for member in (current, -current):
                key = point_key(member)
                if best is None or key < best:
                    best = key
            current = frob(current, 1)
        assert current == point
        return best

    columns = {}
    for mask in sorted(one_rotation):
        for sign in (0, 1):
            key = canonical(one_rotation[mask][sign][0])
            columns.setdefault(key, len(columns))
    rows_by_rotation = []
    all_points = set()
    for rotation in N41_ROTATIONS:
        rows = []
        for mask in sorted(one_rotation):
            for sign in (0, 1):
                point = frob(one_rotation[mask][sign][0], rotation)
                col = columns[canonical(one_rotation[mask][sign][0])]
                rows.append((mask, sign, col, *point_key(point)))
                all_points.add(point_key(point))
        rows_by_rotation.append(rows)
    assert len(rows_by_rotation) == 4 and all(len(rows) == 126 for rows in rows_by_rotation)
    # This label is the exact projected group-point count before orbit folding.
    base_count = len(all_points)
    q = curve(f41(polynomial([(1458168294740 >> i) & 1 for i in range(41)])),
              f41(polynomial([(1672312028033 >> i) & 1 for i in range(41)])))
    assert N41_ORDER * q == curve(0)

    # Build a deterministic positive control with distinct folded columns.
    chosen = []
    used = set()
    for rotation in N41_ROTATIONS:
        choice = next(shape for shape in shapes
                      if len({columns[canonical(one_rotation[m][0][0])] for m in shape}) == 3
                      and not ({columns[canonical(one_rotation[m][0][0])] for m in shape} & used))
        chosen.append(choice)
        used.update(columns[canonical(one_rotation[m][0][0])] for m in choice)
    assert len(used) == 12
    control_points = [frob(one_rotation[mask][0][0], rotation)
                      for rotation, shape in zip(N41_ROTATIONS, chosen)
                      for mask in shape]
    control_q = sum(control_points, curve(0))
    assert control_q != curve(0)
    quartic, quartic_terms = symbolic_quartic()
    for shape, rotation in zip(chosen, N41_ROTATIONS):
        u1, u2, u3 = [source_u[m]**(2**rotation) for m in shape]
        assert u1 + u2 + u3 == 0
        raw_sum = sum((frob(one_rotation[m][0][1], rotation) for m in shape),
                      curve(0))
        if raw_sum != curve(0) and raw_sum[0] != 1:
            z = 1 / (raw_sum[0] + 1)
            assert quartic(source_u[shape[0]]**(2**rotation) +
                           source_u[shape[1]]**(2**rotation), u1*u2, z) == 0

    def write_input(path, target):
        lines = [f"{encode(target[0])} {encode(target[1])} {N41_ORDER} 4"]
        for rotation, rows in zip(N41_ROTATIONS, rows_by_rotation):
            lines.append(f"{rotation} {len(rows)}")
            lines.extend(" ".join(map(str, row)) for row in rows)
        path.write_text("\n".join(lines) + "\n")

    write_input(HERE / "input_public.txt", q)
    write_input(HERE / "input_control.txt", control_q)
    control = {"target": list(point_key(control_q)),
               "rotations": list(N41_ROTATIONS),
               "masks_by_block": [list(shape) for shape in chosen],
               "columns": sorted(used),
               "subgroup_points": [list(point_key(point)) for point in control_points]}
    (HERE / "control_witness.json").write_text(
        json.dumps(control, indent=2, sort_keys=True) + "\n")
    result = {
        "status": "EXACT_GEOMETRY", "proposal_id": "Q20261009195000",
        "candidate_id": None, "run_id": None,
        "n41": {"field_degree": 41, "source_dimension": 7,
                "valid_masks": count41, "unordered_zero_sum_triples": n41_count,
                "signed_triple_state_upper": 8 * n41_count,
                "walsh_nontrivial_abs_max": n41_walsh_max,
                "rotations": list(N41_ROTATIONS), "actual_base_points_B": base_count,
                "folded_columns_K": len(columns), "target_q": list(point_key(q))},
        "n131": {"field_degree": 131, "source_dimension": 18,
                 "valid_masks": count131, "unordered_zero_sum_triples": n131_count,
                 "signed_triple_state_upper": 8 * n131_count,
                 "walsh_nontrivial_abs_max": n131_walsh_max,
                 "rotations": [0, 32, 64, 96],
                 "existing_four_rotation_base_B": screen["n131"]["fixed_union_usable_points_B"],
                 "existing_folded_columns_K": screen["n131"]["signed_frobenius_columns_K"],
                 "subgroup_order": N131_ORDER},
        "quartic": {"variables": ["s", "p", "z"], "terms": quartic_terms,
                    "term_count": len(quartic_terms),
                    "z_cubic_coefficient_factor": "p*s*(s+1)*(s+p+1)"},
        "geometry_wall_ns": time.monotonic_ns() - started,
        "sha256": {"source": sha(__file__), "screen": sha(SCREEN),
                   "runtime": sha(RUNTIME),
                   "n131_valid_bits": sha(HERE / "n131_valid_mask_bits.bin"),
                   "public_input": sha(HERE / "input_public.txt"),
                   "control_input": sha(HERE / "input_control.txt"),
                   "control_witness": sha(HERE / "control_witness.json")},
    }
    (HERE / "geometry_result.json").write_text(json.dumps(result, indent=2,
                                                        sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "n41_triples": n41_count,
                      "n131_triples": n131_count, "n41_B": base_count,
                      "n41_K": len(columns), "geometry_wall_ns": result["geometry_wall_ns"]}),
          flush=True)


if __name__ == "__main__":
    main()
