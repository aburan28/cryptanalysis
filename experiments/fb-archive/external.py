"""Factor bases whose experiments used their own field, curve and builder.

Three complete-DLP results were built outside ToyCurve/family_basis, so `fbarchive.build`
cannot reproduce them with its usual families.  Each family below rebuilds one of them in
Python and carries the experiment's own `field` and `curve` records, so the archive's
curve ID is the ID the experiment's manifests already use:

  kerfrob   f4-gpu-20260925 (Rust `ca-ic`, `build_frobenius_factor_base(kc, index)`):
            every point whose abscissa lies in the kernel of the linearised polynomial
            of a top-degree irreducible factor of x^n - 1 over F_2.  l is that degree,
            seed is the factor index (ascending bitmask order), a2 picks the curve.
            Its results cite the Rust digest (sorted "0x..,0x.." lines), which
            `rust_points_digest` recomputes; aliases.csv maps it to this archive.
  nbexact   hamming-ic-e2e-20260929 n = 9: x = c_i + c_j (exact normal-basis weight 2)
            for the first normal element, every rational lift projected by the cofactor.
            l is the weight; there is no seed (use 1).
  nbstride  ic-candidate-catalog complete n = 13 SAT candidate: the span of every
            4th conjugate of shifted-base-geometry/audit.normal_basis(seed), the lifts
            in the order-r subgroup.  l is the dimension, seed the audit seed.

The two normal-basis families reuse factor-base-yield-v2/engine.py (via
shifted-base-geometry/audit.py), the curve arithmetic those runs used.
"""

from __future__ import annotations

import hashlib
import itertools
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from purepy import PyField  # noqa: E402
from toycurve import sha256_hex  # noqa: E402

KERFROB, NBEXACT, NBSTRIDE = "kerfrob", "nbexact", "nbstride"
FAMILIES = (KERFROB, NBEXACT, NBSTRIDE)
RUST_DIGEST = "ca-ic sorted-xy-hex-lines"

# f4-gpu-20260925/manifests/EC1N23Cka{0,1}h*.json: ca-ic's KoblitzCurve::new(a, 23).
KERFROB_CURVES = {
    (23, 0): {"modulus_terms": [23, 5, 0], "order": 8383412, "r": 2095853, "G": (0x727A76, 0x5E8AA9)},
    (23, 1): {"modulus_terms": [23, 5, 0], "order": 8393806, "r": 4196903, "G": (0x2AAAA5, 0x13907B)},
}


def rust_points_digest(points) -> str:
    """SHA-256 of sorted "x,y" lines of 0x-hex coordinates (suite/examples/f4_batch_bench.rs)."""
    lines = sorted(f"{x:#x},{y:#x}" for x, y in points)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


# ------------------------------------------------------------------ kerfrob
def _top_factors(n: int):
    """Irreducible factors of x^n - 1 over F_2 of the largest degree, as bitmasks, ascending."""
    d = 1
    while pow(2, d, n) != 1:
        d += 1
    if d > 20:
        raise ValueError(f"kerfrob: top factor degree {d} is too large to search")
    target = (1 << n) | 1

    def divides(g: int) -> bool:
        r = target
        dg = g.bit_length() - 1
        while r.bit_length() - 1 >= dg:
            r ^= g << (r.bit_length() - 1 - dg)
        return r == 0

    def irreducible(g: int) -> bool:
        dg = g.bit_length() - 1
        for h in range(2, 1 << (dg // 2 + 1)):
            r = g
            dh = h.bit_length() - 1
            if dh == 0 or dh > dg // 2:
                continue
            while r.bit_length() - 1 >= dh:
                r ^= h << (r.bit_length() - 1 - dh)
            if r == 0:
                return False
        return True

    return [g for g in range((1 << d) | 1, 1 << (d + 1), 2) if divides(g) and irreducible(g)]


def _kernel(K: PyField, g: int) -> list[int]:
    """F_2-basis of {x : sum_i g_i x^(2^i) = 0}, by elimination on the images of z^j."""
    def lin(x: int) -> int:
        acc = 0
        for i in range(g.bit_length()):
            if g >> i & 1:
                acc ^= x
            x = K.sqr(x)
        return acc

    pivots, basis = {}, []
    for j in range(K.n):
        v, comb = lin(1 << j), 1 << j
        while v:
            b = v.bit_length() - 1
            if b not in pivots:
                pivots[b] = (v, comb)
                break
            v ^= pivots[b][0]
            comb ^= pivots[b][1]
        if not v:
            basis.append(comb)
    return basis


def _lifts(K: PyField, a2: int, x: int):
    """Both points of y^2 + xy = x^3 + a2 x^2 + 1 over x (one at x = 0)."""
    if x == 0:
        return [(0, 1)]
    c = x ^ a2 ^ K.sqr(K.inv(x))
    if K.trace(c):
        return []
    y = K.mul(x, K.half_trace(c))
    return [(x, y), (x, y ^ x)]


def _add(K: PyField, a2: int, P, Q):
    if P is None:
        return Q
    if Q is None:
        return P
    (x1, y1), (x2, y2) = P, Q
    if x1 == x2:
        if y1 ^ y2 == x1 or x1 == 0:
            return None
        lam = x1 ^ K.mul(y1, K.inv(x1))
        x3 = K.sqr(lam) ^ lam ^ a2
        return x3, K.sqr(x1) ^ K.mul(lam ^ 1, x3)
    lam = K.mul(y1 ^ y2, K.inv(x1 ^ x2))
    x3 = K.sqr(lam) ^ lam ^ x1 ^ x2 ^ a2
    return x3, K.mul(lam, x1 ^ x3) ^ x3 ^ y1


def _smul(K: PyField, a2: int, P, k: int):
    acc = None
    while k:
        if k & 1:
            acc = _add(K, a2, acc, P)
        P = _add(K, a2, P, P)
        k >>= 1
    return acc


def kerfrob_archive(n: int, l: int, seed: int, a2: int, points: bool) -> dict:
    spec = KERFROB_CURVES.get((n, a2))
    if spec is None:
        raise ValueError(f"kerfrob: no recorded ca-ic curve for n = {n}, a2 = {a2}")
    terms = spec["modulus_terms"]
    K = PyField(n, sum(1 << t for t in terms))
    factors = _top_factors(n)
    if l != factors[0].bit_length() - 1:
        raise ValueError(f"kerfrob: top factors of x^{n} - 1 have degree {factors[0].bit_length() - 1}, not {l}")
    g = factors[seed]
    basis = _kernel(K, g)
    assert len(basis) == l
    span = [0]
    for b in basis:
        span += [s ^ b for s in span]
    pts = sorted(p for x in span for p in _lifts(K, a2, x))
    r, h = spec["r"], spec["order"] // spec["r"]
    G = spec["G"]
    field_rec = {
        "characteristic": 2,
        "degree": n,
        "representation": "polynomial basis",
        "modulus_terms": terms,
        "element_encoding": "integer whose bit i is the coefficient of z^i, 0x lowercase hex",
    }
    curve_rec = {
        "model": "y^2 + x*y = x^3 + a*x^2 + b",
        "a": hex(a2),
        "b": "0x1",
        "order": str(spec["order"]),
        "trace": str((1 << n) + 1 - spec["order"]),
        "subgroup_order": str(r),
        "cofactor": str(h),
        "generator": {"x": hex(G[0]), "y": hex(G[1])},
        "target_group": "order-r subgroup generated by G",
    }
    curve_id = f"EC1N{n}Cka{a2}h{sha256_hex({'field': field_rec, 'curve': curve_rec})[:12]}"
    # columns: signed Frobenius orbits of the cofactor projections [h]P != O
    proj = {_smul(K, a2, P, h) for P in pts} - {None}
    seen, cols = set(), 0
    for P in sorted(proj):
        if P in seen:
            continue
        cols += 1
        Q = P
        for _ in range(n):
            seen.add(Q)
            seen.add((Q[0], Q[0] ^ Q[1]))
            Q = (K.sqr(Q[0]), K.sqr(Q[1]))
    strict = sum(1 for P in pts if _smul(K, a2, P, r) is None)
    rec_points = [[x, y] for x, y in pts]
    rec = {
        "curve_id": curve_id,
        "construction": {
            "family": KERFROB,
            "basis": basis,
            "params": {"a2": a2, "factor_index": seed, "factor": g},
            "polynomial_constraint": "x in the kernel of sum_i g_i x^(2^i), g a top-degree "
                                     "irreducible factor of x^n - 1 over F_2 (ascending bitmask order)",
            "shifted_bases": "none",
        },
        "subgroup_policy": "none: every point over the subspace; rows are projected by the cofactor",
        "enumerated_set_sha256": sha256_hex(rec_points) if points else None,
        "nominal_dimension": l,
        "geometric_point_count": len(pts) if points else None,
        "actual_usable_point_count": len(pts) if points else None,
        "strict_subgroup_point_count": strict if points else None,
        "quotient_rule": "signed Frobenius orbits merged by cofactor projection",
        "effective_columns": cols if points else None,
        "abscissae": len(span),
        "rust_points_sha256": rust_points_digest(pts) if points else None,
    }
    return {
        "field": field_rec,
        "curve": {**curve_rec, "curve_id": curve_id},
        "factor_base": rec,
        "points": rec_points if points else None,
        "point_columns": None,
        "column_representatives": None,
        "builder": "fb-archive/external.py kerfrob (Python rebuild of suite ca-ic build_frobenius_factor_base)",
    }


# ------------------------------------------------------------------ normal-basis bases on engine.py curves
def _engine():
    sys.path.insert(0, str(ROOT / "experiments" / "shifted-base-geometry"))
    import audit

    return audit, audit.engine


def _engine_records(n: int, curve, r: int, cofactor: int, G) -> tuple[dict, dict, str]:
    """The field and curve records of hamming-ic-e2e/run_e2e_n9.py and complete_n13_sat.py."""
    field_rec = {"p": 2, "n": n, "basis": "polynomial", "defining_polynomial_int": curve.f.modulus,
                 "element_encoding": "nonnegative polynomial coefficient bit mask"}
    curve_rec = {"model": "y^2+x*y=x^3+1",
                 "coefficients": {"a1": 1, "a2": 0, "a3": 0, "a4": 0, "a6": 1},
                 "curve_order": cofactor * r, "trace": (1 << n) + 1 - cofactor * r,
                 "r": r, "cofactor": cofactor, "G": list(G),
                 "target_group": "prime_order_r_subgroup"}
    curve_id = f"EC1N{n}Ckb1h{sha256_hex({'field': field_rec, 'curve': curve_rec})[:12]}"
    return field_rec, curve_rec, curve_id


def _signed_frobenius_columns(curve, n: int, pts) -> int:
    seen, cols = set(), 0
    for P in sorted(pts):
        if P in seen:
            continue
        cols += 1
        Q = P
        for _ in range(n):
            seen.add(Q)
            seen.add(curve.neg(Q))
            Q = (curve.f.square(Q[0]), curve.f.square(Q[1]))
    return cols


def _engine_doc(family, n, l, seed, params, constraint, policy, curve, r, cofactor, G, geometric, pts,
                points: bool, builder: str) -> dict:
    field_rec, curve_rec, curve_id = _engine_records(n, curve, r, cofactor, G)
    rec_points = [list(p) for p in pts]
    rec = {
        "curve_id": curve_id,
        "construction": {"family": family, "basis": None, "params": params,
                         "polynomial_constraint": constraint, "shifted_bases": "none"},
        "subgroup_policy": policy,
        "enumerated_set_sha256": sha256_hex(rec_points) if points else None,
        "nominal_dimension": l if family == NBSTRIDE else None,
        "geometric_point_count": geometric if points else None,
        "actual_usable_point_count": len(pts) if points else None,
        "strict_subgroup_point_count": len(pts) if points else None,
        "quotient_rule": "sign+frobenius",
        "effective_columns": _signed_frobenius_columns(curve, n, pts) if points else None,
    }
    return {
        "field": field_rec,
        "curve": {**curve_rec, "curve_id": curve_id},
        "factor_base": rec,
        "points": rec_points if points else None,
        "point_columns": None,
        "column_representatives": None,
        "builder": builder,
    }


def nbexact_archive(n: int, w: int, seed: int, points: bool) -> dict:
    """hamming-ic-e2e-20260929/run_e2e_n9.py normal_basis + build_factor_base, for any w."""
    if seed != 1:
        raise ValueError("nbexact has no seed: the normal element is the first one; use --seed 1")
    _, E = _engine()
    curve, r, G, _ = E.setup(n, E.Ledger())
    order = 1 + (1 << n) - _trace(curve, n)
    cofactor = order // r
    f = curve.f
    for alpha in range(2, f.limit):
        conj = [alpha]
        for _ in range(1, n):
            conj.append(f.square(conj[-1]))
        if f.square(conj[-1]) != alpha:
            continue
        pivots = {}
        for v in conj:
            while v:
                b = v.bit_length() - 1
                if b not in pivots:
                    pivots[b] = v
                    break
                v ^= pivots[b]
        if len(pivots) == n:
            break
    else:
        raise AssertionError("normal basis not found")
    raw = {}
    for sup in itertools.combinations(range(n), w):
        x = 0
        for i in sup:
            x ^= conj[i]
        for P in curve.lift(x):
            Q = curve.mul(P, cofactor)
            if Q is not None:
                raw[P] = Q
    pts = sorted(set(raw.values()))
    return _engine_doc(NBEXACT, n, w, seed, {"w": w, "normal_element": alpha},
                       "Hamming weight of the normal-basis coordinates of x is exactly w "
                       "(first normal element, engine.py curve)",
                       "cofactor_projection: [h]P of every rational lift, identity dropped",
                       curve, r, cofactor, G, len(raw), pts, points,
                       "fb-archive/external.py nbexact (hamming-ic-e2e-20260929/run_e2e_n9.py build_factor_base)")


def nbstride_archive(n: int, l: int, seed: int, stride: int, points: bool) -> dict:
    """ic-candidate-catalog/measurements/2026-09-25/complete_n13_sat.py prepare()."""
    audit, E = _engine()
    curve, r, G, _ = E.setup(n, E.Ledger())
    order = 1 + (1 << n) - _trace(curve, n)
    normal = audit.normal_basis(curve.f, seed)
    xs = audit.subspace([normal[stride * j] for j in range(l)])
    lifted = [P for x in xs for P in curve.lift(x) if P is not None]
    pts = sorted(P for P in lifted if curve.mul(P, r) is None)
    return _engine_doc(NBSTRIDE, n, l, seed, {"stride": stride, "seed": seed},
                       f"x in the span of conjugates 0, {stride}, ..., {stride * (l - 1)} of "
                       "shifted-base-geometry/audit.normal_basis(field, seed)",
                       "subgroup_filter: lifts with [r]P = O",
                       curve, r, order // r, G, len(lifted), pts, points,
                       "fb-archive/external.py nbstride (complete_n13_sat.py prepare)")


def _trace(curve, n: int) -> int:
    """Frobenius trace of y^2 + xy = x^3 + 1 over F_2^n (Lucas sequence t_k = t_{k-1} - 2 t_{k-2})."""
    t0, t1 = 2, 1
    for _ in range(n - 1):
        t0, t1 = t1, t1 - 2 * t0
    return t1


def build(n: int, family: str, l: int, seed: int, points: bool, extra: dict) -> dict:
    if family == KERFROB:
        return kerfrob_archive(n, l, seed, int(extra["a2"]), points)
    if family == NBEXACT:
        return nbexact_archive(n, l, seed, points)
    if family == NBSTRIDE:
        return nbstride_archive(n, l, seed, int(extra["stride"]), points)
    raise ValueError(family)
