"""Fixed-phase three-summand PDP: reusable XOR circuits and hybrid assumptions.

Stage diagnostic only. The exact point oracle never supplies solver inputs.
Run `python3 fixed_phase.py --help`; see FIXED_PHASE.md for accounting/scope.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import platform
import random
import subprocess
import time
from collections import Counter
from pathlib import Path

from gf2n import Curve, GF2n, INF, Point


class Circuit:
    """Hash-consed Boolean circuit with native XOR and quadratic AND gates.

    Wire 0 is false; wire 1 is constrained true. All other wires are positive
    SAT variables. Reuse is valid under *assumptions*, never permanent target
    unit clauses. No numeric elimination pivots are cached.
    """
    def __init__(self):
        self.nvars = 1
        self.clauses = [[1]]
        self.xors = []
        self.gates = []
        self._xor = {}
        self._and = {}

    def var(self):
        self.nvars += 1
        return self.nvars

    def xor(self, *wires):
        parity = set()
        for w in wires:
            if w:
                parity.symmetric_difference_update([w])
        key = tuple(sorted(parity))
        if not key:
            return 0
        if len(key) == 1:
            return key[0]
        if key not in self._xor:
            out = self.var()
            self._xor[key] = out
            self.xors.append(([*key, out], False))
            self.gates.append((out, "xor", key))
        return self._xor[key]

    def land(self, a, b):
        if not a or not b:
            return 0
        if a == 1 or a == b:
            return b
        if b == 1:
            return a
        key = tuple(sorted((a, b)))
        if key not in self._and:
            out = self.var()
            self._and[key] = out
            self.clauses.extend([[-out, a], [-out, b], [out, -a, -b]])
            self.gates.append((out, "and", key))
        return self._and[key]

    def zero(self, w, guard=None):
        if w:
            self.clauses.append(([-guard] if guard is not None else []) + [-w])

    def solver(self):
        import pycryptosat
        s = pycryptosat.Solver(threads=1)
        # Register even unconstrained input variables before assumptions.
        s.add_clause([self.nvars, -self.nvars])
        for clause in self.clauses:
            s.add_clause(clause)
        for wires, rhs in self.xors:
            s.add_xor_clause(wires, rhs)
        return s

    def evaluate(self, inputs):
        """Independent gate evaluation for circuit/arithmetic regression tests."""
        values = {0: False, 1: True, **inputs}
        for out, op, wires in self.gates:
            values[out] = (sum(values[w] for w in wires) % 2 == 1
                           if op == "xor" else all(values[w] for w in wires))
        return values


class FieldCircuit:
    def __init__(self, F, circuit):
        self.F, self.c = F, circuit
        self.one = self.constant(1)
        self.zero = self.constant(0)
        self._mul = {}
        self._square = {}

    def constant(self, x):
        return tuple((x >> j) & 1 for j in range(self.F.n))

    def inputs(self):
        return tuple(self.c.var() for _ in range(self.F.n))

    def add(self, *xs):
        return tuple(self.c.xor(*bits) for bits in zip(*xs))

    def linear(self, wires, basis):
        return tuple(self.c.xor(*(w for w, b in zip(wires, basis) if b >> j & 1))
                     for j in range(self.F.n))

    def square(self, x):
        if x not in self._square:
            self._square[x] = self.linear(x, [self.F.sqr(1 << j) for j in range(self.F.n)])
        return self._square[x]

    def mul(self, x, y):
        key = tuple(sorted((x, y)))
        if key not in self._mul:
            terms = [[] for _ in range(2 * self.F.n - 1)]
            for i, a in enumerate(x):
                for j, b in enumerate(y):
                    terms[i + j].append(self.c.land(a, b))
            wide = [self.c.xor(*row) for row in terms]
            basis = [self.F.pow(2, j) for j in range(len(wide))]
            self._mul[key] = self.linear(wide, basis)
        return self._mul[key]

    def pow(self, x, e):
        out = self.one
        while e:
            if e & 1:
                out = self.mul(out, x)
            e >>= 1
            if e:
                x = self.square(x)
        return out

    def s3(self, x, y, z):
        # S3 = (xy)^2 + (xz)^2 + (yz)^2 + xyz + 1 (b=1).
        xy = self.mul(x, y)
        return self.add(self.square(xy), self.square(self.mul(x, z)),
                        self.square(self.mul(y, z)), self.mul(xy, z), self.one)

    def s4(self, x, y, z, r):
        # The existing symmetrized S4 formula, evaluated as a circuit. This
        # eliminates the intermediate coordinate, but retains AND gate vars.
        e1 = self.add(x, y, z)
        xy = self.mul(x, y)
        e2 = self.add(xy, self.mul(x, z), self.mul(y, z))
        e3 = self.mul(xy, z)
        terms = ((0, 0, 0, 4), (0, 0, 1, 3), (0, 0, 2, 0),
                 (0, 0, 2, 4), (0, 0, 3, 1), (0, 0, 4, 0),
                 (0, 2, 0, 2), (0, 2, 1, 3), (0, 4, 0, 4),
                 (2, 0, 1, 1), (2, 0, 2, 2), (4, 0, 0, 0))
        powers = [{e: self.pow(a, e) for e in {t[i] for t in terms}}
                  for i, a in enumerate((e1, e2, e3, r))]
        result = self.zero
        for term in terms:
            product = self.one
            for i, e in enumerate(term):
                if e:
                    product = self.mul(product, powers[i][e])
            result = self.add(result, product)
        return result


def scalar(E, k, P):
    out = INF
    while k:
        if k & 1:
            out = E.add(out, P)
        P = E.add(P, P)
        k >>= 1
    return out


def subgroup_order(n):
    # Trace recurrence for E0/F2: t0=2, t1=-1, tn=-t(n-1)-2t(n-2).
    a, b = 2, -1
    for _ in range(2, n + 1):
        a, b = b, -b - 2 * a
    return ((1 << n) + 1 - b) // 4


def bases(F, l, phases):
    if not 1 <= l <= F.n or len(phases) != 3:
        raise ValueError("need 1 <= l <= n and exactly three phases")
    return [[F.frob(1 << j, a % F.n) for j in range(l)] for a in phases]


def payload_x(payload, basis):
    out = 0
    for j, b in enumerate(basis):
        if payload >> j & 1:
            out ^= b
    return out


class Template:
    def __init__(self, F, l, phases, encoding):
        if encoding not in ("s4", "s3-chain"):
            raise ValueError(encoding)
        self.F, self.l = F, l
        self.bases = bases(F, l, phases)
        self.c = c = Circuit()
        self.fc = fc = FieldCircuit(F, c)
        self.payload = [[c.var() for _ in range(l)] for _ in range(3)]
        self.target = fc.inputs()
        self.xs = [fc.linear(w, basis) for w, basis in zip(self.payload, self.bases)]
        # Exclude x=0: its lift is small torsion, not an admissible factor.
        for w in self.payload:
            c.clauses.append(list(w))
        x, y, z = self.xs
        if encoding == "s4":
            for w in fc.s4(x, y, z, self.target):
                c.zero(w)
        else:
            self.intermediate = fc.inputs()
            self.finite = c.var()
            for eq in (fc.s3(x, y, self.intermediate),
                       fc.s3(self.intermediate, z, self.target)):
                for w in eq:
                    c.zero(w, self.finite)
            # Complete the chain's missing infinity branch:
            # P1=-P2, P3=R, hence x1=x2 and x3=xR. Lift verification below
            # resolves signs and rejects spurious rational/subgroup models.
            for w in (*fc.add(x, y), *fc.add(z, self.target)):
                c.zero(w, -self.finite)

    def boolean_equations(self, target_x, guess_bits=0, guess=0):
        """Exact Boolean ANFs for a *fresh* specialized circuit, for F4 replay.

        Masks use SAT wire indices minus one. Each clause l1 OR ... OR lk
        becomes product(1+li)=0, reduced by v^2=v. XORs are linear ANFs.
        This is a gate-variable formulation, not the fully expanded S4 ANF.
        """
        if not 0 <= target_x < 1 << self.F.n:
            raise ValueError("target outside field")
        wires = list(itertools.chain.from_iterable(self.payload))
        if not 0 <= guess_bits <= len(wires) or not 0 <= guess < 1 << guess_bits:
            raise ValueError("invalid hybrid slice")
        clauses = self.c.clauses + [[a] for a in self.target_assumptions(target_x)]
        clauses += [[w if guess >> j & 1 else -w] for j, w in enumerate(wires[:guess_bits])]
        equations = []
        for clause in clauses:
            poly = {0}
            for lit in clause:
                bit = 1 << (abs(lit) - 1)
                factor = {0, bit} if lit > 0 else {bit}
                out = set()
                for a in poly:
                    for b in factor:
                        out.symmetric_difference_update([a | b])
                poly = out
            equations.append(poly)
        for row, rhs in self.c.xors:
            equations.append({1 << (w - 1) for w in row} ^ ({0} if rhs else set()))
        return equations

    def export_msolve(self, path, target_x, guess_bits=0, guess=0):
        """Export coefficients in F2 plus explicit field equations for msolve."""
        path = Path(path)
        if path.exists():
            raise FileExistsError(path)
        equations = self.boolean_equations(target_x, guess_bits, guess)
        def mono(mask):
            return "*".join(f"v{j+1}" for j in range(self.c.nvars) if mask >> j & 1) or "1"
        polys = ["+".join(mono(m) for m in sorted(eq)) for eq in equations if eq]
        polys += [f"v{j}^2+v{j}" for j in range(1, self.c.nvars + 1)]
        path.write_text(",".join(f"v{j}" for j in range(1, self.c.nvars + 1))
                        + "\n2\n" + ",\n".join(polys) + "\n")

    def target_assumptions(self, x):
        return [w if x >> j & 1 else -w for j, w in enumerate(self.target)]

    def assignment(self, model):
        return [sum(int(bool(model[w])) << j for j, w in enumerate(block))
                for block in self.payload]

    def verify(self, E, order, target, payloads):
        pts = []
        for payload, basis in zip(payloads, self.bases):
            x = payload_x(payload, basis)
            p = E.lift_x(x) if x else None
            if p is None or not scalar(E, order, p).inf:
                return None
            pts.append(p)
        for signs in range(8):
            signed = [E.neg(p) if signs >> i & 1 else p for i, p in enumerate(pts)]
            if E.sum(signed) == target:
                return signed
        return None

    def search(self, solver, E, order, target, guess_bits, timeout):
        start_wall, start_cpu = time.monotonic(), time.process_time()
        deadline = start_wall + timeout
        wires = list(itertools.chain.from_iterable(self.payload))
        if not 0 <= guess_bits <= len(wires):
            raise ValueError("invalid guess_bits")
        target_assumptions = self.target_assumptions(target.x)
        calls = rejected = 0
        verify_cpu = solver_cpu = 0.0
        result = {"status": "unsat", "payloads": None, "points": None}
        for guess in range(1 << guess_bits):
            assumptions = target_assumptions + [w if guess >> j & 1 else -w
                                                for j, w in enumerate(wires[:guess_bits])]
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    result["status"] = "timeout"
                    break
                t = time.process_time()
                sat, model = solver.solve(assumptions=assumptions, time_limit=remaining)
                solver_cpu += time.process_time() - t
                calls += 1
                if sat is None:
                    result["status"] = "timeout"
                    break
                if not sat:
                    break
                payloads = self.assignment(model)
                t = time.process_time()
                pts = self.verify(E, order, target, payloads)
                verify_cpu += time.process_time() - t
                if pts is not None:
                    result.update(status="sat", payloads=payloads,
                                  points=[[p.x, p.y] for p in pts])
                    break
                rejected += 1
                # A point-invalid tuple is invalid for either sign of this
                # target. Guard by target bits so another target remains valid.
                block = [-a for a in target_assumptions]
                block += [-w if model[w] else w for w in wires]
                solver.add_clause(block)
            if result["status"] in ("sat", "timeout"):
                break
        return {**result, "calls": calls, "rejected": rejected,
                "solver_cpu_s": solver_cpu, "verify_cpu_s": verify_cpu,
                "search_cpu_s": time.process_time() - start_cpu,
                "search_wall_s": time.monotonic() - start_wall}


def direct_anf(F, l, phases, target_x):
    """Fully expanded numeric-target S4 descent: the existing harness model,
    generalized to a separate Frobenius-transformed basis in each block.
    """
    import sumpoly
    def mul(p, q):
        out = {}
        for a, ca in p.items():
            for b, cb in q.items():
                out[a | b] = out.get(a | b, 0) ^ F.mul(ca, cb)
        return {k: v for k, v in out.items() if v}
    powers = []
    for i, basis in enumerate(bases(F, l, phases)):
        x = {1 << (i * l + j): b for j, b in enumerate(basis)}
        x2 = {k: F.sqr(v) for k, v in x.items()}
        powers.append([{0: 1}, x, x2, mul(x, x2), {k: F.sqr(v) for k, v in x2.items()}])
    out = {}
    for mono in sorted(sumpoly.load(4)[4]):
        p = {0: F.pow(target_x, mono[3])}  # b=1
        for i in range(3):
            p = mul(p, powers[i][mono[i]])
        for k, v in p.items():
            out[k] = out.get(k, 0) ^ v
    return {k: v for k, v in out.items() if v}


class AnfTemplate(Template):
    """Fresh numeric-target ANF baseline, sharing only verification machinery."""
    def __init__(self, F, l, phases, target_x):
        self.F, self.l, self.bases = F, l, bases(F, l, phases)
        self.c = c = Circuit()
        self.payload = [[c.var() for _ in range(l)] for _ in range(3)]
        self.target = tuple(c.var() for _ in range(F.n))
        flat = list(itertools.chain.from_iterable(self.payload))
        equations = [[] for _ in range(F.n)]
        for mask, coefficient in sorted(direct_anf(F, l, phases, target_x).items()):
            w = 1
            for j, bit in enumerate(flat):
                if mask >> j & 1:
                    w = c.land(w, bit)
            for j in range(F.n):
                if coefficient >> j & 1:
                    equations[j].append(w)
        for eq in equations:
            c.zero(c.xor(*eq))
        for block in self.payload:
            c.clauses.append(list(block))


def exact_oracle(E, order, basis_blocks, target):
    """Point MITM reference, with no summation polynomials or SAT machinery."""
    blocks = []
    for basis in basis_blocks:
        pts = []
        for u in range(1, 1 << len(basis)):
            p = E.lift_x(payload_x(u, basis))
            if p is not None and scalar(E, order, p).inf:
                pts.extend([(u, p), (u, E.neg(p))])
        blocks.append(pts)
    pairs = {}
    for u, p in blocks[0]:
        for v, q in blocks[1]:
            pairs[E.add(p, q)] = (u, v)
    for w, p in blocks[2]:
        key = E.add(target, E.neg(p))
        if key in pairs:
            return (*pairs[key], w)
    return None


def corpus(E, order, count, seed):
    """Blind targets in the order-r subgroup; no planted decompositions."""
    rng = random.Random(seed)
    while True:
        G = scalar(E, 4, E.random_point(rng))
        if not G.inf and scalar(E, order, G).inf:
            break
    if count > (order - 1) // 2:
        raise ValueError("too many targets for distinct sign-orbits")
    # Unique up to sign: repeated x(R) must not make reuse look artificially cheap.
    return [scalar(E, k, G) for k in rng.sample(range(1, (order + 1) // 2), count)]


def benchmark(n, l, phases, encoding, mode, guess_bits, count, seed, timeout):
    # The common field/curve initialization is charged to each contender.
    start_cpu, start_wall = time.process_time(), time.monotonic()
    F = GF2n(n)
    E, order = Curve(F, 1), subgroup_order(n)
    if order <= 2 or any(order % d == 0 for d in range(2, math.isqrt(order) + 1)):
        raise ValueError("blind corpus requires a prime order-r subgroup larger than two")
    common_cpu = time.process_time() - start_cpu
    # Fixed corpus creation/oracle are experimental instrumentation, excluded
    # from this PDP-only measurement and explicitly reported separately.
    ti = time.process_time()
    targets = corpus(E, order, count, seed)
    bs = bases(F, l, phases)
    truth = [exact_oracle(E, order, bs, R) for R in targets]
    oracle_cpu = time.process_time() - ti
    build_cpu = load_cpu = 0.0
    rows = []
    template = solver = None
    for idx, (R, expected) in enumerate(zip(targets, truth)):
        if template is None or mode == "cold":
            t = time.process_time()
            template = (AnfTemplate(F, l, phases, R.x) if encoding == "anf-s4"
                        else Template(F, l, phases, encoding))
            build_cpu += time.process_time() - t
        if solver is None or mode != "incremental":
            t = time.process_time()
            solver = template.c.solver()
            load_cpu += time.process_time() - t
        row = template.search(solver, E, order, R, guess_bits, timeout)
        decided = row["status"] != "timeout"
        correct = ((row["status"] == "sat") == (expected is not None)) if decided else None
        if correct is False:
            raise AssertionError(f"oracle mismatch n={n} l={l} index={idx}: {row}")
        rows.append({"index": idx, "target": [R.x, R.y], "oracle_sat": expected is not None,
                     "correct": correct, **row})
    total_cpu = time.process_time() - start_cpu - oracle_cpu
    target_json = json.dumps([[R.x, R.y] for R in targets], separators=(",", ":"))
    statuses = Counter(row["status"] for row in rows)
    return {"n": n, "modulus": F.mod, "subgroup_order": order, "l": l,
            "phases": phases, "encoding": encoding, "mode": mode,
            "guess_bits": guess_bits, "seed": seed, "targets": count,
            "target_sha256": hashlib.sha256(target_json.encode()).hexdigest(),
            "statuses": dict(statuses), "verified": statuses["sat"],
            "oracle_sat": sum(x is not None for x in truth),
            "common_cpu_s": common_cpu, "build_cpu_s": build_cpu,
            "load_cpu_s": load_cpu, "total_cpu_s": total_cpu,
            "cpu_s_per_verified": total_cpu / statuses["sat"] if statuses["sat"] else None,
            "elapsed_wall_s_including_oracle": time.monotonic() - start_wall,
            "oracle_and_corpus_cpu_s_excluded": oracle_cpu,
            "variables": template.c.nvars, "and_gates": len(template.c._and),
            "xor_gates": len(template.c._xor), "base_clauses": len(template.c.clauses),
            "rows": rows}


def main():
    import pycryptosat
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, nargs="+", default=[7, 13])
    p.add_argument("--l", type=int, nargs="+", default=[4])
    p.add_argument("--seeds", type=int, nargs="+", default=[17, 911])
    p.add_argument("--targets", type=int, default=8)
    p.add_argument("--timeout", type=float, default=1.0, help="shared per-target search budget")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if any(n < 3 or n % 2 == 0 or n > 31 for n in args.n):
        p.error("this diagnostic supports odd 3 <= n <= 31")
    if any((r := subgroup_order(n)) <= 2 or any(r % d == 0 for d in range(2, math.isqrt(r) + 1))
           for n in args.n):
        p.error("choose n with prime (#E/4) > 2 for the blind subgroup corpus")
    if args.targets <= 0 or args.timeout <= 0 or any(l < 1 or l > min(args.n) for l in args.l):
        p.error("invalid targets, timeout or payload dimension")
    if any(args.targets > (subgroup_order(n) - 1) // 2 for n in args.n):
        p.error("targets exceed the number of distinct nonzero sign-orbits")
    if args.out.exists():
        p.error("output exists; choose a new run path")
    variants = [("cold", 0), ("template", 0), ("incremental", 0), ("incremental", 2)]
    configs = list(itertools.product(args.n, args.l, args.seeds, [(0, 0, 0), (0, 1, 2)],
                                    ["s4", "s3-chain"], variants))
    configs += [(n, l, seed, phases, "anf-s4", ("cold", 0))
                for n, l, seed, phases in itertools.product(args.n, args.l, args.seeds,
                                                           [(0, 0, 0), (0, 1, 2)])]
    # Fixed shuffle reduces systematic ordering effects, without tuning to timing.
    random.Random(20260922).shuffle(configs)
    output = {"schema": "fixed-phase-pdp/v1", "scope": "PDP stage only; no DLP/rho speed claim",
              "python": platform.python_version(), "platform": platform.platform(),
              "pycryptosat": pycryptosat.__version__, "timeout_s": args.timeout,
              "config_shuffle_seed": 20260922, "runs": []}
    output["source_sha256"] = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                               for name in ("fixed_phase.py", "gf2n.py", "sumpoly.py")}
    output["base_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for n, l, seed, phases, encoding, (mode, g) in configs:
        r = benchmark(n, l, phases, encoding, mode, g, args.targets, seed, args.timeout)
        output["runs"].append(r)
        args.out.write_text(json.dumps(output, indent=2) + "\n")
        print(n, l, seed, phases, encoding, mode, g, r["statuses"], round(r["total_cpu_s"], 4), flush=True)


if __name__ == "__main__":
    main()
