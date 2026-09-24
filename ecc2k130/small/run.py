#!/usr/bin/env python3
"""Solve a small ECC2K-like Koblitz challenge on the Metal walker.

    run.py selftest CURVE.json          GPU arithmetic against field.py
    run.py solve CURVE.json [options]   walk to a collision, solve, verify

CURVE.json is a challenges/ecc/curves record: y^2 + xy = x^3 + a x^2 + 1
over F_2^m (m <= 127) with a prime subgroup order.  The challenge's field is
mapped into a sparse-polynomial field the kernel reduces cheaply; the
recovered log is checked in the challenge's own field with
challenges/ecc/generate.py's independent scalar multiplication.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import struct
import subprocess
import sys
import time
from pathlib import Path

import field as fl

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BINARY = HERE.parent / "build" / "ksmall"
KBASE = 12  # m^12 start points: 6 bases gave repeated starts at m = 83

sys.path.insert(0, str(REPO / "challenges" / "ecc"))
import generate as gen  # noqa: E402


def tonelli(n: int, p: int) -> int:
    r = gen.tonelli(n, p)
    if r is None:
        raise ValueError("no square root")
    return r


class Setup:
    def __init__(self, curve_path: Path, seed: int = 1):
        rec = json.loads(curve_path.read_text())
        self.rec = rec
        self.id = rec["id"]
        fld = rec["field"]
        if fld["type"] != "binary" or rec.get("family") != "binary-koblitz":
            raise SystemExit("not a binary Koblitz curve record")
        self.m = m = int(fld["degree"])
        if m > 127:
            raise SystemExit("the kernel handles m <= 127")
        self.a = int(rec["a"], 16)
        if int(rec["b"], 16) != 1:
            raise SystemExit("expected b = 1")
        self.src_terms = sorted(fld["polynomial_terms"], reverse=True)
        self.n = int(rec["subgroup_order"], 16)
        self.G_src = (int(rec["generator"]["x"], 16), int(rec["generator"]["y"], 16))
        self.Q_src = (int(rec["target"]["x"], 16), int(rec["target"]["y"], 16))
        self.known_log = int(rec["known_log"], 16) if rec.get("known_log") else None

        self.terms = fl.gpu_polynomial(m)
        self.F = fl.Field(m, sum(1 << t for t in self.terms))
        self.E = fl.Curve(self.F, self.a)
        self.nw = (m + 31) // 32
        phi = fl.isomorphism(self.src_terms, self.F, seed)
        self.P = (phi(self.G_src[0]), phi(self.G_src[1]))
        self.Q = (phi(self.Q_src[0]), phi(self.Q_src[1]))
        assert self.E.on_curve(self.P) and self.E.on_curve(self.Q), "isomorphism broke the curve"
        assert self.E.mul(self.n, self.P) is fl.INF and self.E.mul(self.n, self.Q) is fl.INF

        # sigma(P) = lambda P with lambda^2 - mu lambda + 2 = 0 mod n.
        mu = -1 if self.a == 0 else 1
        root = tonelli(-7 % self.n, self.n)
        half = pow(2, -1, self.n)
        fP = self.E.frob(self.P)
        for r in (root, self.n - root):
            lam = (mu + r) * half % self.n
            if self.E.mul(lam, self.P) == fP:
                self.lam = lam
                break
        else:
            raise RuntimeError("no Frobenius eigenvalue")

        self.beta, self.rows = fl.normal_basis(self.F)
        rng = random.Random(f"{self.id}:bases:{seed}")
        self.base_logs = [rng.randrange(1, self.n) for _ in range(KBASE)]
        self.bases = [self.E.mul(r, self.P) for r in self.base_logs]

    # -- expectations --
    def expected_iterations(self) -> float:
        return math.sqrt(math.pi * self.n / (4 * self.m))

    def dp_probability(self, t: int) -> float:
        # x-coordinates of the prime-order subgroup have trace 0, i.e. even weight.
        good = sum(math.comb(self.m, w) for w in range(0, t + 1, 2))
        return good / 2 ** (self.m - 1)

    def dp_cutoff(self, bits: float) -> int:
        best = min(range(0, self.m + 1, 2), key=lambda t: abs(math.log2(max(self.dp_probability(t), 1e-300)) + bits))
        return best

    # -- the kernel's prelude --
    def prelude(self, batch: int, dpw: int) -> str:
        nw = self.nw
        words = lambda v: "{" + ", ".join(f"0x{w:08x}u" for w in fl.to_words(v, nw)) + "}"
        mid = [t for t in self.terms if t != self.m]
        lines = [
            "#include <metal_stdlib>",
            "using namespace metal;",
            f"// {self.id}: F_2^{self.m} = F_2[z]/({' + '.join('z^%d' % t for t in self.terms)})",
            f"#define M {self.m}",
            f"#define NW {nw}",
            f"#define NTERMS {len(mid)}",
            f"#define BATCH {batch}",
            f"#define DPW {dpw}",
            f"#define KBASE {KBASE}",
            f"#define J_BASE {fl.J_BASE}",
            f"#define J_COUNT {fl.J_COUNT}",
            f"constant int kTerms[NTERMS] = {{{', '.join(map(str, mid))}}};",
            f"constant uint kCurveA[NW] = {words(self.a)};",
            f"constant uint kQX[NW] = {words(self.Q[0])};",
            f"constant uint kQY[NW] = {words(self.Q[1])};",
            "constant uint kBaseX[KBASE][NW] = {" + ", ".join(words(B[0]) for B in self.bases) + "};",
            "constant uint kBaseY[KBASE][NW] = {" + ", ".join(words(B[1]) for B in self.bases) + "};",
            "constant uint kNormal[M][NW] = {" + ",\n  ".join(words(r) for r in self.rows) + "};",
            "",
        ]
        return "\n".join(lines)

    # -- bookkeeping for a report --
    def start_log(self, seed: int) -> int:
        es = fl.start_exponents(seed, KBASE, self.m)
        return sum(r * pow(self.lam, e, self.n) for r, e in zip(self.base_logs, es)) % self.n

    def walk_factor(self, counts) -> int:
        c = 1
        for i, k in enumerate(counts):
            c = c * pow(1 + pow(self.lam, fl.J_BASE + i, self.n), k, self.n) % self.n
        return c


def write_workdir(S: Setup, work: Path, batch: int, dpw: int, extra: dict):
    work.mkdir(parents=True, exist_ok=True)
    (work / "shader.metal").write_text(S.prelude(batch, dpw) + (HERE / "ksmall.metal").read_text())
    cfg = {"M": S.m, "NW": S.nw, "batch": batch, **extra}
    (work / "config.json").write_text(json.dumps(cfg, indent=2))


def ensure_binary():
    subprocess.run(["make", "-s", "-C", str(HERE), "../build/ksmall"], check=True)


def cmd_selftest(args):
    S = Setup(Path(args.curve), args.seed)
    ensure_binary()
    work = Path(args.work or f"/tmp/ksmall-{S.id}-selftest-{os.getpid()}")
    rng = random.Random(7)
    cases = args.cases
    ins, seeds, expect = [], [], []
    for i in range(cases):
        a = rng.getrandbits(S.m) or 1
        b = rng.getrandbits(S.m)
        Pt = S.E.mul(rng.randrange(1, S.n), S.P)
        seed = rng.getrandbits(40)
        for v in (a, b, Pt[0], Pt[1]):
            ins += fl.to_words(v, S.nw)
        seeds.append(seed)
        nxt, j = fl.step(S.E, Pt, S.rows)
        st = fl.start_point(S.E, seed, S.Q, S.bases, S.m)
        expect.append((S.F.mul(a, b), S.F.sqr(a), S.F.inv(a), nxt, st, fl.weight(Pt[0], S.rows), j))
    write_workdir(S, work, 1, 0, {"cases": cases})
    (work / "selftest-in.bin").write_bytes(struct.pack(f"<{len(ins)}I", *ins))
    (work / "selftest-seeds.bin").write_bytes(struct.pack(f"<{cases}Q", *seeds))
    out = subprocess.run([str(BINARY), "selftest", str(work)], check=True, capture_output=True, text=True)
    print(out.stdout.strip())
    raw = (work / "selftest-out.bin").read_bytes()
    nw = S.nw
    words = struct.unpack(f"<{cases * 7 * nw + cases * 3}I", raw)
    bad = 0
    for i, (mul, sqr, inv, nxt, st, hw, j) in enumerate(expect):
        got = [fl.from_words(words[(i * 7 + k) * nw:(i * 7 + k + 1) * nw]) for k in range(7)]
        tail = words[cases * 7 * nw + i * 3: cases * 7 * nw + i * 3 + 3]
        want = [mul, sqr, inv, nxt[0], nxt[1], st[0], st[1]]
        names = ["mul", "sqr", "inv", "step.x", "step.y", "start.x", "start.y"]
        for name, g, w in zip(names, got, want):
            if g != w:
                bad += 1
                if bad <= 10:
                    print(f"case {i} {name}: gpu {g:#x} want {w:#x}")
        if tail[0] != hw or tail[1] != j or tail[2] != 3:
            bad += 1
            if bad <= 10:
                print(f"case {i} hw/j/ok: gpu {tuple(tail)} want {(hw, j, 3)}")
    checks = cases * 10
    print(json.dumps({"curve": S.id, "polynomial": S.terms, "checks": checks, "failures": bad}))
    return 1 if bad else 0


def solve_collision(S: Setup, col: dict):
    ra, rb = col["a"], col["b"]
    pts = []
    for r in (ra, rb):
        u = S.start_log(r["seed"])
        c = S.walk_factor(r["counts"])
        R = (int(r["x"], 16), int(r["y"], 16))
        # The reported point must be c (u P + Q): re-derives the whole trail's bookkeeping.
        want = S.E.add(S.E.mul(c * u % S.n, S.P), S.E.mul(c, S.Q))
        if want != R:
            return {"status": "bookkeeping-mismatch", "seed": r["seed"]}
        pts.append((R, u, c))
    (Ra, ua, ca), (Rb, ub, cb) = pts
    for s in range(S.m):
        xb, yb = S.F.sqrn(Rb[0], s), S.F.sqrn(Rb[1], s)
        if xb == Ra[0]:
            eps = 1 if yb == Ra[1] else -1
            assert eps == 1 or (yb ^ xb) == Ra[1]
            break
    else:
        return {"status": "not-same-class"}
    # c_a (u_a + k) = eps lambda^s c_b (u_b + k)  (mod n)
    t = eps * pow(S.lam, s, S.n) * cb % S.n
    den = (ca - t) % S.n
    if den == 0:
        return {"status": "degenerate", "frobenius": s, "sign": eps}
    k = (t * ub - ca * ua) * pow(den, -1, S.n) % S.n
    # Independent check in the challenge's own field and basis.
    ok = gen.bin_mul_point(k, S.G_src, S.a, 1, S.m) == S.Q_src
    return {"status": "solved" if ok else "wrong", "log": hex(k), "frobenius": s, "sign": eps,
            "trailSteps": [ra["steps"], rb["steps"]]}


def cmd_solve(args):
    t_setup = time.time()
    S = Setup(Path(args.curve), args.seed)
    ensure_binary()
    W = S.expected_iterations()
    lanes = args.threads * args.batch
    dp_bits = args.dp_bits if args.dp_bits is not None else max(2.0, math.floor(math.log2(W) - math.log2(lanes) - 5))
    dpw = S.dp_cutoff(dp_bits)
    p = S.dp_probability(dpw)
    trail = 1 / p
    steps = args.steps or int(min(4096, max(64, 2 ** 27 // lanes), max(64, W / lanes / 8)))
    dp_cap = min(1 << 22, max(4096, int(4 * lanes * steps * p) + 1024))
    work = Path(args.work or f"/tmp/ksmall-{S.id}-{time.strftime('%Y%m%d-%H%M%S')}")
    if work.exists() and any(work.iterdir()):
        raise SystemExit(f"{work} is not empty")
    write_workdir(S, work, args.batch, dpw, {
        "threads": args.threads, "steps": steps, "dpCap": dp_cap,
        "maxTrail": int(min(2 ** 31, 40 * trail)), "collisions": args.collisions,
        "seedBase": args.seed_base, "maxSeconds": args.max_seconds,
        "progressEvery": args.progress_every, "threadgroup": args.threadgroup,
        "keepDps": args.keep_dps,
    })
    plan = {
        "curve": S.id, "m": S.m, "a": S.a, "subgroupBits": S.n.bit_length(),
        "gpuPolynomial": S.terms, "challengePolynomial": S.src_terms,
        "lambda": hex(S.lam), "normalElement": hex(S.beta),
        "expectedIterations": W, "log2ExpectedIterations": math.log2(W),
        "dpWeightCutoff": dpw, "dpProbability": p, "log2Trail": math.log2(trail),
        "lanes": lanes, "parallelOverheadFraction": lanes * trail / W,
        "setupSeconds": round(time.time() - t_setup, 3), "work": str(work),
    }
    print(json.dumps(plan, indent=2), flush=True)
    proc = subprocess.run([str(BINARY), "run", str(work)], stdout=subprocess.PIPE, text=True)
    if proc.returncode not in (0, 3):
        raise SystemExit(f"ksmall failed with {proc.returncode}")
    stats = json.loads(proc.stdout.strip().splitlines()[-1])
    results = []
    path = work / "collisions.jsonl"
    for line in (path.read_text().splitlines() if path.exists() else []):
        results.append(solve_collision(S, json.loads(line)))
    solved = [r for r in results if r["status"] == "solved"]
    summary = {
        **plan, "run": stats, "collisions": results,
        "solved": bool(solved), "log": solved[0]["log"] if solved else None,
        "iterationsOverExpected": stats["iterations"] / W,
    }
    if S.known_log is not None and solved:
        summary["knownLogMatches"] = int(solved[0]["log"], 16) == S.known_log
    (work / "result.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in ("curve", "solved", "log", "iterationsOverExpected")} |
                     {"iterations": stats["iterations"], "rateMps": stats["iterationsPerSecondGpu"] / 1e6,
                      "wallSeconds": stats["wallSeconds"], "collisions": [r["status"] for r in results],
                      "result": str(work / "result.json")}, indent=2))
    return 0 if solved else 2


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("selftest")
    t.add_argument("curve")
    t.add_argument("--cases", type=int, default=64)
    t.add_argument("--seed", type=int, default=1)
    t.add_argument("--work")
    s = sub.add_parser("solve")
    s.add_argument("curve")
    s.add_argument("--threads", type=int, default=8192)
    s.add_argument("--batch", type=int, default=8)
    s.add_argument("--threadgroup", type=int, default=64)
    s.add_argument("--steps", type=int, default=0, help="walk steps per launch (default: 2^27 / lanes)")
    s.add_argument("--dp-bits", type=float, help="log2 of the mean trail length")
    s.add_argument("--collisions", type=int, default=1)
    s.add_argument("--max-seconds", type=float, default=0)
    s.add_argument("--progress-every", type=int, default=16)
    s.add_argument("--seed", type=int, default=1, help="isomorphism root choice and start-point bases")
    s.add_argument("--seed-base", type=int, default=1)
    s.add_argument("--keep-dps", action="store_true")
    s.add_argument("--work")
    args = ap.parse_args()
    sys.exit(cmd_selftest(args) if args.cmd == "selftest" else cmd_solve(args))


if __name__ == "__main__":
    main()
