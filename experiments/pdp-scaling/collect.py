"""End-to-end relation-collection throughput for the m = 3 PDP on E(F_2^n).

The single-instance harness (`solve.py`) times one point decomposition, always
on a *planted* (satisfiable) target.  But relation collection is dominated by
the *undecomposable* targets: a random R decomposes into three factor-base
points with probability only about 2^(3l)/(6 * 2^n), and every one of the far
more numerous non-relations still costs a full unsatisfiable search.  The
honest cost of index calculus is therefore

    (attempts to find one relation) * (cost of an unsatisfiable search),

which this tool measures directly.  For a given (n, l, engine, configuration)
it draws random curve points, runs the WDSat symmetrised-model search on each,
classifies SAT / UNSAT, counts conflicts and CPU time separately for the two
classes, verifies every claimed relation by lifting to points and re-adding,
and reports verified relations per PDP call, per CPU-second, and the SAT/UNSAT
conflict split.  This is the instrument any "measurable improvement" is scored
against; see README's "Relation-collection throughput" section.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
import time

import symmodel
from descend import Instance
from gf2n import Curve, GF2n, Point
from solve import Stopwatch, wdsat_binary
from symmodel import trace_line


def target_instance(F: GF2n, b: int, m: int, l: int, xR: int) -> Instance:
    """An Instance carrying only the target abscissa (no planted decomposition)."""
    return Instance(
        n=F.n, mod=F.mod, b=b, m=m, l=l, xR=xR, anf={}, planted=0, points=[]
    )


def _branch_order(core: int, l: int, order: str) -> str:
    if order == "interleave":
        ids = [i * l + j + 1 for j in range(l) for i in range(3)]
    else:  # default: WDSat's own index order (block by block)
        ids = list(range(1, core + 1))
    return ",".join(str(x) for x in ids)


def size_bound(prep: dict, n: int) -> dict:
    """WDSat's static table sizes, as an upper bound over every target x_R.

    The main equations of a target are sums of the twelve target-independent
    pieces, so their monomials lie in the union U of the pieces' monomials;
    bounding by U lets one binary serve every target of a factor base.
    """
    U: set[int] = set()
    for piece in prep["pieces"].values():
        U.update(piece)
    U.discard(0)
    nonlin_main = [mk for mk in U if mk & (mk - 1)]
    defs = prep["definitions"]
    def_tokens = max(ln.count(" ") for ln in defs)
    main_tokens = sum((mk.bit_count() + 1) if mk & (mk - 1) else 1 for mk in U) + 3
    maxdeg = max([3] + [mk.bit_count() for mk in nonlin_main])
    nonlinear = len(prep["nonlinear_defs"]) + len(nonlin_main)
    or_clauses = sum(len(t) + 1 for t in prep["nonlinear_defs"]) + sum(
        mk.bit_count() + 1 for mk in nonlin_main
    )
    max_terms = max(def_tokens, main_tokens)
    nlines = len(defs) + n
    return {
        "anf_id": prep["nvars"] + 1,
        "degree": maxdeg + 1,
        "max_id": prep["nvars"] + nonlinear,
        "buffer": max(200000, 8 * (or_clauses + max_terms * n)),
        "max_eq": or_clauses + 16,
        "eq_size": maxdeg + 2,
        "xeq": nlines + 2,
        "xeq_size": max_terms + 2,
    }


class Collector:
    def __init__(
        self,
        n: int,
        m: int,
        l: int,
        b: int,
        src: str,
        gauss: bool,
        order: str,
        trace: bool = False,
    ):
        assert m == 3, "collector implements the m = 3 symmetrised model"
        assert 3 * l - 2 <= n, "symmetrised model needs 3l - 2 <= n"
        self.F = GF2n(n)
        self.E = Curve(self.F, b)
        self.n, self.m, self.l, self.b = n, m, l, b
        self.gauss = gauss
        self.order = order
        self.trace = trace
        self.src = src
        # prepare the target-independent model once, and one WDSat binary sized for every target
        self.prep = symmodel.prepare(n, self.F.mod, b, l)
        self.info = {"nvars": self.prep["nvars"]}
        self.params = size_bound(self.prep, n)
        self.exe = wdsat_binary(self.params, src)
        self.core = 3 * l
        self.mvc = _branch_order(self.core, l, order)

    def build_oracle(self) -> None:
        """Exact decomposability for small l: R is a relation iff R in F + F + F.

        F is every rational point with x in V (both signs).  The pair-sum table
        has |F|^2 / 2 entries, so this is only for l up to about 8.
        """
        fb: list[Point] = []
        for x in range(1 << self.l):
            P = self.E.lift_x(x)
            if P is not None:
                fb += [P, self.E.neg(P)] if P.y != (P.x ^ P.y) else [P]
        self.fb = fb
        pair: set[tuple[int, int, bool]] = set()
        for i, P in enumerate(fb):
            for Q in fb[i:]:
                S = self.E.add(P, Q)
                pair.add((S.x, S.y, S.inf))
        self.pair = pair

    def decomposable(self, R: Point) -> bool:
        for P in self.fb:
            T = self.E.add(R, self.E.neg(P))
            if (T.x, T.y, T.inf) in self.pair:
                return True
        return False

    def _lift_xs(self, xs: list[int]) -> list[Point] | None:
        pts = []
        for x in xs:
            P = self.E.lift_x(x)
            if P is None:
                return None
            pts.append(P)
        return pts

    def verify(self, core_bits: str, R: Point) -> bool:
        l = self.l
        xs = [
            sum(1 << j for j in range(l) if core_bits[i * l + j] == "1")
            for i in range(3)
        ]
        pts = self._lift_xs(xs)
        if pts is None:
            return False
        for signs in range(1 << 3):
            Q = self.E.sum(
                [self.E.neg(P) if (signs >> i) & 1 else P for i, P in enumerate(pts)]
            )
            if not Q.inf and Q.x == R.x:
                return True
        return False

    def attempt(self, R: Point, timeout: float) -> dict:
        inst = target_instance(self.F, self.b, self.m, self.l, R.x)
        lines, _ = symmodel.build_model(inst)
        if self.trace:
            body = lines[1:] + [trace_line(self.F, self.l, R.x)]
            lines = [f"p cnf {self.prep['nvars']} {len(body)}", *body]
        with tempfile.TemporaryDirectory() as d:
            inp = os.path.join(d, "in.anf")
            with open(inp, "w") as fh:
                fh.write("\n".join(lines) + "\n")
            cmd = [
                self.exe,
                "-i",
                inp,
                "-n",
                str(self.n),
                "-l",
                str(self.l),
                "-m",
                str(self.m),
                "-b",
            ]
            if self.gauss:
                cmd.append("-x")
            if self.order != "default":
                cmd += ["-g", self.mvc]
            sw = Stopwatch(children=True)
            try:
                r = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=timeout, check=False
                )
            except subprocess.TimeoutExpired:
                return {"status": "timeout", **sw.report()}
            timing = sw.report()
        out = [
            ln.strip()
            for ln in r.stdout.splitlines()
            if ln.strip() and not ln.startswith("!!!")
        ]
        if r.returncode != 0 or not out:
            return {"status": "error", **timing, "stderr": (r.stderr + r.stdout)[-300:]}
        if out[0] == "UNSAT" or out[-2:-1] == ["UNSAT"]:
            return {"status": "unsat", "conflicts": int(out[-1]), **timing}
        bits, conflicts = out[-2], int(out[-1])
        verified = self.verify(bits, R)
        return {"status": "sat", "conflicts": conflicts, "verified": verified, **timing}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--l", type=int, required=True)
    ap.add_argument(
        "--engine",
        default="wdsat",
        choices=["wdsat", "wdsat-xg", "wdsat-fork", "wdsat-fork-xg"],
    )
    ap.add_argument("--order", default="default", choices=["default", "interleave"])
    ap.add_argument("--mode", default="random", choices=["random", "planted"])
    ap.add_argument(
        "--calls", type=int, default=2000, help="number of PDP attempts (random mode)"
    )
    ap.add_argument(
        "--relations",
        type=int,
        default=0,
        help="stop after this many verified relations (0 = use --calls)",
    )
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument(
        "--oracle",
        action="store_true",
        help="check every answer against exhaustive decomposability (small l)",
    )
    ap.add_argument(
        "--trace",
        action="store_true",
        help="add the Tr(x) homomorphism constraint to the model",
    )
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    gauss = a.engine.endswith("xg")
    if a.engine.startswith("wdsat-fork"):
        src = os.environ.get("WDSAT_FORK_SRC", "/tmp/WDSat-fork")
    else:
        src = os.environ.get("WDSAT_SRC", "/tmp/WDSat")
    b = 1  # the Koblitz curve of ECC2K-130
    col = Collector(a.n, a.m, a.l, b, src, gauss, a.order, a.trace)
    if a.oracle:
        col.build_oracle()
    rng = random.Random(a.seed)

    truly = missed = spurious = 0
    attempts = sat = unsat = timeouts = errors = verified = 0
    conf_sat = conf_unsat = 0
    cpu_sat = cpu_unsat = 0.0
    t0 = time.monotonic()

    def one_target() -> Point:
        if a.mode == "planted":
            pts = [col.E.random_factor_base_point(a.l, rng) for _ in range(a.m)]
            R = col.E.sum(pts)
            while R.inf:
                pts = [col.E.random_factor_base_point(a.l, rng) for _ in range(a.m)]
                R = col.E.sum(pts)
            return R
        return col.E.random_point(rng)

    while True:
        if a.relations and verified >= a.relations:
            break
        if not a.relations and attempts >= a.calls:
            break
        R = one_target()
        res = col.attempt(R, a.timeout)
        attempts += 1
        st = res["status"]
        if a.oracle:
            truth = col.decomposable(R)
            truly += truth
            if truth and not (st == "sat" and res.get("verified")):
                missed += 1
        if st == "sat":
            sat += 1
            conf_sat += res.get("conflicts", 0)
            cpu_sat += res["seconds"]
            if res.get("verified"):
                verified += 1
            else:
                spurious += (
                    1  # S_4 vanishes, but the x_i do not lift to a rational relation
                )
        elif st == "unsat":
            unsat += 1
            conf_unsat += res.get("conflicts", 0)
            cpu_unsat += res["seconds"]
        elif st == "timeout":
            timeouts += 1
        else:
            errors += 1
        if attempts % 500 == 0:
            print(
                f"  {a.engine} n={a.n} l={a.l} {a.order}: {attempts} attempts, "
                f"{verified} relations, {unsat} unsat",
                file=sys.stderr,
                flush=True,
            )

    wall = time.monotonic() - t0
    cpu_total = cpu_sat + cpu_unsat
    theory_yield = 2 ** (3 * a.l) / (6 * 2**a.n) if a.mode == "random" else 1.0
    out = {
        "engine": a.engine,
        "order": a.order,
        "trace": a.trace,
        "mode": a.mode,
        "n": a.n,
        "m": a.m,
        "l": a.l,
        "attempts": attempts,
        "sat": sat,
        "unsat": unsat,
        "timeouts": timeouts,
        "errors": errors,
        "spurious_sat": spurious,
        "oracle_decomposable": truly if a.oracle else None,
        "oracle_missed": missed if a.oracle else None,
        "verified": verified,
        "yield": verified / attempts if attempts else 0.0,
        "theory_yield_random": theory_yield,
        "conf_sat_mean": conf_sat / sat if sat else 0.0,
        "conf_unsat_mean": conf_unsat / unsat if unsat else 0.0,
        "cpu_sat_mean": cpu_sat / sat if sat else 0.0,
        "cpu_unsat_mean": cpu_unsat / unsat if unsat else 0.0,
        "cpu_total": cpu_total,
        "cpu_per_call": cpu_total / attempts if attempts else 0.0,
        "relations_per_cpu_sec": verified / cpu_total if cpu_total else 0.0,
        "wall": wall,
        "core_vars": col.core,
        "model_vars": col.info["nvars"],
    }
    line = json.dumps(out)
    print(line)
    if a.out:
        with open(a.out, "a") as fh:
            fh.write(line + "\n")


if __name__ == "__main__":
    main()
