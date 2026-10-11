"""Solve one descended PDP instance with one engine and report JSON.

    python3 solve.py --engine {sat,f5b,boolean-f5b-native,boolean-f5b-m4ri,msolve,mitm} --n 31 --m 3 --l 6 --seed 1 [--timeout S]

Engines
  sat     CryptoMiniSat through pycryptosat.  Every monomial of degree >= 2
          becomes a Tseitin AND variable; each of the n Boolean equations is
          one native XOR clause.  This is the standard ANF -> CNF+XOR route.
  msolve  msolve (F4-style Groebner basis, grevlex) over F_2 with the field
          equations v^2 + v added; the solution is read off the reduced
          basis.  Set MSOLVE=/path/to/msolve.
  f5b    SymPy F5B on the complete descended Boolean ideal, including field
          equations. Linear basis assignments are extracted and remaining
          variables are enumerated under a hard process timeout. Every root is
          replayed through the original ANF and elliptic-curve group law.
  polybori  Sage/PolyBoRi on the complete Boolean ideal using its native
          squarefree representation, with the same bounded extraction and
          independent curve replay. This is a performance reference, not F5.
  boolean-f5b-native  O3 C++ Boolean signature engine. Python independently
          verifies its basis, original generators, roots, and curve relation.
  boolean-f5b-m4ri  Bounded F5 signature prepass feeding an M4RI Boolean
          Macaulay matrix and certified completion. Python independently
          verifies the complete result. Set M4RI_PREFIX when M4RI is not in
          the bundled Sage location.
  mitm    The combinatorial reference: meet-in-the-middle over the factor
          base itself, P_1 + ... + P_k = R - P_{k+1} - ... - P_m with
          k = ceil(m/2), in group operations.  No algebra at all.

The reported time is the solve only; building the instance is reported
separately.  Every claimed solution is checked by lifting the x_i to points
and re-adding them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
import time

from descend import Instance, make_instance, verify_solution
from gf2n import Curve, GF2n, Point


BOOLEAN_F5B_SIGNATURE_LIMIT = 128
BOOLEAN_M4RI_SIGNATURE_LIMIT = 1
BOOLEAN_M4RI_DEGREE = 8


class Stopwatch:
    """CPU seconds (the reported time) and monotonic wall seconds.

    CPU time is the process's own for in-process engines and the children's
    (RUSAGE_CHILDREN delta) for engines that run a solver binary.  Wall time
    uses CLOCK_MONOTONIC, which does not advance while the VM is paused, so
    limits and reported durations are immune to host pauses; the wall-clock
    time.time() is not, which is why it is not used for measurement.
    """

    def __init__(self, children: bool):
        import resource

        self.children = children
        self._rusage = resource.getrusage
        self._who = resource.RUSAGE_CHILDREN
        self.t0 = time.monotonic()
        self.c0 = self._cpu()

    def _cpu(self) -> float:
        if self.children:
            r = self._rusage(self._who)
            return r.ru_utime + r.ru_stime
        return time.process_time()

    def cpu(self) -> float:
        return self._cpu() - self.c0

    def wall(self) -> float:
        return time.monotonic() - self.t0

    def report(self) -> dict:
        return {"seconds": self.cpu(), "wall_seconds": self.wall()}


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
    sw = Stopwatch(children=False)
    sat, model = s.solve()
    if sat is None:
        return {"status": "timeout", **sw.report(), "aux_vars": len(aux)}
    if not sat:
        return {"status": "unsat", **sw.report(), "aux_vars": len(aux)}
    v = 0
    for j in range(nv):
        if model[j + 1]:
            v |= 1 << j
    return {
        "status": "sat",
        **sw.report(),
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
        sw = Stopwatch(children=True)
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
                **sw.report(),
                "input_bytes": size,
            }
        timing = sw.report()
        if r.returncode != 0:
            return {
                "status": "error",
                **timing,
                "stderr": r.stderr[-500:],
                "input_bytes": size,
            }
        with open(out) as fh:
            text = fh.read()
    basis = _parse_msolve_basis(text)
    if basis == ["1"]:
        return {"status": "unsat", **timing, "input_bytes": size}
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
        **timing,
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


def _f5b_child(pipe, inst: Instance, max_free: int) -> None:
    try:
        import sympy as sp

        started = time.monotonic()
        variables = sp.symbols(f"v0:{inst.nvars}")
        monomials: dict[int, object] = {0: sp.Integer(1)}

        def monomial(mask: int):
            value = monomials.get(mask)
            if value is None:
                value = sp.Integer(1)
                for j in range(inst.nvars):
                    if (mask >> j) & 1:
                        value *= variables[j]
                monomials[mask] = value
            return value

        polynomials = [sum((monomial(mask) for mask in equation), sp.Integer(0))
                       for equation in inst.equations() if equation]
        polynomial_metrics = {
            polynomial: (sp.Poly(polynomial, *variables, modulus=2).total_degree(),
                         len(sp.Poly(polynomial, *variables, modulus=2).terms()))
            for polynomial in polynomials
        }
        polynomials.sort(key=lambda polynomial: polynomial_metrics[polynomial])
        polynomials.extend(variable**2 + variable for variable in variables)
        encoding_seconds = time.monotonic() - started
        basis_started = time.monotonic()
        basis = sp.groebner(polynomials, *variables, modulus=2,
                            order="grevlex", method="f5b")
        basis_seconds = time.monotonic() - basis_started
        basis_text = [str(polynomial.as_expr()) for polynomial in basis.polys]
        basis_digest = hashlib.sha256("\n".join(basis_text).encode()).hexdigest()
        basis_evidence = {"basis_sha256": basis_digest,
                          "input_order": "degree_then_terms_ascending_field_last",
                          "basis_sample": basis_text[:16]}
        if len(basis.polys) == 1 and basis.polys[0].as_expr() == 1:
            pipe.send({"status": "unsat", "complete": True,
                       "encoding_seconds": encoding_seconds,
                       "basis_seconds": basis_seconds, "basis_size": 1,
                       **basis_evidence})
            return
        fixed: dict[int, int] = {}
        for polynomial in basis.polys:
            terms = polynomial.terms()
            linear = [(powers.index(1), int(coefficient) & 1)
                      for powers, coefficient in terms if sum(powers) == 1]
            constant = sum((int(coefficient) & 1) for powers, coefficient in terms
                           if sum(powers) == 0) & 1
            if len(linear) == 1 and all(sum(powers) <= 1 for powers, _ in terms):
                fixed[linear[0][0]] = constant
        free = [j for j in range(inst.nvars) if j not in fixed]
        result = {"status": "gb", "complete": len(free) <= max_free,
                  "encoding_seconds": encoding_seconds,
                  "basis_seconds": basis_seconds, "basis_size": len(basis.polys),
                  "fixed_vars": len(fixed), "free_vars": len(free),
                  **basis_evidence}
        if len(free) > max_free:
            pipe.send(result)
            return
        extraction_started = time.monotonic()
        base = sum(value << j for j, value in fixed.items())
        checked = 0
        for selector in range(1 << len(free)):
            assignment = base
            for i, j in enumerate(free):
                if (selector >> i) & 1:
                    assignment |= 1 << j
            checked += 1
            if inst.evaluate(assignment) == 0 and verify_solution(inst, assignment):
                result.update({"status": "solved", "assignment": assignment,
                               "verified": True,
                               "is_planted": same_points(inst, assignment)})
                break
        result["extraction_seconds"] = time.monotonic() - extraction_started
        result["assignments_checked"] = checked
        if result["status"] == "gb":
            result["status"] = "gb-no-verified-solution"
        pipe.send(result)
    except BaseException as error:
        pipe.send({"status": "error", "error_type": type(error).__name__,
                   "detail": str(error)})
    finally:
        pipe.close()


def solve_f5b(inst: Instance, timeout: float, threads: int) -> dict:
    """Complete F5B basis and verified root extraction for bounded ANF systems."""
    del threads  # SymPy F5B is single-threaded.
    process_context = multiprocessing.get_context("fork")
    receive, send = process_context.Pipe(duplex=False)
    process = process_context.Process(target=_f5b_child, args=(send, inst, 20))
    stopwatch = Stopwatch(children=True)
    process.start()
    send.close()
    message = None
    try:
        if receive.poll(timeout):
            try:
                message = receive.recv()
            except EOFError:
                pass
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join()
        receive.close()
    timing = stopwatch.report()
    if message is None:
        return {"status": "timeout", "complete": False, **timing}
    message.update(timing)
    return message


def _polybori_child(pipe, inst: Instance, max_free: int) -> None:
    try:
        from sage.all import BooleanPolynomialRing

        started = time.monotonic()
        ring = BooleanPolynomialRing(inst.nvars, "v")
        variables = ring.gens()
        monomials = {0: ring.one()}

        def monomial(mask: int):
            value = monomials.get(mask)
            if value is None:
                value = ring.one()
                for j in range(inst.nvars):
                    if (mask >> j) & 1:
                        value *= variables[j]
                monomials[mask] = value
            return value

        polynomials = []
        for equation in inst.equations():
            if not equation:
                continue
            polynomial = ring.zero()
            for mask in equation:
                polynomial += monomial(mask)
            polynomials.append(polynomial)
        polynomials.sort(key=lambda polynomial: (polynomial.deg(), len(polynomial)))
        encoding_seconds = time.monotonic() - started
        basis_started = time.monotonic()
        basis = ring.ideal(polynomials).groebner_basis()
        basis_seconds = time.monotonic() - basis_started
        basis_text = [str(polynomial) for polynomial in basis]
        evidence = {
            "basis_sha256": hashlib.sha256("\n".join(basis_text).encode()).hexdigest(),
            "basis_sample": basis_text[:16],
            "input_order": "degree_then_terms_ascending",
        }
        if basis_text == ["1"]:
            pipe.send({"status": "unsat", "complete": True,
                       "encoding_seconds": encoding_seconds,
                       "basis_seconds": basis_seconds, "basis_size": 1,
                       **evidence})
            return
        result = {"status": "gb", "complete": inst.nvars <= max_free,
                  "encoding_seconds": encoding_seconds,
                  "basis_seconds": basis_seconds, "basis_size": len(basis),
                  "fixed_vars": 0, "free_vars": inst.nvars, **evidence}
        if inst.nvars > max_free:
            pipe.send(result)
            return
        extraction_started = time.monotonic()
        checked = 0
        for assignment in range(1 << inst.nvars):
            checked += 1
            if inst.evaluate(assignment) == 0 and verify_solution(inst, assignment):
                result.update({"status": "solved", "assignment": assignment,
                               "verified": True,
                               "is_planted": same_points(inst, assignment)})
                break
        result["extraction_seconds"] = time.monotonic() - extraction_started
        result["assignments_checked"] = checked
        if result["status"] == "gb":
            result["status"] = "gb-no-verified-solution"
        pipe.send(result)
    except BaseException as error:
        pipe.send({"status": "error", "error_type": type(error).__name__,
                   "detail": str(error)})
    finally:
        pipe.close()


def solve_polybori(inst: Instance, timeout: float, threads: int) -> dict:
    """Complete Boolean-native Gröbner reference with verified extraction."""
    del threads
    process_context = multiprocessing.get_context("fork")
    receive, send = process_context.Pipe(duplex=False)
    process = process_context.Process(target=_polybori_child, args=(send, inst, 20))
    stopwatch = Stopwatch(children=True)
    process.start()
    send.close()
    message = None
    try:
        if receive.poll(timeout):
            try:
                message = receive.recv()
            except EOFError:
                pass
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join()
        receive.close()
    timing = stopwatch.report()
    if message is None:
        return {"status": "timeout", "complete": False, **timing}
    message.update(timing)
    return message


def _boolean_f5b_child(pipe, inst: Instance, max_free: int,
                       timeout: float, cache_dir=None) -> None:
    engine = None
    matrix_cache = None
    try:
        from boolean_f5b import BooleanF5B
        from macaulay_cache import MacaulayCache

        configured_cache = MacaulayCache.from_environment(cache_dir)
        if cache_dir is not None or configured_cache.redis_store is not None:
            matrix_cache = configured_cache
        signature_limit = BOOLEAN_F5B_SIGNATURE_LIMIT
        engine = BooleanF5B(inst.nvars, timeout=timeout, max_pairs=1_000_000,
                            max_signature_insertions=signature_limit,
                            matrix_cache=matrix_cache)
        equations = [equation for equation in inst.equations() if equation]
        equations.sort(key=lambda polynomial: (
            max((monomial.bit_count() for monomial in polynomial), default=0),
            len(polynomial)))
        generators = [engine.from_terms(equation) for equation in equations]
        basis = engine.basis(generators)
        basis_text = ["+".join(str(mask) for mask in sorted(engine.terms(polynomial)))
                      for polynomial in basis]
        result = {
            "status": "gb", "complete": inst.nvars <= max_free,
            "basis_seconds": engine.stats["seconds"],
            "basis_size": len(basis), "fixed_vars": 0,
            "free_vars": inst.nvars,
            "basis_sha256": engine.stats["basis_sha256"],
            "basis_sample": basis_text[:16],
            "input_order": "degree_then_terms_ascending",
            "signature_criteria": "rewrite_only_boolean_quotient",
            "signature_insertion_limit": signature_limit,
            "groebner_verified": engine.stats["groebner_verified"],
            "f5_stats": engine.stats,
            "macaulay_cache": None if matrix_cache is None else matrix_cache.stats,
        }
        if basis == [engine.constant_one]:
            result.update({"status": "unsat", "complete": True})
            pipe.send(result)
            return
        if inst.nvars > max_free:
            pipe.send(result)
            return
        extraction_started = time.monotonic()
        checked = 0
        for assignment in range(1 << inst.nvars):
            checked += 1
            if inst.evaluate(assignment) == 0 and verify_solution(inst, assignment):
                result.update({"status": "solved", "assignment": assignment,
                               "verified": True,
                               "is_planted": same_points(inst, assignment)})
                break
        result["extraction_seconds"] = time.monotonic() - extraction_started
        result["assignments_checked"] = checked
        if result["status"] == "gb":
            result["status"] = "gb-no-verified-solution"
        pipe.send(result)
    except TimeoutError as error:
        pipe.send({"status": "timeout", "complete": False,
                   "detail": str(error),
                   "f5_stats": None if engine is None else engine.stats,
                   "macaulay_cache": None if matrix_cache is None else matrix_cache.stats})
    except BaseException as error:
        pipe.send({"status": "error", "error_type": type(error).__name__,
                   "detail": str(error)})
    finally:
        pipe.close()


def solve_boolean_f5b(inst: Instance, timeout: float, threads: int,
                      cache_dir=None) -> dict:
    """Packed squarefree signature engine with complete bounded extraction."""
    del threads
    process_context = multiprocessing.get_context("fork")
    receive, send = process_context.Pipe(duplex=False)
    process = process_context.Process(
        target=_boolean_f5b_child, args=(send, inst, 20, timeout, cache_dir))
    stopwatch = Stopwatch(children=True)
    process.start()
    send.close()
    message = None
    try:
        if receive.poll(timeout + 0.5):
            try:
                message = receive.recv()
            except EOFError:
                pass
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join()
        receive.close()
    timing = stopwatch.report()
    if message is None:
        return {"status": "timeout", "complete": False, **timing}
    message.update(timing)
    return message


def solve_boolean_f5b_native(inst: Instance, timeout: float, threads: int) -> dict:
    """O3 compiled Boolean signature engine with Python verification."""
    del threads
    from boolean_native_runner import solve_native
    return solve_native(inst, timeout, BOOLEAN_F5B_SIGNATURE_LIMIT)


def solve_boolean_f5b_m4ri(inst: Instance, timeout: float, threads: int) -> dict:
    """Bounded signatures plus dense GF(2) Macaulay completion and verification."""
    del threads
    from boolean_m4ri_runner import solve_m4ri
    return solve_m4ri(inst, timeout, BOOLEAN_M4RI_SIGNATURE_LIMIT,
                      BOOLEAN_M4RI_DEGREE)


def _parse_msolve_basis(text: str) -> list[str]:
    body = text[text.index("[") + 1 : text.rindex("]")]
    return [p.strip() for p in body.replace("\n", "").split(",") if p.strip()]


def solve_mitm(inst: Instance, timeout: float, threads: int) -> dict:
    F = GF2n(inst.n, inst.mod)
    E = Curve(F, inst.b)
    R = E.sum(inst.points)
    sw = Stopwatch(children=False)
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
                if sw.wall() > timeout:
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
                if sw.wall() > timeout:
                    raise TimeoutError
            return False

        rec_right(0, 0, Point(0, 0, True))
    except TimeoutError:
        return {"status": "timeout", **sw.report(), "group_ops": ops}
    timing = sw.report()
    if found is None:
        return {
            "status": "not-found",
            **timing,
            "group_ops": ops,
            "factor_base": len(fb),
        }
    pts = [fb[i] for i in found[0]] + [fb[i] for i in found[1]]
    v = 0
    for i, P in enumerate(pts):
        v |= P.x << (i * inst.l)
    return {
        "status": "solved",
        **timing,
        "group_ops": ops,
        "factor_base": len(fb),
        "assignment": v,
        "verified": verify_solution(inst, v),
    }


WDSAT_CONFIG = """
#define __XG_ENHANCED__
#define __MAX_ANF_ID__ {anf_id}
#define __MAX_DEGREE__ {degree}
#define __MAX_ID__ {max_id}
#define __MAX_BUFFER_SIZE__ {buffer}
#define __MAX_EQ__ {max_eq}
#define __MAX_EQ_SIZE__ {eq_size}
#define __MAX_XEQ__ {xeq}
#define __MAX_XEQ_SIZE__ {xeq_size}
"""


def wdsat_binary(params: dict, src: str | None = None) -> str:
    """WDSat sizes its tables statically, so build one binary per size class.

    WDSAT_SRC points at a checkout of https://github.com/mtrimoska/WDSat (or a
    fork with the same sources and config.h macro names).
    """
    import hashlib
    import shutil

    src = src or os.environ.get("WDSAT_SRC", "/tmp/WDSat")
    key = hashlib.sha1((src + repr(sorted(params.items()))).encode()).hexdigest()[:12]
    build = os.path.join(os.environ.get("WDSAT_BUILDS", "/tmp/wdsat-builds"), key)
    exe = os.path.join(build, "wdsat_solver")
    if os.path.exists(exe):
        return exe
    os.makedirs(build, exist_ok=True)
    for f in os.listdir(os.path.join(src, "src")):
        if f.endswith((".c", ".h")) and f != "config.h":
            shutil.copy(os.path.join(src, "src", f), build)
    with open(os.path.join(build, "config.h"), "w") as fh:
        fh.write(WDSAT_CONFIG.format(**params))
    # The upstream reader holds one input line in a 30 kB stack buffer; the
    # direct (non-symmetrised) model has equations far longer than that.
    for fname, old, new in (
        (
            "wdsat_utils.h",
            "#define __STATIC_CLAUSE_STRING_SIZE__ 30000",
            "#define __STATIC_CLAUSE_STRING_SIZE__ (1 << 27)",
        ),
        (
            "dimacs.c",
            "char str_clause[__STATIC_CLAUSE_STRING_SIZE__] = {0};",
            "static char str_clause[__STATIC_CLAUSE_STRING_SIZE__];",
        ),
    ):
        p = os.path.join(build, fname)
        with open(p) as fh:
            text = fh.read()
        if old not in text:
            raise RuntimeError(
                f"WDSat source at {src} does not match the expected {fname}"
            )
        with open(p, "w") as fh:
            fh.write(text.replace(old, new))
    srcs = [f for f in os.listdir(build) if f.endswith(".c")]
    subprocess.run(["gcc", "-O3", "-w", "-o", exe, *srcs, "-lm"], cwd=build, check=True)
    return exe


def solve_wdsat(
    inst: Instance,
    timeout: float,
    threads: int,
    src_env: str = "WDSAT_SRC",
    src_default: str = "/tmp/WDSat",
    gauss: bool = False,
    trace: bool = False,
) -> dict:
    """WDSat on the symmetrised model of Trimoska–Ionica–Dequen (m = 3 only).

    WDSat's ANF front end is only correct for monomials of degree <= 3 (the
    upstream code returns wrong models on degree >= 4 inputs), so the direct
    descended S_4 (degree 6) cannot be fed to it; the symmetrised model has
    degree 3 by construction and is the one the paper measured.

    src_env names the environment variable holding the source checkout (so a
    fork can be measured next to upstream); gauss adds -x (the XORGAUSS module,
    off by default as in the paper); trace appends the Tr(x) homomorphism
    constraint (symmodel.trace_line), which every rational relation obeys.
    """
    if inst.m != 3:
        return {
            "status": "unsupported",
            "seconds": 0.0,
            "detail": "wdsat engine implements the m = 3 model only",
        }
    if 3 * inst.l - 2 > inst.n:
        return {
            "status": "unsupported",
            "seconds": 0.0,
            "detail": "symmetrised model needs 3l - 2 <= n (e3 must not wrap)",
        }
    import symmodel

    lines, info = symmodel.build_model(inst)
    if trace:
        body = lines[1:] + [
            symmodel.trace_line(GF2n(inst.n, inst.mod), inst.l, inst.xR)
        ]
        lines = [f"p cnf {info['nvars']} {len(body)}", *body]
    nv = info["core"]
    params = {
        "anf_id": info["nvars"] + 1,
        "degree": info["maxdeg"] + 1,
        "max_id": info["nvars"] + info["nonlinear"],
        "buffer": max(200000, 8 * (info["or_clauses"] + info["max_terms"] * inst.n)),
        "max_eq": info["or_clauses"] + 16,
        "eq_size": info["maxdeg"] + 2,
        "xeq": len(lines) + 1,
        "xeq_size": info["max_terms"] + 2,
    }
    exe = wdsat_binary(params, os.environ.get(src_env, src_default))
    with tempfile.TemporaryDirectory() as d:
        inp = os.path.join(d, "in.anf")
        with open(inp, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        sw = Stopwatch(children=True)
        try:
            r = subprocess.run(
                [
                    exe,
                    "-i",
                    inp,
                    "-n",
                    str(inst.n),
                    "-l",
                    str(inst.l),
                    "-m",
                    str(inst.m),
                    "-b",
                ]
                + (["-x"] if gauss else []),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"status": "timeout", **sw.report()}
        timing = sw.report()
    lines = [
        ln.strip()
        for ln in r.stdout.splitlines()
        if ln.strip() and not ln.startswith("!!!")
    ]
    if r.returncode != 0 or not lines:
        return {
            "status": "error",
            **timing,
            "stderr": (r.stderr + r.stdout)[-500:],
        }
    if lines[-2:-1] == ["UNSAT"] or lines[0] == "UNSAT":
        return {"status": "unsat", **timing, "conflicts": int(lines[-1])}
    bits, conflicts = lines[-2], int(lines[-1])
    v = sum(1 << j for j, ch in enumerate(bits[:nv]) if ch == "1")
    return {
        "status": "sat",
        **timing,
        "conflicts": conflicts,
        "model_vars": info["nvars"],
        "model_monomials": info["nonlinear"],
        "assignment": v,
        "verified": verify_solution(inst, v),
        "is_planted": same_points(inst, v),
    }


def _wdsat_variant(**kw):
    return lambda inst, timeout, threads: solve_wdsat(inst, timeout, threads, **kw)


ENGINES = {
    "sat": solve_sat,
    "f5b": solve_f5b,
    "polybori": solve_polybori,
    "boolean-f5b": solve_boolean_f5b,
    "boolean-f5b-native": solve_boolean_f5b_native,
    "boolean-f5b-m4ri": solve_boolean_f5b_m4ri,
    "msolve": solve_msolve,
    "mitm": solve_mitm,
    "wdsat": solve_wdsat,
    "wdsat-xg": _wdsat_variant(gauss=True),
    "wdsat-trace": _wdsat_variant(trace=True),
    # the same model through a fork: WDSAT_FORK_SRC points at its checkout
    "wdsat-fork": _wdsat_variant(
        src_env="WDSAT_FORK_SRC", src_default="/tmp/WDSat-fork"
    ),
    "wdsat-fork-xg": _wdsat_variant(
        src_env="WDSAT_FORK_SRC", src_default="/tmp/WDSat-fork", gauss=True
    ),
}


def main() -> None:
    global BOOLEAN_F5B_SIGNATURE_LIMIT, BOOLEAN_M4RI_SIGNATURE_LIMIT
    global BOOLEAN_M4RI_DEGREE
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=ENGINES, required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--m", type=int, required=True)
    ap.add_argument("--l", type=int, required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=3600)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--signature-limit", type=int, default=128,
                    help="boolean-f5b insertions before certified completion")
    ap.add_argument("--m4ri-signature-limit", type=int, default=1,
                    help="F5 insertions feeding boolean-f5b-m4ri")
    ap.add_argument("--m4ri-degree", type=int, default=8,
                    help="maximum Boolean Macaulay degree for boolean-f5b-m4ri")
    ap.add_argument("--macaulay-cache-dir",
                    help="opt-in persistent Boolean monomial/reducer-row cache")
    ap.add_argument(
        "--random-curve",
        action="store_true",
        help="random b instead of the Koblitz b = 1",
    )
    a = ap.parse_args()
    if a.signature_limit < 1:
        ap.error("--signature-limit must be positive")
    if a.m4ri_signature_limit < 0:
        ap.error("--m4ri-signature-limit must be nonnegative")
    if a.m4ri_degree < 0:
        ap.error("--m4ri-degree must be nonnegative")
    if a.macaulay_cache_dir is not None and a.engine != "boolean-f5b":
        ap.error("--macaulay-cache-dir requires --engine boolean-f5b")
    BOOLEAN_F5B_SIGNATURE_LIMIT = a.signature_limit
    BOOLEAN_M4RI_SIGNATURE_LIMIT = a.m4ri_signature_limit
    BOOLEAN_M4RI_DEGREE = a.m4ri_degree
    t0 = time.monotonic()
    inst = make_instance(
        a.n,
        a.m,
        a.l,
        a.seed,
        b=None if a.random_curve else 1,
        build_anf=a.engine != "mitm",
    )
    build = time.monotonic() - t0
    if a.engine == "boolean-f5b":
        res = solve_boolean_f5b(inst, a.timeout, a.threads,
                                cache_dir=a.macaulay_cache_dir)
    else:
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
