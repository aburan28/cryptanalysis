"""Factor-base / BSGS / rho tournament over 7-isogenous, rescaled models of
y^2 = x^3 + x^2 + 2x over F_83 (G=(26,58), Q=(61,82), Q=17G, n=41).

Cost unit ("ops"), per solve:
  group  = elliptic-curve additions + doublings (every add/dbl call = 1,
           including those inside scalar multiplications and membership tests)
  lookup = table probes (decomposition table, BSGS baby table, rho collision checks)
  la     = multiply-adds mod 41 in the linear algebra
  ops(w) = group + w*(lookup + la), primary w = 1; band w in {0, 0.1, 1}.
Isogeny transport and model rescaling are setup, not charged to any solver.
"""
import json, random, sys
from iso7 import kernels7, velu, short_from_general, j as jinv, count as npts
p, n = 83, 41
inv = lambda v: pow(v % p, -1, p)

class Ctr:
    def __init__(s): s.group = s.lookup = s.la = 0
    def ops(s, w=1.0): return s.group + w * (s.lookup + s.la)

def mk(A, C):
    def add(P, R):
        C.group += 1
        if P is None: return R
        if R is None: return P
        if P[0] == R[0]:
            if (P[1] + R[1]) % p == 0: return None
            l = (3 * P[0] * P[0] + A) * inv(2 * P[1]) % p
        else:
            l = (R[1] - P[1]) * inv(R[0] - P[0]) % p
        x = (l * l - P[0] - R[0]) % p
        return (x, (l * (P[0] - x) - P[1]) % p)
    def neg(P): return None if P is None else (P[0], -P[1] % p)
    def smul(k, P):
        R = None; k %= n
        for bit in bin(k)[2:] if k else "":
            R = add(R, R) if R is not None else R
            if bit == "1": R = add(R, P)
        return R
    return add, neg, smul

# ---------------- isogeny transport (exact, via F_p[z]/h) ----------------
def ext_ops(h):
    def mul(a, b):
        r = [0] * 5
        for i in range(3):
            for k in range(3): r[i + k] += a[i] * b[k]
        for d in (4, 3):  # z^3 = -(h0 + h1 z + h2 z^2)
            c = r[d]; r[d] = 0
            for t in range(3): r[d - 3 + t] -= c * h[t]
        return [c % p for c in r[:3]]
    def pw(a, e):
        r = [1, 0, 0]
        while e:
            if e & 1: r = mul(r, a)
            a = mul(a, a); e >>= 1
        return r
    s1 = -h[2] % p; s2 = h[1]
    p1, p2 = s1, (s1 * s1 - 2 * s2) % p
    tr = lambda c: (3 * c[0] + c[1] * p1 + c[2] * p2) % p
    return mul, pw, tr

def isogeny_eval(A, B, h, P):
    mul, pw, tr = ext_ops(h)
    z = [0, 1, 0]; z2 = mul(z, z); z3 = mul(z2, z)
    t = [(2 * A + 6 * z2[0]) % p, 6 * z2[1] % p, 6 * z2[2] % p]
    u = [4 * (z3[i] + A * z[i] + (B if i == 0 else 0)) % p for i in range(3)]
    x0, y0 = P
    d = [(x0 - z[0]) % p, -1 % p, 0]
    di = pw(d, p ** 3 - 2); di2 = mul(di, di); di3 = mul(di2, di)
    X = (x0 + tr(mul(t, di)) + tr(mul(u, di2))) % p
    dX = (1 - tr(mul(t, di2)) - 2 * tr(mul(u, di3))) % p
    return (X, y0 * dX % p)

KCACHE = {}
def kernels(A, B):
    if (A, B) not in KCACHE:
        KCACHE[(A, B)] = sorted(kernels7(A, B)[0])
    return KCACHE[(A, B)]

def start_instance():
    s = (-1 * inv(3)) % p
    A, B = short_from_general(1, 2, 0)
    tox = lambda P: ((P[0] - s) % p, P[1])
    return A, B, tox((26, 58)), tox((61, 82))

def make_candidate(rng):
    A, B, G, Q = start_instance()
    L = rng.randrange(0, 7)
    path = [jinv(A, B)]; prev = None; pairs = 0; ks = []
    for _ in range(L):
        k = rng.randrange(2); h = kernels(A, B)[k]
        G, Q = isogeny_eval(A, B, h, G), isogeny_eval(A, B, h, Q)
        A, B = velu(A, B, h)
        path.append(jinv(A, B)); ks.append(k)
    pairs = sum(1 for i in range(2, len(path)) if path[i] == path[i - 2])
    u = rng.randrange(1, p)
    A, B = A * pow(u, 4, p) % p, B * pow(u, 6, p) % p
    sc = lambda P: (P[0] * u * u % p, P[1] * pow(u, 3, p) % p)
    return dict(A=A, B=B, G=sc(G), Q=sc(Q), steps=L, kernels=ks, path=path,
                inverse_pairs=pairs, u=u)

# ---------------- solvers ----------------
XB = 20  # factor base: subgroup points with x < XB, one per +/- pair

def rref_solve_x(rows, ncols, C):
    M = [r[:] for r in rows]; piv = []; r0 = 0
    for c in range(ncols):
        pr = next((i for i in range(r0, len(M)) if M[i][c] % n), None)
        if pr is None: continue
        M[r0], M[pr] = M[pr], M[r0]
        iv = pow(M[r0][c], -1, n)
        M[r0] = [v * iv % n for v in M[r0]]; C.la += ncols + 1
        for i in range(len(M)):
            if i != r0 and M[i][c] % n:
                f = M[i][c]; M[i] = [(a - f * b) % n for a, b in zip(M[i], M[r0])]
                C.la += ncols + 1
        piv.append(c); r0 += 1
    xc = ncols - 1
    if xc in piv: return M[piv.index(xc)][-1]
    return None

def factor_base(cand, seed):
    C = Ctr(); A = cand["A"]; add, neg, smul = mk(A, C); G, Q = cand["G"], cand["Q"]
    rng = random.Random(seed)
    fb = []
    for x in range(XB):
        r = (x ** 3 + A * x + cand["B"]) % p
        ys = [y for y in range(p // 2 + 1) if y * y % p == r]
        for y in ys[:1]:
            P = (x, y)
            if P[1] != 0 and add(smul(n - 1, P), P) is None: fb.append(P)  # P in <G>
    fbn = len(fb); table = {}
    def put(pt, vec):
        if pt is None: return
        table.setdefault(pt, vec); table.setdefault(neg(pt), tuple(-v for v in vec))
    for i, P in enumerate(fb):
        e = [0] * fbn; e[i] = 1; put(P, tuple(e))
        for k in range(i, fbn):
            for sgn in (1, -1):
                v = [0] * fbn; v[i] += 1; v[k] += sgn
                put(add(P, fb[k] if sgn == 1 else neg(fb[k])), tuple(v))
    a, b = rng.randrange(n), rng.randrange(n)
    R = add(smul(a, G), smul(b, Q)); rels = []
    need = fbn + 3
    while True:
        while len(rels) < need:
            if rng.random() < 0.5: R = add(R, G); a = (a + 1) % n
            else: R = add(R, Q); b = (b + 1) % n
            C.lookup += 1
            if R is None: rels.append([0] * fbn + [b, (-a) % n])
            elif R in table: rels.append([v % n for v in table[R]] + [(-b) % n, a])
        x = rref_solve_x(rels, fbn + 1, C)
        if x is not None and smul(x, G) == Q: return x, C
        need += 3

def bsgs(cand, seed):
    C = Ctr(); add, neg, smul = mk(cand["A"], C); G, Q = cand["G"], cand["Q"]
    rng = random.Random(seed); r = rng.randrange(n)
    T = add(Q, smul(r, G)); m = 7; baby = {}; P = None
    for j in range(m):
        baby.setdefault(P, j); P = add(P, G)
    step = neg(P)  # P = mG
    for i in range(m):
        C.lookup += 1
        if T in baby: return (i * m + baby[T] - r) % n, C
        T = add(T, step)
    raise RuntimeError

def rho(cand, seed, r=8):
    C = Ctr(); add, neg, smul = mk(cand["A"], C); G, Q = cand["G"], cand["Q"]
    rng = random.Random(seed)
    while True:
        M = [(rng.randrange(n), rng.randrange(n)) for _ in range(r)]
        Mp = [add(smul(c, G), smul(d, Q)) for c, d in M]
        def f(S):
            R, a, b = S; k = 0 if R is None else R[0] % r
            return add(R, Mp[k]), (a + M[k][0]) % n, (b + M[k][1]) % n
        a0, b0 = rng.randrange(n), rng.randrange(n)
        S = (add(smul(a0, G), smul(b0, Q)), a0, b0); T = f(S)
        while True:
            C.lookup += 1
            if S[0] == T[0]: break
            S = f(S); T = f(f(T))
        db = (T[2] - S[2]) % n
        if db:
            x = (S[1] - T[1]) * pow(db, -1, n) % n
            if smul(x, G) == Q: return x, C

SOLVERS = {"factor_base": factor_base, "bsgs": bsgs, "rho": rho}

def main(pool=2000, seeds=12, cand_seed=20261016, out="results.json"):
    rng = random.Random(cand_seed)
    A, B, G, Q = start_instance()
    cands = [make_candidate(rng) for _ in range(pool)]
    for c in cands:   # exact checks on every transported instance
        add, neg, smul = mk(c["A"], Ctr())
        assert npts(c["A"], c["B"]) == 82
        assert (c["G"][1] ** 2 - c["G"][0] ** 3 - c["A"] * c["G"][0] - c["B"]) % p == 0
        assert smul(17, c["G"]) == c["Q"] and c["G"] is not None and add(smul(40, c["G"]), c["G"]) is None
    res = []
    for ci, c in enumerate(cands):
        row = dict(idx=ci, A=c["A"], B=c["B"], j=c["path"][-1], path=c["path"],
                   steps=c["steps"], inverse_pairs=c["inverse_pairs"], u=c["u"])
        for name, fn in SOLVERS.items():
            runs = []
            for s in range(seeds):
                x, C = fn(c, 1000 + s); assert x == 17
                runs.append(dict(group=C.group, lookup=C.lookup, la=C.la))
            row[name] = runs
        res.append(row)
    json.dump(dict(pool=pool, seeds=seeds, cand_seed=cand_seed, XB=XB, rows=res), open(out, "w"))

if __name__ == "__main__":
    main()
