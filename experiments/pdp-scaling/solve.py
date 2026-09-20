"""Solve one descended PDP instance with one engine and report JSON.

    python3 solve.py --engine {sat,msolve,mitm} --n 31 --m 3 --l 6 --seed 1 [--timeout S]

Engines
  sat     CryptoMiniSat through pycryptosat.  Every monomial of degree >= 2
          becomes a Tseitin AND variable; each of the n Boolean equations is
          one native XOR clause.  This is the standard ANF -> CNF+XOR route.
  msolve  msolve (F4-style Groebner basis, grevlex) over F_2 with the field
          equations v^2 + v added; the solution is read off the reduced
          basis.  Set MSOLVE=/path/to/msolve.
  mitm    The combinatorial reference: meet-in-the-middle over the factor
          base itself, P_1 + ... + P_k = R - P_{k+1} - ... - P_m with
          k = ceil(m/2), in group operations.  No algebra at all.

The reported time is the solve only; building the instance is reported
separately.  Every claimed solution is checked by lifting the x_i to points
and re-adding them.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

from descend import Instance, make_instance, verify_solution
from gf2n import Curve, GF2n, Point


def solve_sat(inst: Instance, timeout: float, threads: int) -> dict:
    import pycryptosat

    eqs = inst.equations()
    nv = inst.nvars
    aux: dict[int, int] = {}
    s = pycryptosat.Solver(threads=threads, time_limit=timeout)
    nxt = nv + 1
    monomials = set().union(*eqs)
    for mask in monomials:
        if mask == 0 or mask & (mask - 1) == 0:
            continue
        lits = [j + 1 for j in range(nv) if (mask >> j) & 1]
        t = nxt
        nxt += 1
        aux[mask] = t
        for v in lits:
            s.add_clause([-t, v])
        s.add_clause([t] + [-v for v in lits])
    for eq in eqs:
        xs = []
        rhs = False
        for mask in eq:
            if mask == 0:
                rhs = not rhs
            elif mask & (mask - 1) == 0:
                xs.append(mask.bit_length())
            else:
                xs.append(aux[mask])
        if xs:
            s.add_xor_clause(xs, rhs)
        elif rhs:
            return {"status": "unsat-constant", "seconds": 0.0}
    t0 = time.time()
    sat, model = s.solve()
    dt = time.time() - t0
    if sat is None:
        return {"status": "timeout", "seconds": dt, "aux_vars": len(aux)}
    if not sat:
        return {"status": "unsat", "seconds": dt, "aux_vars": len(aux)}
    v = 0
    for j in range(nv):
        if model[j + 1]:
            v |= 1 << j
    return {
        "status": "sat",
        "seconds": dt,
        "aux_vars": len(aux),
        "assignment": v,
        "verified": verify_solution(inst, v),
        "is_planted": same_points(inst, v),
    }


def same_points(inst: Instance, v: int) -> bool:
    """The planted decomposition, up to the order of the summands."""
    return sorted(inst.x_from_assignment(v)) == sorted(
        inst.x_from_assignment(inst.planted)
    )


def _msolve_poly(mask: int, nv: int) -> str:
    if mask == 0:
        return "1"
    return "*".join(f"v{j}" for j in range(nv) if (mask >> j) & 1)


def solve_msolve(inst: Instance, timeout: float, threads: int) -> dict:
    exe = os.environ.get("MSOLVE", "msolve")
    nv = inst.nvars
    eqs = inst.equations()
    with tempfile.TemporaryDirectory() as d:
        inp = os.path.join(d, "in.ms")
        out = os.path.join(d, "out.ms")
        with open(inp, "w") as fh:
            fh.write(",".join(f"v{j}" for j in range(nv)) + "\n2\n")
            polys = [
                "+".join(_msolve_poly(mk, nv) for mk in sorted(eq)) for eq in eqs if eq
            ]
            polys += [f"v{j}^2+v{j}" for j in range(nv)]
            fh.write(",\n".join(polys) + "\n")
        size = os.path.getsize(inp)
        t0 = time.time()
        try:
            r = subprocess.run(
                [exe, "-g", "2", "-t", str(threads), "-f", inp, "-o", out],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "seconds": time.time() - t0,
                "input_bytes": size,
            }
        dt = time.time() - t0
        if r.returncode != 0:
            return {
                "status": "error",
                "seconds": dt,
                "stderr": r.stderr[-500:],
                "input_bytes": size,
            }
        with open(out) as fh:
            text = fh.read()
    basis = _parse_msolve_basis(text)
    if basis == ["1"]:
        return {"status": "unsat", "seconds": dt, "input_bytes": size}
    # read v_j = c off the linear basis elements; brute-force any leftovers
    fixed: dict[int, int] = {}
    for p in basis:
        terms = [t.strip() for t in p.replace("-", "+").split("+") if t.strip()]
        vs = [t for t in terms if t.startswith("1*v") and "^" not in t]
        consts = [t for t in terms if t == "1"]
        if len(vs) == 1 and len(terms) == len(vs) + len(consts):
            j = int(vs[0][3:])
            fixed[j] = len(consts) % 2
    free = [j for j in range(nv) if j not in fixed]
    res = {
        "status": "gb",
        "seconds": dt,
        "basis_size": len(basis),
        "free_vars": len(free),
        "input_bytes": size,
    }
    if len(free) > 16:
        return res
    base = sum(c << j for j, c in fixed.items())
    for k in range(1 << len(free)):
        v = base
        for i, j in enumerate(free):
            if (k >> i) & 1:
                v |= 1 << j
        if inst.evaluate(v) == 0 and verify_solution(inst, v):
            res.update(
                {
                    "status": "solved",
                    "assignment": v,
                    "verified": True,
                    "is_planted": same_points(inst, v),
                }
            )
            return res
    res["status"] = "gb-no-solution-found"
    return res


def _parse_msolve_basis(text: str) -> list[str]:
    body = text[text.index("[") + 1 : text.rindex("]")]
    return [p.strip() for p in body.replace("\n", "").split(",") if p.strip()]


def solve_mitm(inst: Instance, timeout: float, threads: int) -> dict:
    F = GF2n(inst.n, inst.mod)
    E = Curve(F, inst.b)
    R = E.sum(inst.points)
    t0 = time.time()
    fb: list[Point] = []
    for x in range(1 << inst.l):
        P = E.lift_x(x)
        if P is not None:
            fb.append(P)
            fb.append(E.neg(P))
    k = (inst.m + 1) // 2  # left side has k points, right side m - k
    ops = 0

    def sums(count: int, start: Point) -> dict[int, tuple]:
        table: dict[int, tuple] = {}

        # unordered multisets via non-decreasing indices
        def rec(depth: int, lo: int, acc: Point, chosen: tuple) -> None:
            nonlocal ops
            if depth == count:
                if not acc.inf:
                    table.setdefault(acc.x, chosen)
                return
            for i in range(lo, len(fb)):
                ops += 1
                rec(depth + 1, i, E.add(acc, fb[i]), chosen + (i,))
                if time.time() - t0 > timeout:
                    raise TimeoutError

        rec(0, 0, start, ())
        return table

    try:
        left = sums(k, Point(0, 0, True))
        # right side: R - (P_{k+1} + ... + P_m), matched on x (signs absorbed)
        found = None
        right_count = inst.m - k
        idx_stack: list[int] = []

        def rec_right(depth: int, lo: int, acc: Point) -> bool:
            nonlocal found, ops
            if depth == right_count:
                target = E.add(R, E.neg(acc))
                if not target.inf and target.x in left:
                    found = (left[target.x], tuple(idx_stack))
                    return True
                return False
            for i in range(lo, len(fb)):
                ops += 1
                idx_stack.append(i)
                if rec_right(depth + 1, i, E.add(acc, fb[i])):
                    return True
                idx_stack.pop()
                if time.time() - t0 > timeout:
                    raise TimeoutError
            return False

        rec_right(0, 0, Point(0, 0, True))
    except TimeoutError:
        return {"status": "timeout", "seconds": time.time() - t0, "group_ops": ops}
    dt = time.time() - t0
    if found is None:
        return {
            "status": "not-found",
            "seconds": dt,
            "group_ops": ops,
            "factor_base": len(fb),
        }
    pts = [fb[i] for i in found[0]] + [fb[i] for i in found[1]]
    v = 0
    for i, P in enumerate(pts):
        v |= P.x << (i * inst.l)
    return {
        "status": "solved",
        "seconds": dt,
        "group_ops": ops,
        "factor_base": len(fb),
        "assignment": v,
        "verified": verify_solution(inst, v),
    }


ENGINES = {"sat": solve_sat, "msolve": solve_msolve, "mitm": solve_mitm}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=ENGINES, required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--m", type=int, required=True)
    ap.add_argument("--l", type=int, required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=3600)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument(
        "--random-curve",
        action="store_true",
        help="random b instead of the Koblitz b = 1",
    )
    a = ap.parse_args()
    t0 = time.time()
    inst = make_instance(
        a.n,
        a.m,
        a.l,
        a.seed,
        b=None if a.random_curve else 1,
        build_anf=a.engine != "mitm",
    )
    build = time.time() - t0
    res = ENGINES[a.engine](inst, a.timeout, a.threads)
    res.update(
        {
            "engine": a.engine,
            "n": a.n,
            "m": a.m,
            "l": a.l,
            "seed": a.seed,
            "curve": "random" if a.random_curve else "koblitz",
            "b": inst.b,
            "vars": inst.nvars,
            "monomials": len(inst.anf),
            "build_seconds": build,
        }
    )
    json.dump(res, sys.stdout)
    print()


if __name__ == "__main__":
    main()
