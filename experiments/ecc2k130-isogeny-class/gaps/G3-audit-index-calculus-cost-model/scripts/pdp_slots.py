"""H1 vs H2: cost of the algebraic PDP with one shared factor-base subspace (plain, GGMP H1)
versus GGMP 2020 Sec 3.1 ordered tau-slots (x_i in V_i = V_0^(2^i), GGMP H2), same solver
(msolve F4, grevlex, F_2 with field equations, 1 thread), same curve E: y^2+xy=x^3+1 over F_{2^n},
same targets.  GGMP assume H1 = H2, which is what turns the m! gain in the relation probability
into an m! gain in relation-collection cost.

The Weil descent generalises experiments/pdp-scaling/descend.py (repo, read-only; copied helper
modules gf2n.py / sumpoly.py live in scripts/pdpcopy) to a per-slot basis: x_i = sum_j v_ij w_ij.

Subspaces: normal element beta; ordered slot i basis = beta^(2^(m j + i)), j < l (GGMP's
construction, pairwise disjoint); plain: every slot uses the slot-0 basis.
Targets: 'planted' (R = P_1 + ... + P_m with P_i in the slot factor bases, satisfiable) and
'random' (R a random point: almost always no decomposition, which is the dominant case in
relation collection).

usage: python3 pdp_slots.py OUT.jsonl n m l seeds timeout
"""
import json, os, random, resource, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdpcopy"))
import sumpoly
from gf2n import GF2n, Curve, Point, INF

MSOLVE = os.environ.get("MSOLVE", "/opt/homebrew/bin/msolve")


def rank(vecs):
    a = list(vecs); r = 0
    for bit in range(max(v.bit_length() for v in a) - 1, -1, -1):
        piv = next((i for i in range(r, len(a)) if a[i] >> bit & 1), None)
        if piv is None: continue
        a[r], a[piv] = a[piv], a[r]
        for i in range(len(a)):
            if i != r and a[i] >> bit & 1: a[i] ^= a[r]
        r += 1
    return r


def normal_element(F, rng):
    while True:
        b = F.random(rng)
        conj = [b]
        for _ in range(F.n - 1): conj.append(F.sqr(conj[-1]))
        if rank(conj) == F.n: return conj


def slot_polys(F, W, max_e):
    """blk[e] for x = sum_j v_j W[j]: {mask over the l v_j: coefficient}."""
    out = []
    for e in range(max_e + 1):
        poly = {0: 1}; k = 0; ee = e
        while ee:
            if ee & 1:
                lin = [(1 << j, F.frob(w, k)) for j, w in enumerate(W)]
                nxt = {}
                for mask, c in poly.items():
                    for vm, zc in lin:
                        nm = mask | vm
                        nxt[nm] = nxt.get(nm, 0) ^ F.mul(c, zc)
                poly = {mk: c for mk, c in nxt.items() if c}
            ee >>= 1; k += 1
        out.append(poly)
    return out


def descend(S, F, b, m, bases, xR):
    l = len(bases[0])
    p = S[m + 1]; max_e = 2 ** (m - 1)
    c = {}
    for mono in p:
        key = tuple(mono[:m])
        val = F.mul(F.pow(xR, mono[m]), F.pow(b, mono[sumpoly.B]))
        c[key] = c.get(key, 0) ^ val
    c = {k: v for k, v in c.items() if v}
    blks = [slot_polys(F, bases[i], max_e) for i in range(m)]
    A = {(0, k): v for k, v in c.items()}
    for i in range(m):
        nxt = {}; shift = i * l
        for (mask, rest), val in A.items():
            e, rest2 = rest[0], rest[1:]
            for bm, coef in blks[i][e].items():
                key = (mask | (bm << shift), rest2)
                nxt[key] = nxt.get(key, 0) ^ F.mul(coef, val)
        A = {k: v for k, v in nxt.items() if v}
    return {mask: val for (mask, _), val in A.items()}


def evaluate(anf, v):
    acc = 0
    for mask, c in anf.items():
        if mask & ~v == 0: acc ^= c
    return acc


def xs_of(bases, F, v, m, l):
    xs = []
    for i in range(m):
        x = 0
        for j in range(l):
            if v >> (i * l + j) & 1: x ^= bases[i][j]
        xs.append(x)
    return xs


def run_msolve(anf, n, nv, timeout):
    eqs = [set() for _ in range(n)]
    for mask, c in anf.items():
        t = 0
        while c:
            if c & 1: eqs[t].add(mask)
            c >>= 1; t += 1
    def mono(mask):
        return "1" if mask == 0 else "*".join(f"v{j}" for j in range(nv) if mask >> j & 1)
    with tempfile.TemporaryDirectory() as d:
        inp, outp = os.path.join(d, "in.ms"), os.path.join(d, "out.ms")
        with open(inp, "w") as fh:
            fh.write(",".join(f"v{j}" for j in range(nv)) + "\n2\n")
            polys = ["+".join(mono(mk) for mk in sorted(eq)) for eq in eqs if eq]
            polys += [f"v{j}^2+v{j}" for j in range(nv)]
            fh.write(",\n".join(polys) + "\n")
        r0 = resource.getrusage(resource.RUSAGE_CHILDREN); w0 = time.monotonic()
        try:
            r = subprocess.run([MSOLVE, "-g", "2", "-t", "1", "-f", inp, "-o", outp],
                               capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            r1 = resource.getrusage(resource.RUSAGE_CHILDREN)   # the killed child has been reaped
            return {"status": "timeout", "cpu": None,
                    "cpu_at_timeout": (r1.ru_utime + r1.ru_stime) - (r0.ru_utime + r0.ru_stime),
                    "wall": time.monotonic() - w0}
        r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = (r1.ru_utime + r1.ru_stime) - (r0.ru_utime + r0.ru_stime)
        if r.returncode != 0:
            return {"status": "error", "cpu": cpu, "stderr": r.stderr[-300:]}
        text = open(outp).read()
    body = text[text.index("[") + 1: text.rindex("]")]
    basis = [q.strip() for q in body.replace("\n", "").split(",") if q.strip()]
    return {"status": "unsat" if basis == ["1"] else "gb", "cpu": cpu,
            "wall": time.monotonic() - w0, "basis": basis}


def solutions_from_basis(basis, anf, nv):
    fixed = {}
    for p in basis:
        terms = [t.strip() for t in p.replace("-", "+").split("+") if t.strip()]
        vs = [t for t in terms if t.startswith("1*v") and "^" not in t and "*" not in t[2:]]
        consts = [t for t in terms if t == "1"]
        if len(vs) == 1 and len(terms) == len(vs) + len(consts):
            fixed[int(vs[0][3:])] = len(consts) % 2
    free = [j for j in range(nv) if j not in fixed]
    if len(free) > 18: return None, len(free)
    base = sum(c << j for j, c in fixed.items())
    sols = []
    for k in range(1 << len(free)):
        v = base
        for i, j in enumerate(free):
            if k >> i & 1: v |= 1 << j
        if evaluate(anf, v) == 0: sols.append(v)
    return sols, len(free)


def main():
    out, n, m, l, seeds, timeout = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), float(sys.argv[6])
    only = sys.argv[7].split(",") if len(sys.argv) > 7 else None   # e.g. "plain:random" (variant:target)
    assert m * l <= n
    S = sumpoly.load(m + 1)
    F = GF2n(n); E = Curve(F, 1)
    fh = open(out, "a")
    for seed in range(1, seeds + 1):
        rng = random.Random(1000 * n + 100 * l + seed)
        while True:
            # redraw the normal element until slot 0 has >= m liftable abscissae (a planted
            # plain instance needs m distinct x in V_0; at l = 3 some V_0 have fewer)
            conj = normal_element(F, rng)
            ordered_bases = [[conj[(m * j + i) % n] for j in range(l)] for i in range(m)]
            lift0 = 0
            for c in range(1, 1 << l):
                x = 0
                for j in range(l):
                    if c >> j & 1: x ^= ordered_bases[0][j]
                lift0 += E.lift_x(x) is not None
            if lift0 >= m: break
        plain_bases = [ordered_bases[0]] * m
        assert rank([w for B in ordered_bases for w in B]) == m * l
        # slot i = tau^i(slot 0)
        for i in range(m):
            assert ordered_bases[i] == [F.frob(w, i) for w in ordered_bases[0]]
        def fb_point(B):
            while True:
                c = rng.getrandbits(l)
                if c == 0: continue
                x = 0
                for j in range(l):
                    if c >> j & 1: x ^= B[j]
                P = E.lift_x(x)
                if P is not None: return P if rng.getrandbits(1) else E.neg(P)
        # targets: one planted per variant (planted in that variant's slots) + one shared random
        Rrand = E.random_point(rng)
        tgt = {}
        for var, bases in (("plain", plain_bases), ("ordered", ordered_bases)):
            while True:
                pts = [fb_point(bases[i]) for i in range(m)]
                R = E.sum(pts)
                if not R.inf and len({P.x for P in pts}) == m: break
            tgt[var] = R
        for var, bases in (("plain", plain_bases), ("ordered", ordered_bases)):
            for kind, R in (("planted", tgt[var]), ("random", Rrand)):
                if only is not None and f"{var}:{kind}" not in only:
                    continue
                t0 = time.process_time()
                anf = descend(S, F, 1, m, bases, R.x)
                tb = time.process_time() - t0
                res = run_msolve(anf, n, m * l, timeout)
                row = dict(n=n, m=m, l=l, seed=seed, variant=var, target=kind, monomials=len(anf),
                           build_cpu=round(tb, 3), status=res["status"], cpu=res.get("cpu"),
                           cpu_at_timeout=res.get("cpu_at_timeout"), wall=res.get("wall"))
                if res["status"] == "gb":
                    sols, nfree = solutions_from_basis(res["basis"], anf, m * l)
                    row["free_vars"] = nfree
                    if sols is not None:
                        # verify: x's lift and some sign pattern sums to +-R
                        good = 0
                        for v in sols:
                            xs = xs_of(bases, F, v, m, l)
                            Ps = [E.lift_x(x) for x in xs]
                            if any(P is None for P in Ps): continue
                            ok = False
                            for sg in range(1 << m):
                                Q = E.sum([E.neg(P) if sg >> i & 1 else P for i, P in enumerate(Ps)])
                                if not Q.inf and Q.x == R.x: ok = True; break
                            good += ok
                        row["solutions"] = len(sols); row["verified_solutions"] = good
                row["basis_size"] = len(res.get("basis", [])) if res.get("basis") else None
                fh.write(json.dumps(row) + "\n"); fh.flush()
                print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
