"""Signed-Frobenius Pollard rho on E0: y^2 + xy = x^3 + 1 over F_2^19.

The walk runs on classes of <tau, -1>, where tau(x, y) = (x^2, y^2) acts on the
order-r subgroup as multiplication by lambda (lambda^2 + lambda + 2 = 0 mod r).
Each class has 2n = 38 points, so a random walk on the r/38 classes collides
after about sqrt(pi r / (4 n)) steps: the floor S = sqrt(pi / (4 n)).

Frozen design (protocol.json, "rho"):

- Canonical form of W: among the 19 conjugates x^(2^e), take the one with the
  smallest integer encoding (bit i = coefficient of z^i); among the two points
  with that x, take the one whose y has the smaller encoding. The coefficient
  pair (a, b) of W = aP + bQ is multiplied by the same unit eps * lambda^e.
- R-adding walk (Teske), R = 16. Multipliers M_i = A_i + eps_i tau^(e_i)(Q)
  where A_i = alpha_i P is target-independent (one table per walk seed,
  reusable across targets, built outside the online interval). Building M_i
  from A_i costs one target-dependent addition each; tau costs only squarings.
- Index idx(W) = top log2(R) bits of (key(W) * 0x9E3779B97F4A7C15 mod 2^64).
- 2-cycle reduction (Bernstein-Lange-Schwabe look-ahead): if idx(W + M_j) == j,
  use M_(j+1) instead, iterated, at most R tries. Every tried addition is
  counted as a group operation.
- Collision detection: every visited class is stored (distinguished points with
  probability 1; the expected walk is ~74 steps, so the table is tiny and there
  is no distinguished-point tail). A repeat with a different b solves the DLP.
- Fruitless cycles: a repeat with identical (a, b) is a fruitless cycle. Escape
  deterministically to canon(2 * min(cycle)) (minimum by key), one doubling.
  After MAX_ESCAPES escapes in one solve, restart from a fresh start point.
- Verification: the recovered s is checked as s * P == Q by the backend's own
  scalar multiplication (not the walk), and against the planted scalar by the
  caller.

The walk logic is backend-agnostic: PyBackend (pure Python, used for local
validation without Sage) and SageBackend (Sage points over the same
GF(2^19, modulus) as ic.sage/tau.sage, used for measured runs so that CPU time
is comparable with the IC arms).
"""

import random
import time

N_BITS = 19
# z^19 + z^18 + z^16 + z^11 + z^8 + z^6 + z^4 + z + 1 (run.sage MODULUS, PARI default).
MODULUS_INT = (1 << 19) | (1 << 18) | (1 << 16) | (1 << 11) | (1 << 8) | (1 << 6) | (1 << 4) | (1 << 1) | 1
R_ORDER = 130873
COFACTOR = 4
HASH_MUL = 0x9E3779B97F4A7C15
MASK64 = (1 << 64) - 1
MAX_ESCAPES = 64


def nominal_mul_ops(k):
    """Group operations of left-to-right double-and-add for k >= 1."""
    k = int(k)
    if k <= 0:
        return 0
    return (k.bit_length() - 1) + (bin(k).count('1') - 1)


# ---------------------------------------------------------------------------
# Pure-Python backend
# ---------------------------------------------------------------------------

def gf_mul(a, b, n=N_BITS, mod=MODULUS_INT):
    r = 0
    while b:
        if b & 1:
            r ^= a
        b >>= 1
        a <<= 1
        if a >> n:
            a ^= mod
    return r


def gf_sq(a):
    return gf_mul(a, a)


def gf_inv(a, n=N_BITS):
    # a^(2^n - 2)
    if a == 0:
        raise ZeroDivisionError
    r, base, e = 1, a, (1 << n) - 2
    while e:
        if e & 1:
            r = gf_mul(r, base)
        base = gf_mul(base, base)
        e >>= 1
    return r


def gf_trace(a, n=N_BITS):
    t, s = a, a
    for _ in range(n - 1):
        t = gf_sq(t)
        s ^= t
    return s


def gf_half_trace(c, n=N_BITS):
    t, s = c, c
    for _ in range((n - 1) // 2):
        t = gf_sq(gf_sq(t))
        s ^= t
    return s


class PyBackend:
    """Affine points (x, y) as int pairs; None is the identity. a = 0, b = 1."""

    name = 'python'

    def __init__(self):
        self.b = 1

    def on_curve(self, P):
        if P is None:
            return True
        x, y = P
        return gf_sq(y) ^ gf_mul(x, y) == gf_mul(gf_sq(x), x) ^ self.b

    def lift_x_all(self, x):
        """Both points with this x (y = x w, w^2 + w = x + b / x^2), or []."""
        if x == 0:
            return []
        c = x ^ gf_mul(self.b, gf_inv(gf_sq(x)))
        if gf_trace(c) != 0:
            return []
        w = gf_half_trace(c)
        return [(x, gf_mul(x, w)), (x, gf_mul(x, w ^ 1))]

    def is_zero(self, P):
        return P is None

    def neg(self, P):
        return None if P is None else (P[0], P[0] ^ P[1])

    def add(self, P, Q):
        if P is None:
            return Q
        if Q is None:
            return P
        x1, y1 = P
        x2, y2 = Q
        if x1 == x2:
            if y1 == y2:
                return self.dbl(P)
            return None
        lam = gf_mul(y1 ^ y2, gf_inv(x1 ^ x2))
        x3 = gf_sq(lam) ^ lam ^ x1 ^ x2
        y3 = gf_mul(lam, x1 ^ x3) ^ x3 ^ y1
        return (x3, y3)

    def dbl(self, P):
        if P is None:
            return None
        x1, y1 = P
        if x1 == 0:
            return None
        lam = x1 ^ gf_mul(y1, gf_inv(x1))
        x3 = gf_sq(lam) ^ lam
        y3 = gf_sq(x1) ^ gf_mul(lam ^ 1, x3)
        return (x3, y3)

    def mul(self, k, P):
        k = int(k)
        if k < 0:
            return self.mul(-k, self.neg(P))
        Rr = None
        for bit in bin(k)[2:] if k else '':
            Rr = self.dbl(Rr)
            if bit == '1':
                Rr = self.add(Rr, P)
        return Rr

    def eq(self, P, Q):
        return P == Q

    def frob(self, P, e):
        if P is None:
            return None
        x, y = P
        for _ in range(e):
            x, y = gf_sq(x), gf_sq(y)
        return (x, y)

    def canon(self, P):
        """(canonical point, e, eps, key, squarings)."""
        x, y = P
        best, be, cx = x, 0, x
        for e in range(1, N_BITS):
            cx = gf_sq(cx)
            if cx < best:
                best, be = cx, e
        cy = y
        for _ in range(be):
            cy = gf_sq(cy)
        ny = best ^ cy
        eps = 1
        if ny < cy:
            cy, eps = ny, -1
        return (best, cy), be, eps, (best << N_BITS) | cy, (N_BITS - 1) + be


# ---------------------------------------------------------------------------
# Sage backend (imported lazily; only used inside Sage)
# ---------------------------------------------------------------------------

class SageBackend:
    """Sage points on the given E0 (the Curve.E object of ic.sage)."""

    name = 'sage'

    def __init__(self, E):
        self.E = E
        F = E.base_field()
        self.F = F
        self.O = E(0)
        x = F.gen()
        try:
            x.to_integer()
            self.enc = lambda e: int(e.to_integer())
        except AttributeError:   # older Sage
            from sage.all import ZZ
            self.enc = lambda e: int(ZZ(e.polynomial().change_ring(ZZ)(2)))
        try:
            E.point([F(0), F(1), F(1)], check=False)
            self.mk = lambda x, y: E.point([x, y, F(1)], check=False)
        except TypeError:
            self.mk = lambda x, y: E(x, y)

    def is_zero(self, P):
        return P.is_zero()

    def neg(self, P):
        return -P

    def add(self, P, Q):
        return P + Q

    def dbl(self, P):
        return P + P

    def mul(self, k, P):
        return int(k) * P

    def eq(self, P, Q):
        return P == Q

    def frob(self, P, e):
        if P.is_zero():
            return P
        x, y = P[0], P[1]
        for _ in range(e):
            x, y = x * x, y * y
        return self.mk(x, y)

    def canon(self, P):
        x, y = P[0], P[1]
        enc = self.enc
        best, be, bx, cx = enc(x), 0, x, x
        for e in range(1, N_BITS):
            cx = cx * cx
            v = enc(cx)
            if v < best:
                best, be, bx = v, e, cx
        cy = y
        for _ in range(be):
            cy = cy * cy
        ny = bx + cy
        vy, vny = enc(cy), enc(ny)
        eps = 1
        if vny < vy:
            cy, vy, eps = ny, vny, -1
        return self.mk(bx, cy), be, eps, (best << N_BITS) | vy, (N_BITS - 1) + be


# ---------------------------------------------------------------------------
# Walk
# ---------------------------------------------------------------------------

def frob_eigen(B, P, r=R_ORDER):
    """lambda with tau(P) = lambda P, a root of t^2 + t + 2 mod r."""
    roots = [t for t in range(r) if (t * t + t + 2) % r == 0] if r < 10 ** 6 else None
    TP = B.frob(P, 1)
    for lam in roots:
        if B.eq(B.mul(lam, P), TP):
            return lam
    raise ValueError('no Frobenius eigenvalue')


class WalkTable:
    """Target-independent part of one walk seed: alpha_i, A_i = alpha_i P,
    the Q-side shape (eps_i, e_i) and restart start points."""

    def __init__(self, B, P, seed, R=16, n_starts=8, r=R_ORDER):
        rng = random.Random(seed)
        self.R, self.seed = R, seed
        self.alpha = [rng.randrange(1, r) for _ in range(R)]
        self.qe = [rng.randrange(N_BITS) for _ in range(R)]
        self.qeps = [rng.choice((1, -1)) for _ in range(R)]
        self.start_alpha = [rng.randrange(1, r) for _ in range(n_starts)]
        self.start_e = [rng.randrange(N_BITS) for _ in range(n_starts)]
        t0 = time.process_time()
        self.A = [B.mul(a, P) for a in self.alpha]
        self.S = [B.mul(a, P) for a in self.start_alpha]
        self.setup_cpu_s = time.process_time() - t0
        self.setup_nominal_ops = sum(nominal_mul_ops(a) for a in self.alpha + self.start_alpha)
        self.shift = 64 - (R.bit_length() - 1)
        assert 1 << (R.bit_length() - 1) == R


def solve(B, P, Q, lam, table, r=R_ORDER, max_steps=None, verify=True, lookahead=True):
    """One complete single-target signed-Frobenius rho solve of Q = sP.

    Returns a dict with the recovered log, verification, operation counts and
    CPU/wall time of the online interval (first target-dependent operation to
    recovered and verified scalar). lookahead=False is for stress tests only
    (it raises the fruitless 2-cycle rate so the escape path is exercised)."""
    R, shift = table.R, table.shift
    if max_steps is None:
        max_steps = 64 * int(r ** 0.5) + 1000
    lp = [pow(lam, e, r) for e in range(N_BITS)]
    st = {'steps': 0, 'adds': 0, 'dbls': 0, 'lookahead_extra': 0, 'fruitless': 0,
          'restarts': 0, 'squarings': 0, 'table_entries': 0}
    c0 = time.process_time()
    w0 = time.perf_counter()

    def idx(key):
        return ((key * HASH_MUL) & MASK64) >> shift

    # Target-dependent multipliers M_i = A_i + eps_i tau^e_i(Q): one add each.
    M, mb = [], []
    for i in range(R):
        TQ = B.frob(Q, table.qe[i])
        st['squarings'] += 2 * table.qe[i]
        if table.qeps[i] < 0:
            TQ = B.neg(TQ)
        M.append(B.add(table.A[i], TQ))
        st['adds'] += 1
        mb.append(table.qeps[i] * lp[table.qe[i]] % r)
    ma = table.alpha

    def canon(W, a, b):
        Wc, e, eps, key, sq = B.canon(W)
        st['squarings'] += sq
        u = eps * lp[e] % r
        return Wc, key, a * u % r, b * u % r

    def start(k):
        # W = A_start_k + tau^e(Q); k = 0 is Q itself (no group operation).
        if k == 0:
            return Q, 0, 1
        j = (k - 1) % len(table.S)
        TQ = B.frob(Q, table.start_e[j])
        st['squarings'] += 2 * table.start_e[j]
        st['adds'] += 1
        return B.add(table.S[j], TQ), table.start_alpha[j], lp[table.start_e[j]]

    seen = {}          # key -> (a, b, path index)
    path_pts = []      # path index -> (point, key, a, b)
    W, a, b = start(0)
    W, key, a, b = canon(W, a, b)
    seen[key] = (a, b, 0)
    path_pts.append((W, key, a, b))
    escapes = 0
    s = None
    status = 'max_steps'
    while st['steps'] < max_steps:
        i = idx(key)
        j = i
        for t in range(R):
            W1 = B.add(W, M[j])
            st['adds'] += 1
            if t:
                st['lookahead_extra'] += 1
            if B.is_zero(W1):
                break
            W1c, key1, a1, b1 = canon(W1, (a + ma[j]) % r, (b + mb[j]) % r)
            if not lookahead or idx(key1) != j:
                break
            j = (j + 1) % R
        st['steps'] += 1
        if B.is_zero(W1):
            # W = -M_j: the class walk hit the identity; restart (keeps the table).
            st['restarts'] += 1
            escapes = 0
            W1, a1, b1 = start(st['restarts'])
            W1c, key1, a1, b1 = canon(W1, a1, b1)
        while True:
            hit = seen.get(key1)
            if hit is None:
                break
            a0, b0, t0 = hit
            if b0 != b1:
                s = (a1 - a0) * pow(b0 - b1, -1, r) % r
                status = 'collision'
                break
            assert a0 == a1, 'same point, same b, different a'
            # Fruitless cycle: path[t0:] closes on itself with identical coefficients.
            st['fruitless'] += 1
            escapes += 1
            if escapes > MAX_ESCAPES:
                st['restarts'] += 1
                escapes = 0
                W1, a1, b1 = start(st['restarts'])
                W1c, key1, a1, b1 = canon(W1, a1, b1)
                continue
            cyc = path_pts[t0:]
            Wm, km, am, bm = min(cyc, key=lambda z: z[1])
            W2 = B.dbl(Wm)
            st['dbls'] += 1
            W1c, key1, a1, b1 = canon(W2, 2 * am % r, 2 * bm % r)
        if s is not None:
            break
        seen[key1] = (a1, b1, len(path_pts))
        path_pts.append((W1c, key1, a1, b1))
        W, key, a, b = W1c, key1, a1, b1
    c_found = time.process_time()
    ok = None
    if s is not None and verify:
        ok = B.eq(B.mul(s, P), Q)
    c1 = time.process_time()
    w1 = time.perf_counter()
    st['table_entries'] = len(seen)
    st.update({'status': status, 'log': s, 'verified': ok,
               'group_ops': st['adds'] + st['dbls'],
               'cpu_s_to_recovery': c_found - c0, 'cpu_s': c1 - c0, 'wall_s': w1 - w0,
               'verify_nominal_ops': nominal_mul_ops(s) if s is not None else 0})
    return st
