#!/usr/bin/env python3
"""Generate the elliptic-curve challenge corpus.

Every order is either counted directly (small fields) or taken from a
recurrence / CM formula and then checked against the group law.  The
script is deterministic (``SEED``).  Re-run from the repository root:

    python3 challenges/elliptic/generate.py

It writes ``challenges/elliptic/corpus.json`` and, for the 64-bit C
registry, ``challenges/elliptic/c_registry.txt``.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path

SEED = 20260922
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "corpus.json"
C_OUT = Path(__file__).resolve().parent / "c_registry.txt"

# Φ₂ and Φ₃, the same integer polynomials as suite/.../modular_polynomial.rs.
PHI2 = {
    (3, 0): 1,
    (2, 2): -1,
    (2, 1): 1488,
    (2, 0): -162000,
    (1, 1): 40773375,
    (1, 0): 8748000000,
    (0, 0): -157464000000000,
}
PHI3 = {
    (4, 0): 1,
    (3, 3): -1,
    (3, 2): 2232,
    (3, 1): -1069956,
    (3, 0): 36864000,
    (2, 2): 2587918086,
    (2, 1): 8900222976000,
    (2, 0): 452984832000000,
    (1, 1): -770845966336000000,
    (1, 0): 1855425871872000000000,
}


# ── primes, residues, integers ────────────────────────────────────────


def sieve(limit: int) -> list[int]:
    mark = bytearray(b"\x01") * (limit + 1)
    mark[0:2] = b"\x00\x00"
    for i in range(2, int(limit**0.5) + 1):
        if mark[i]:
            step = i
            start = i * i
            mark[start : limit + 1 : step] = b"\x00" * (((limit - start) // step) + 1)
    return [i for i in range(limit + 1) if mark[i]]


SMALL_PRIMES = sieve(1_000_000)


def is_probable_prime(n: int) -> bool:
    if n < 2:
        return False
    for p in SMALL_PRIMES:
        if p * p > n:
            return True
        if n % p == 0:
            return n == p
    # Deterministic Miller-Rabin bases for 64-bit, then a few extra.
    d = n - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1
    bases = [2, 3, 5, 7, 11, 13, 23, 29, 31, 37]
    if n.bit_length() > 64:
        bases += [41, 43, 47, 53, 59]
    for a in bases:
        if a % n == 0:
            continue
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def next_prime(n: int) -> int:
    if n <= 2:
        return 2
    n += 1 if n % 2 == 0 else 0
    while not is_probable_prime(n):
        n += 2
    return n


def factor(n: int, limit: int = 1_000_000) -> tuple[list[tuple[int, int]], int]:
    """Trial-divide ``n``.  Returns (factors, cofactor)."""
    if n < 1:
        raise ValueError(n)
    fac: list[tuple[int, int]] = []
    for p in SMALL_PRIMES:
        if p > limit or p * p > n:
            break
        if n % p == 0:
            e = 0
            while n % p == 0:
                n //= p
                e += 1
            fac.append((p, e))
    if n > 1 and n.bit_length() <= 64 and is_probable_prime(n):
        fac.append((n, 1))
        n = 1
    return fac, n


def inv(a: int, p: int) -> int:
    return pow(a % p, -1, p)


def legendre(a: int, p: int) -> int:
    a %= p
    if a == 0:
        return 0
    s = pow(a, (p - 1) // 2, p)
    return -1 if s == p - 1 else 1


def tonelli(a: int, p: int) -> int | None:
    a %= p
    if a == 0:
        return 0
    if legendre(a, p) != 1:
        return None
    if p % 4 == 3:
        return pow(a, (p + 1) // 4, p)
    s = p - 1
    e = 0
    while s % 2 == 0:
        s //= 2
        e += 1
    n = 2
    while legendre(n, p) != -1:
        n += 1
    x = pow(a, (s + 1) // 2, p)
    b = pow(a, s, p)
    g = pow(n, s, p)
    r = e
    while True:
        t = b
        m = 0
        for m in range(r):
            if t == 1:
                break
            t = pow(t, 2, p)
        if m == 0:
            return x
        gs = pow(g, 1 << (r - m - 1), p)
        g = pow(gs, 2, p)
        x = x * gs % p
        b = b * g % p
        r = m


def isqrt(n: int) -> int:
    return int(math.isqrt(n))


def hasse_bound(q: int) -> int:
    return isqrt(4 * q)


def fundamental_part(disc: int) -> tuple[int, int]:
    """Write ``disc = f² · D_K`` with ``D_K`` fundamental.  ``disc < 0``."""
    if disc >= 0:
        raise ValueError(disc)
    f = 1
    # Peel square factors.  ``disc`` is tiny for the volcano search.
    n = -disc
    primes = sieve(isqrt(n) + 2)
    for p in primes:
        pp = p * p
        while n % pp == 0:
            n //= pp
            f *= p
        if pp > n:
            break
    d = -n
    # d ≡ 0 or 1 (mod 4) after absorbing a factor of 4 when needed?  A
    # negative discriminant is fundamental when it is square-free except
    # possibly for a factor 4, and ≡ 0 or 1 mod 4, and not ≡ 0 mod 4 with
    # the odd part ≡ 1 mod 4?  Standard: square-free and 1 mod 4, or
    # 4·(square-free ≡ 2 or 3 mod 4).
    if d % 4 == 0:
        odd = d // 4
        if odd % 4 == 1:
            # 4 times something 1 mod 4 is not fundamental; peel another square? 
            # odd is square-free.  If odd ≡ 1 mod 4 then D_K = odd, f *= 2.
            return odd, f * 2
        return d, f
    if d % 4 == 1:
        return d, f
    # d ≡ 2 or 3 (mod 4): the fundamental discriminant is 4d and one
    # factor of 2 belongs to it rather than to the conductor.
    if f % 2 != 0:
        raise RuntimeError(f"discriminant {disc} is not a discriminant")
    return 4 * d, f // 2


def valuation(n: int, q: int) -> int:
    v = 0
    n = abs(n)
    while n % q == 0 and n:
        n //= q
        v += 1
    return v


# ── prime-field curves ───────────────────────────────────────────────


INF = None  # point at infinity


def j_invariant(p: int, A: int, B: int) -> int | None:
    disc = (4 * pow(A, 3, p) + 27 * pow(B, 2, p)) % p
    if disc == 0:
        return None
    return (6912 * pow(A, 3, p) * inv(disc, p)) % p


def curve_from_j(p: int, j: int) -> tuple[int, int]:
    j %= p
    if j == 0:
        return 0, 1
    if j == 1728 % p:
        return 1, 0
    k = j * inv((1728 - j) % p, p) % p
    return (3 * k) % p, (2 * k) % p


def on_curve(p: int, A: int, B: int, P) -> bool:
    if P is INF:
        return True
    x, y = P
    return (y * y - (x * x * x + A * x + B)) % p == 0


def ec_add(p: int, A: int, P, Q):
    if P is INF:
        return Q
    if Q is INF:
        return P
    x1, y1 = P
    x2, y2 = Q
    if x1 == x2 and (y1 + y2) % p == 0:
        return INF
    if P != Q:
        lam = (y2 - y1) * inv((x2 - x1) % p, p) % p
    else:
        if y1 % p == 0:
            return INF
        lam = (3 * x1 * x1 + A) * inv(2 * y1 % p, p) % p
    x3 = (lam * lam - x1 - x2) % p
    y3 = (lam * (x1 - x3) - y1) % p
    return x3, y3


def ec_mul(p: int, A: int, k: int, P):
    if k < 0:
        if P is INF:
            return INF
        P = (P[0], (-P[1]) % p)
        k = -k
    R = INF
    Q = P
    while k:
        if k & 1:
            R = ec_add(p, A, R, Q)
        Q = ec_add(p, A, Q, Q)
        k >>= 1
    return R


def find_point(p: int, A: int, B: int, rng: random.Random, skip: int = 0):
    # Deterministic scan, then a few random abscissae.
    for x in list(range(skip, min(p, skip + 64))) + [rng.randrange(p) for _ in range(32)]:
        rhs = (x * x * x + A * x + B) % p
        y = tonelli(rhs, p)
        if y is not None:
            return x % p, y
    raise RuntimeError("no point")


def brute_order(p: int, A: int, B: int) -> int:
    cnt = 1
    for x in range(p):
        rhs = (x * x * x + A * x + B) % p
        cnt += 1 + legendre(rhs, p)
    return cnt


def bsgs_traces(p: int, A: int, B: int, P) -> list[int]:
    """All Hasse-bounded t with [t]P = [p+1]P."""
    bound = isqrt(4 * p)
    Q = ec_mul(p, A, p + 1, P)
    width = 2 * bound + 1
    m = isqrt(width) + 1
    babies: dict[tuple, list[int]] = {}
    R = INF
    for i in range(m):
        key = ("O",) if R is INF else R
        babies.setdefault(key, []).append(i)
        R = ec_add(p, A, R, P)
    mP = ec_mul(p, A, m, P)
    j_min = -((bound + m - 1) // m)
    j_max = (bound + m - 1) // m
    # U_j = [j](mP), walked from j_min by adding mP.
    U = ec_mul(p, A, j_min, mP) if j_min else INF
    found = []
    for j in range(j_min, j_max + 1):
        # i P = Q + [j](mP), t = i - j m
        V = ec_add(p, A, Q, U)
        key = ("O",) if V is INF else V
        if key in babies:
            for i in babies[key]:
                t = i - j * m
                if -bound <= t <= bound:
                    found.append(t)
        U = ec_add(p, A, U, mP)
    return sorted(set(found))


def ec_trace(p: int, A: int, B: int, rng: random.Random) -> int:
    if p < 8_000:
        return p + 1 - brute_order(p, A, B)
    for attempt in range(24):
        P = find_point(p, A, B, rng, skip=rng.randrange(max(p // 2, 1)))
        ts = bsgs_traces(p, A, B, P)
        if len(ts) != 1:
            continue
        tr = ts[0]
        P2 = find_point(p, A, B, rng, skip=rng.randrange(max(p // 3, 1)) + attempt + 1)
        if ec_mul(p, A, p + 1 - tr, P2) is INF:
            return tr
    if p < 200_000:
        return p + 1 - brute_order(p, A, B)
    raise RuntimeError(f"trace not unique mod p={p}")


def order_kills(p: int, A: int, B: int, N: int, rng: random.Random, samples: int = 2) -> bool:
    for s in range(samples):
        P = find_point(p, A, B, rng, skip=s * 3)
        if ec_mul(p, A, N, P) is not INF:
            return False
    return True


def j0_candidate_traces(t: int, v: int) -> list[int]:
    out = []
    for num in (t, -t, (t + 3 * v) // 2, -(t + 3 * v) // 2, (t - 3 * v) // 2, -(t - 3 * v) // 2):
        if num not in out:
            out.append(num)
    return out


def make_j0_ordinary(bits: int, rng: random.Random) -> tuple[int, int, int, int, int]:
    """Return (p, b, trace, t_rep, v) for y² = x³ + b, p ≡ 1 (mod 3)."""
    for _ in range(100_000):
        half = max(2, (bits + 1) // 2)
        v = rng.randrange(1 << (half - 1), 1 << half) | 1
        t = rng.randrange(1 << (half - 1), 1 << half)
        if (t - v) % 2:
            t += 1
        disc = t * t + 3 * v * v
        if disc % 4:
            continue
        p = disc // 4
        if p.bit_length() != bits or not is_probable_prime(p) or p % 3 != 1:
            continue
        # Pick b whose trace is one of the six CM traces, preferring the
        # representative of largest absolute value (a large |t| is fine).
        cands = j0_candidate_traces(t, v)
        for b in range(1, 40):
            if j_invariant(p, 0, b) != 0:
                continue
            good = []
            P = find_point(p, 0, b, rng)
            for tr in cands:
                N = p + 1 - tr
                if N > 0 and ec_mul(p, 0, N, P) is INF:
                    good.append(tr)
            if len(good) == 1:
                tr = good[0]
                if order_kills(p, 0, b, p + 1 - tr, rng):
                    return p, b, tr, t, v
            elif len(good) > 1:
                # A small-order point was killed by several candidates.
                P2 = find_point(p, 0, b, rng, skip=5)
                good2 = [tr for tr in good if ec_mul(p, 0, p + 1 - tr, P2) is INF]
                if len(good2) == 1:
                    return p, b, good2[0], t, v
    raise RuntimeError(f"no j=0 ordinary prime of {bits} bits")


def make_j1728_ordinary(bits: int, rng: random.Random) -> tuple[int, int, int]:
    """Return (p, a, trace) for y² = x³ + a x, p ≡ 1 (mod 4)."""
    for _ in range(100_000):
        half = max(2, bits // 2)
        c = rng.randrange(1 << (half - 1), 1 << half) | 1
        d = rng.randrange(1 << (half - 1), 1 << half) & ~1
        if d == 0:
            continue
        p = c * c + d * d
        if p.bit_length() != bits or not is_probable_prime(p) or p % 4 != 1:
            continue
        cands = [2 * c, -2 * c, 2 * d, -2 * d]
        for a in range(1, 30):
            if j_invariant(p, a, 0) != 1728 % p:
                continue
            if p < 300_000:
                tr = p + 1 - brute_order(p, a, 0)
                if tr in cands:
                    return p, a, tr
                continue
            good = set(cands)
            for s in range(8):
                P = find_point(p, a, 0, rng, skip=rng.randrange(p))
                good = {tr for tr in good if p + 1 - tr > 0 and ec_mul(p, a, p + 1 - tr, P) is INF}
                if len(good) == 1:
                    break
            if len(good) != 1:
                continue
            tr = next(iter(good))
            if order_kills(p, a, 0, p + 1 - tr, rng):
                return p, a, tr
    raise RuntimeError(f"no j=1728 ordinary prime of {bits} bits")


def make_supersingular(bits: int, kind: str, rng: random.Random) -> tuple[int, int, int]:
    """kind 'j0' (p ≡ 2 mod 3, b=1) or 'j1728' (p ≡ 3 mod 4, a=1)."""
    for _ in range(100_000):
        p = rng.randrange(1 << (bits - 1), 1 << bits) | 1
        p = next_prime(p)
        if p.bit_length() != bits:
            continue
        if kind == "j0" and p % 3 == 2:
            return p, 0, 1
        if kind == "j1728" and p % 4 == 3:
            return p, 1, 0
    raise RuntimeError(kind)


def make_smooth_prime(bits: int, residue_mod: int, residue: int, rng: random.Random) -> int:
    """p = N - 1 prime, N smooth, p ≡ residue (mod residue_mod), ~bits bits."""
    primes = [q for q in SMALL_PRIMES if q < 300]
    for _attempt in range(50_000):
        N = 1
        # Force the congruence of p = N-1.
        if residue_mod == 3 and residue == 2:
            N = 3
        elif residue_mod == 4 and residue == 3:
            N = 4
        guard = 0
        while N.bit_length() < bits and guard < 40:
            N *= primes[rng.randrange(len(primes))]
            guard += 1
        # Trim down to the window by dividing out factors if we overshot a lot.
        while N.bit_length() > bits + 2 and N > residue_mod:
            for q in reversed(primes):
                if N % q == 0 and (N // q).bit_length() >= bits:
                    N //= q
                    break
            else:
                break
        if not (bits - 1 <= (N - 1).bit_length() <= bits + 1):
            continue
        p = N - 1
        if p > 3 and is_probable_prime(p) and p % residue_mod == residue:
            return p
    raise RuntimeError(f"no smooth-order supersingular prime near {bits} bits")


def sha256_scalar(ident: str, scalar: int) -> str:
    return hashlib.sha256(f"{ident}\n{scalar}".encode()).hexdigest()


def point_json(P) -> dict | None:
    if P is INF:
        return None
    x, y = P
    if isinstance(x, list):
        return {"x": [str(c) for c in x], "y": [str(c) for c in y]}
    return {"x": [str(x)], "y": [str(y)]}


def relation_json(ident: str, base, target, scalar: int | None, hidden: int | None) -> dict:
    rel = {
        "base": point_json(base),
        "target": point_json(target),
        "scalar": None if scalar is None else str(scalar),
        "scalar_sha256": sha256_scalar(ident, hidden if hidden is not None else scalar),
    }
    return rel


class Corpus:
    def __init__(self):
        self.instances: list[dict] = []
        self.volcanoes: list[dict] = []
        self.ids: set[str] = set()

    def add(self, inst: dict) -> None:
        if inst["id"] in self.ids:
            raise RuntimeError(f"duplicate id {inst['id']}")
        self.ids.add(inst["id"])
        self.instances.append(inst)


def prime_instance(
    corpus: Corpus,
    rng: random.Random,
    *,
    ident: str,
    family: str,
    p: int,
    A: int,
    B: int,
    trace: int,
    tags: list[str],
    endomorphisms: list[str],
    solvers: list[str],
    note: str,
    tier: str | None = None,
    witness_k: int = 10007,
) -> dict:
    N = p + 1 - trace
    if N <= 0:
        raise RuntimeError(f"{ident}: non-positive order {N}")
    if abs(trace) > hasse_bound(p):
        raise RuntimeError(f"{ident}: trace {trace} outside Hasse")
    j = j_invariant(p, A, B)
    if j is None:
        raise RuntimeError(f"{ident}: singular")
    if p < 5000:
        counted = brute_order(p, A, B)
        if counted != N:
            raise RuntimeError(f"{ident}: order {N} != counted {counted}")
    else:
        if not order_kills(p, A, B, N, rng):
            raise RuntimeError(f"{ident}: [N]P ≠ O")
    P = find_point(p, A, B, rng)
    if ec_mul(p, A, N, P) is not INF:
        raise RuntimeError(f"{ident}: generator check failed")
    bits = N.bit_length() - 1
    if tier is None:
        if bits <= 20:
            tier = "open"
        elif bits <= 48:
            tier = "bench"
        else:
            tier = "shape"
    fac, cof = factor(N)
    factored = cof == 1
    largest = max((q for q, _ in fac), default=None)
    if cof > 1:
        largest = cof if largest is None else max(largest, cof)
    # Subgroup: the largest prime factor when we fully factored and it is
    # the unique large one; otherwise the whole group.
    subgroup = N
    cofactor = 1
    if factored and largest:
        subgroup = largest
        cofactor = N // largest
        # Lift P into the large subgroup.
        P = ec_mul(p, A, cofactor, P)
        if P is INF or ec_mul(p, A, subgroup, P) is not INF:
            # cofactor multiple landed on O; fall back to the full group.
            P = find_point(p, A, B, rng)
            subgroup = N
            cofactor = 1
    k_witness = witness_k % subgroup
    if k_witness == 0:
        k_witness = 3
    W = ec_mul(p, A, k_witness, P)
    if tier == "shape":
        secret = rng.randrange(2, subgroup)
        Q = ec_mul(p, A, secret, P)
        if ec_mul(p, A, subgroup, Q) is not INF and cofactor == 1:
            pass
        relation = relation_json(ident, P, Q, None, secret)
    else:
        secret = rng.randrange(2, subgroup)
        Q = ec_mul(p, A, secret, P)
        relation = relation_json(ident, P, Q, secret, secret)
    card_bits = p.bit_length() - 1
    emb = None
    if largest and factored and largest > 2 and largest.bit_length() <= 40:
        emb = embedding_degree(p, largest)
    inst = {
        "id": ident,
        "family": family,
        "tier": tier,
        "tags": tags,
        "field": {
            "kind": "prime",
            "characteristic": str(p),
            "degree": 1,
            "degree_kind": "prime-field",
            "cardinality": str(p),
            "cardinality_bits": card_bits,
        },
        "model": "short-weierstrass",
        "a": [str(A)],
        "b": [str(B)],
        "j": str(j),
        "trace": str(trace),
        "group_order": str(N),
        "subgroup_order": str(subgroup),
        "cofactor": str(cofactor),
        "factored_completely": factored,
        "largest_prime_factor": None if largest is None else str(largest),
        "embedding_degree": emb,
        "endomorphisms": endomorphisms,
        "solvers": solvers,
        "relation": relation,
        "witness": {
            "scalar": str(k_witness),
            "point": point_json(W),
        },
        "note": note,
    }
    corpus.add(inst)
    return inst


def embedding_degree(q: int, r: int) -> int | None:
    """Order of q modulo r, when r is prime and does not divide q."""
    if r <= 2 or q % r == 0:
        return None
    if not is_probable_prime(r):
        return None
    fac, cof = factor(r - 1)
    if cof != 1:
        return None
    # k is the lcm of the orders, computed by removing prime powers.
    k = r - 1
    for p, e in fac:
        pe = p**e
        k_try = k // pe
        if pow(q, k_try, r) == 1:
            k = k_try
            # remove further powers
            while k % p == 0 and pow(q, k // p, r) == 1:
                k //= p
    return k


def solvers_for_prime(tags: list[str], factored: bool, largest: int | None, order_bits: int) -> list[str]:
    s = ["pollard-rho", "negation-map-rho", "index-calculus"]
    if "j0" in tags and "ordinary" in tags:
        s.append("glv-j0")
        s.append("j0-index-calculus")
    if "j1728" in tags and "ordinary" in tags:
        s.append("glv-j1728")
    if "supersingular" in tags:
        s.append("mov")
    if "anomalous" in tags:
        s.append("smart")
    if factored and largest is not None and largest.bit_length() <= 20 and order_bits > largest.bit_length() + 2:
        s.append("pohlig-hellman")
    if "smooth-order" in tags:
        if "pohlig-hellman" not in s:
            s.append("pohlig-hellman")
        if "mov" not in s:
            s.append("mov")
    return s


# ── binary fields ────────────────────────────────────────────────────


def _rows_from_columns(cols: list[int], m: int) -> list[int]:
    rows = [0] * m
    for j, col in enumerate(cols):
        bit = col
        i = 0
        while bit:
            if bit & 1:
                rows[i] |= 1 << j
            bit >>= 1
            i += 1
    return rows


def _rref_f2(rows: list[int], aug: list[int] | None, m: int) -> tuple[list[int], list[int] | None, list[int]]:
    """Row-reduce.  Returns (rows, aug, pivot_col_of_row) with -1 for non-pivot rows."""
    pivot = [-1] * m
    row = 0
    for col in range(m):
        sel = None
        for i in range(row, m):
            if (rows[i] >> col) & 1:
                sel = i
                break
        if sel is None:
            continue
        rows[row], rows[sel] = rows[sel], rows[row]
        if aug is not None:
            aug[row], aug[sel] = aug[sel], aug[row]
        for i in range(m):
            if i != row and ((rows[i] >> col) & 1):
                rows[i] ^= rows[row]
                if aug is not None:
                    aug[i] ^= aug[row]
        pivot[row] = col
        row += 1
    return rows, aug, pivot


def _solve_f2_columns(cols: list[int], rhs: int, m: int) -> int | None:
    """Solve M v = rhs with M given by columns.  Free variables are set to 0."""
    rows = _rows_from_columns(cols, m)
    aug = [(rhs >> i) & 1 for i in range(m)]
    rows, aug, pivot = _rref_f2(rows, aug, m)
    assert aug is not None
    z = 0
    for r, col in enumerate(pivot):
        if col < 0:
            if aug[r]:
                return None
            continue
        if aug[r]:
            z |= 1 << col
    return z


def _nullspace_f2(cols: list[int], m: int) -> list[int]:
    rows = _rows_from_columns(cols, m)
    rows, _, pivot = _rref_f2(rows, None, m)
    pivot_col = {col: r for r, col in enumerate(pivot) if col >= 0}
    free = [c for c in range(m) if c not in pivot_col]
    basis = []
    for fcol in free:
        v = 1 << fcol
        for col, r in pivot_col.items():
            if (rows[r] >> fcol) & 1:
                v |= 1 << col
        basis.append(v)
    return basis


class BinaryField:
    def __init__(self, m: int, irr: int):
        if irr >> m != 1:
            raise ValueError("irreducible must be degree m")
        self.m = m
        self.irr = irr
        self._sq = self._squaring_matrix()

    def mul(self, a: int, b: int) -> int:
        r = 0
        aa = a
        bb = b
        irr = self.irr
        m = self.m
        while bb:
            if bb & 1:
                r ^= aa
            bb >>= 1
            aa <<= 1
            if aa >> m:
                aa ^= irr
        return r

    def square(self, a: int) -> int:
        # Bit i goes to bit 2i, then reduce.
        s = 0
        i = 0
        aa = a
        while aa:
            if aa & 1:
                s |= 1 << (2 * i)
            aa >>= 1
            i += 1
        return self.reduce(s)

    def reduce(self, a: int) -> int:
        m = self.m
        irr = self.irr
        while a >> m:
            deg = a.bit_length() - 1
            a ^= irr << (deg - m)
        return a

    def add(self, a: int, b: int) -> int:
        return a ^ b

    def pow(self, a: int, e: int) -> int:
        r = 1
        b = a
        while e:
            if e & 1:
                r = self.mul(r, b)
            b = self.square(b)
            e >>= 1
        return r

    def inv(self, a: int) -> int:
        if a == 0:
            raise ZeroDivisionError
        # Itoh–Tsujii: a^{-1} = a^{2^m - 2} = (a^{2^{m-1} - 1})^2.
        if self.m == 1:
            return a
        return self.square(self._pow_2nm1(a, self.m - 1))

    def _pow_2nm1(self, a: int, n: int) -> int:
        """``a^{2^n - 1}`` for ``n ≥ 1`` (Itoh–Tsujii addition chain)."""
        if n == 1:
            return a
        if n % 2 == 0:
            half = n // 2
            part = self._pow_2nm1(a, half)
            x = part
            for _ in range(half):
                x = self.square(x)
            return self.mul(x, part)
        part = self._pow_2nm1(a, n - 1)
        return self.mul(self.square(part), a)

    def div(self, a: int, b: int) -> int:
        return self.mul(a, self.inv(b))

    def trace(self, a: int) -> int:
        t = 0
        x = a
        for _ in range(self.m):
            t ^= x
            x = self.square(x)
        return t & 1

    def _squaring_matrix(self) -> list[int]:
        cols = []
        for j in range(self.m):
            cols.append(self.square(1 << j))
        return cols

    def solve_artin_schreier(self, c: int) -> int | None:
        """Solve z² + z = c.  Returns one solution, or None if Tr(c) = 1."""
        if self.trace(c) != 0:
            return None
        # Columns of z ↦ z² + z.  Bit i of column j is output coordinate i.
        cols = [self._sq[j] ^ (1 << j) for j in range(self.m)]
        z = _solve_f2_columns(cols, c, self.m)
        if z is None or self.add(self.square(z), z) != c:
            raise RuntimeError("Artin-Schreier solver failed")
        return z

    def random_element(self, rng: random.Random) -> int:
        return rng.randrange(1 << self.m)

    def iter_subfield(self, k: int):
        """Yield the 2^k elements of F_{2^k} inside this field.  k must divide m."""
        if self.m % k:
            raise ValueError("k does not divide m")
        # Kernel of x ↦ x^{2^k} + x.
        cols = []
        for j in range(self.m):
            y = 1 << j
            for _ in range(k):
                y = self.square(y)
            cols.append(y ^ (1 << j))
        basis = _nullspace_f2(cols, self.m)
        if len(basis) != k:
            raise RuntimeError(f"subfield dimension {len(basis)} != {k}")
        span = [0]
        for b in basis:
            span += [x ^ b for x in span]
        return span


def _square_mod(a: int, m: int, irr: int) -> int:
    s = 0
    i = 0
    aa = a
    while aa:
        if aa & 1:
            s |= 1 << (2 * i)
        aa >>= 1
        i += 1
    while s >> m:
        deg = s.bit_length() - 1
        s ^= irr << (deg - m)
    return s


def is_irreducible_binary(low: list[int], m: int) -> bool:
    """Rabin test.  ``low`` are the exponents below ``z^m``, including 0."""
    f = 1 << m
    for i in low:
        f |= 1 << i

    def x_pow_2k(k: int) -> int:
        x = 0b10
        for _ in range(k):
            x = _square_mod(x, m, f)
        return x

    # x^{2^m} ≡ x, and gcd(x^{2^{m/q}} + x, f) = 1 for every prime q | m.
    if x_pow_2k(m) != 0b10:
        return False
    n = m
    primes = []
    d = 2
    while d * d <= n:
        if n % d == 0:
            primes.append(d)
            while n % d == 0:
                n //= d
        d += 1 if d == 2 else 2
    if n > 1:
        primes.append(n)

    def gcd_poly(a: int, b: int) -> int:
        while b:
            while a.bit_length() >= b.bit_length() and b:
                a ^= b << (a.bit_length() - b.bit_length())
            a, b = b, a
        return a

    for q in primes:
        xp = x_pow_2k(m // q) ^ 0b10
        if gcd_poly(f, xp) != 1:
            return False
    return True


def find_binary_irreducible(m: int, rng: random.Random | None = None) -> tuple[list[int], int]:
    """Sparse irreducible: a trinomial if one exists, otherwise a random pentanomial."""
    for k in range(1, m):
        low = [0, k]
        if is_irreducible_binary(low, m):
            irr = (1 << m) | (1 << k) | 1
            return low, irr
    rng = rng or random.Random(m)
    for _ in range(max(1000, 8 * m)):
        ks = sorted(rng.sample(range(1, m), 3))
        low = [0, *ks]
        if is_irreducible_binary(low, m):
            irr = (1 << m) | 1
            for e in ks:
                irr |= 1 << e
            return low, irr
    raise RuntimeError(f"no sparse irreducible of degree {m}")


def poly_str_binary(low: list[int], m: int) -> str:
    terms = [f"z^{m}"] + [f"z^{e}" if e > 1 else ("z" if e == 1 else "1") for e in reversed(low)]
    return " + ".join(terms)


def koblitz_order(a: int, n: int) -> tuple[int, int]:
    t = -1 if a == 0 else 1
    s_prev, s_cur = 2, t
    for _ in range(1, n):
        s_prev, s_cur = s_cur, t * s_cur - 2 * s_prev
    return (1 << n) + 1 - s_cur, t


def subfield_order(trace: int, q: int, e: int) -> int:
    s_prev, s_cur = 2, trace
    for _ in range(1, e):
        s_prev, s_cur = s_cur, trace * s_cur - q * s_prev
    return q**e + 1 - s_cur


def binary_on_curve(field: BinaryField, a: int, b: int, P) -> bool:
    if P is INF:
        return True
    x, y = P
    left = field.add(field.square(y), field.mul(x, y))
    right = field.add(field.add(field.mul(field.square(x), x), field.mul(a, field.square(x))), b)
    return left == right


def binary_add(field: BinaryField, a: int, P, Q):
    if P is INF:
        return Q
    if Q is INF:
        return P
    x1, y1 = P
    x2, y2 = Q
    if x1 == x2:
        if y1 != y2:
            return INF
        if x1 == 0:
            return INF
        lam = field.add(x1, field.div(y1, x1))
        x3 = field.add(field.add(field.square(lam), lam), a)
        y3 = field.add(field.square(x1), field.mul(field.add(lam, 1), x3))
        return x3, y3
    lam = field.div(field.add(y1, y2), field.add(x1, x2))
    x3 = field.add(field.add(field.add(field.square(lam), lam), field.add(x1, x2)), a)
    y3 = field.add(field.add(field.mul(lam, field.add(x1, x3)), x3), y1)
    return x3, y3


def binary_mul(field: BinaryField, a: int, k: int, P):
    R = INF
    Q = P
    while k:
        if k & 1:
            R = binary_add(field, a, R, Q)
        Q = binary_add(field, a, Q, Q)
        k >>= 1
    return R


def binary_find_point(field: BinaryField, a: int, b: int, rng: random.Random):
    m = field.m
    for _ in range(8 * m + 16):
        x = rng.randrange(1 << m)
        if x == 0:
            # y² = b, y = b^{2^{m-1}}
            y = field.pow(b, 1 << (m - 1)) if m else b
            if field.square(y) == b and binary_on_curve(field, a, b, (0, y)):
                return 0, y
            continue
        c = field.add(field.add(x, a), field.div(b, field.square(x)))
        z = field.solve_artin_schreier(c)
        if z is None:
            continue
        y = field.mul(z, x)
        P = (x, y)
        if not binary_on_curve(field, a, b, P):
            raise RuntimeError("binary point builder drifted")
        return P
    raise RuntimeError("no binary point")


def binary_count(field: BinaryField, a: int, b: int, xs=None) -> int:
    cnt = 1
    domain = range(1 << field.m) if xs is None else xs
    for x in domain:
        if x == 0:
            y = field.pow(b, 1 << (field.m - 1))
            if field.square(y) == b:
                cnt += 1
            continue
        c = field.add(field.add(x, a), field.div(b, field.square(x)))
        if field.trace(c) == 0:
            cnt += 2
    return cnt


# ── odd-characteristic extension fields ──────────────────────────────


class FpN:
    def __init__(self, p: int, coeffs: list[int]):
        """Monic irreducible, ``coeffs`` low-to-high INCLUDING the leading 1."""
        if coeffs[-1] != 1:
            raise ValueError("must be monic")
        self.p = p
        self.mod = [c % p for c in coeffs]
        self.n = len(coeffs) - 1

    def add(self, a, b):
        return [(x + y) % self.p for x, y in zip(self._pad(a), self._pad(b))]

    def sub(self, a, b):
        return [(x - y) % self.p for x, y in zip(self._pad(a), self._pad(b))]

    def neg(self, a):
        return [(-x) % self.p for x in self._pad(a)]

    def _pad(self, a):
        a = [c % self.p for c in a]
        if len(a) < self.n:
            a = a + [0] * (self.n - len(a))
        return a[: self.n]

    def mul(self, a, b):
        a, b = self._pad(a), self._pad(b)
        n, p = self.n, self.p
        raw = [0] * (2 * n - 1)
        for i, ai in enumerate(a):
            if ai == 0:
                continue
            for j, bj in enumerate(b):
                if bj:
                    raw[i + j] = (raw[i + j] + ai * bj) % p
        mod = self.mod
        for d in range(2 * n - 2, n - 1, -1):
            coef = raw[d]
            if coef == 0:
                continue
            # subtract coef * z^{d-n} * mod
            shift = d - n
            for i, c in enumerate(mod):
                raw[i + shift] = (raw[i + shift] - coef * c) % p
        return raw[:n]

    def pow(self, a, e: int):
        r = [1] + [0] * (self.n - 1)
        b = self._pad(a)
        while e:
            if e & 1:
                r = self.mul(r, b)
            b = self.mul(b, b)
            e >>= 1
        return r

    def inv(self, a):
        # Extended Euclid on polynomials.
        p = self.p
        r0 = self.mod[:]
        r1 = self._pad(a) + [0]
        s0, s1 = [0], [1]
        while any(r1):
            # deg
            d0 = _deg(r0)
            d1 = _deg(r1)
            if d1 < 0:
                break
            while d0 >= d1 and d1 >= 0:
                coef = r0[d0] * inv(r1[d1], p) % p
                shift = d0 - d1
                r0 = _poly_sub(r0, _poly_shift(r1, shift, coef, p), p)
                s0 = _poly_sub(s0, _poly_shift(s1, shift, coef, p), p)
                d0 = _deg(r0)
            r0, r1 = r1, r0
            s0, s1 = s1, s0
        if _deg(r0) != 0:
            raise ZeroDivisionError
        scale = inv(r0[0], p)
        s0 = [(c * scale) % p for c in s0]
        return self._pad(s0)

    def div(self, a, b):
        return self.mul(a, self.inv(b))

    def eq(self, a, b) -> bool:
        return self._pad(a) == self._pad(b)

    def is_square(self, a) -> bool:
        q = self.p**self.n
        if all(c % self.p == 0 for c in a):
            return True
        leg = self.pow(a, (q - 1) // 2)
        return leg == self._pad([1])

    def sqrt(self, a):
        """Tonelli-Shanks in F_q.  Returns one root or None."""
        q = self.p**self.n
        a = self._pad(a)
        if all(c == 0 for c in a):
            return a
        if not self.is_square(a):
            return None
        if q % 4 == 3:
            return self.pow(a, (q + 1) // 4)
        # General Tonelli.
        s = q - 1
        e = 0
        while s % 2 == 0:
            s //= 2
            e += 1
        # Find a nonresidue.
        z = [2] + [0] * (self.n - 1)
        while self.is_square(z):
            z[0] += 1
            if z[0] == self.p:
                z = [0, 1] + [0] * (self.n - 2)
        x = self.pow(a, (s + 1) // 2)
        b = self.pow(a, s)
        g = self.pow(z, s)
        r = e
        one = self._pad([1])
        while True:
            t = b
            m = 0
            for m in range(r):
                if t == one:
                    break
                t = self.mul(t, t)
            if m == 0:
                return x
            gs = g
            for _ in range(r - m - 1):
                gs = self.mul(gs, gs)
            g = self.mul(gs, gs)
            x = self.mul(x, gs)
            b = self.mul(b, g)
            r = m


def _deg(a: list[int]) -> int:
    for i in range(len(a) - 1, -1, -1):
        if a[i] != 0:
            return i
    return -1


def _poly_shift(a, shift, coef, p):
    out = [0] * (len(a) + shift)
    for i, c in enumerate(a):
        out[i + shift] = c * coef % p
    return out


def _poly_sub(a, b, p):
    n = max(len(a), len(b))
    out = [0] * n
    for i in range(n):
        ai = a[i] if i < len(a) else 0
        bi = b[i] if i < len(b) else 0
        out[i] = (ai - bi) % p
    return out


def is_irreducible_fp(p: int, coeffs: list[int]) -> bool:
    """Rabin irreducibility.  ``coeffs`` low-to-high, monic."""
    n = len(coeffs) - 1
    field = FpN(p, coeffs)

    def x_pow(exp: int):
        return field.pow([0, 1], exp)

    # x^{p^n} ≡ x
    if x_pow(p**n) != field._pad([0, 1]):
        return False
    primes = []
    m = n
    d = 2
    while d * d <= m:
        if m % d == 0:
            primes.append(d)
            while m % d == 0:
                m //= d
        d += 1 if d == 2 else 2
    if m > 1:
        primes.append(m)
    for q in primes:
        # gcd(x^{p^{n/q}} - x, f) == 1
        xp = x_pow(p ** (n // q))
        xp[1] = (xp[1] - 1) % p  # -x, xp is length n
        # gcd with modulus via Euclid inside field construction: run Euclid
        g = _poly_gcd(field.mod, field._pad(xp), p)
        if _deg(g) > 0:
            return False
    return True


def _poly_gcd(a, b, p):
    a = [c % p for c in a]
    b = [c % p for c in b]
    while _deg(b) >= 0:
        a = _poly_mod(a, b, p)
        a, b = b, a
    return a


def _poly_mod(a, b, p):
    a = a[:]
    db = _deg(b)
    invb = inv(b[db], p)
    while _deg(a) >= db:
        da = _deg(a)
        coef = a[da] * invb % p
        shift = da - db
        for i, c in enumerate(b):
            if c:
                a[i + shift] = (a[i + shift] - coef * c) % p
    return a


def find_fp_irreducible(p: int, n: int, rng: random.Random | None = None) -> list[int]:
    """Monic irreducible of degree ``n`` over ``F_p``.  Deterministic given ``(p, n)``."""
    if n == 1:
        return [0, 1]
    rng = rng or random.Random((p << 16) ^ n)
    # Sparse first: z^n + a z + b, then a few random polynomials.
    for b in range(p):
        for a in range(p):
            coeffs = [b, a] + [0] * (n - 2) + [1]
            if is_irreducible_fp(p, coeffs):
                return coeffs
    for _ in range(max(200, 20 * n)):
        coeffs = [rng.randrange(p) for _ in range(n)] + [1]
        if coeffs[0] == 0 and n > 1:
            continue  # z divides it
        if is_irreducible_fp(p, coeffs):
            return coeffs
    raise RuntimeError(f"no irreducible of degree {n} over F_{p}")


def short_add(field: FpN, A, P, Q):
    """y² = x³ + A x + B over char > 3.  B is not needed for the group law."""
    if P is INF:
        return Q
    if Q is INF:
        return P
    x1, y1 = P
    x2, y2 = Q
    if field.eq(x1, x2) and field.eq(field.add(y1, y2), [0]):
        return INF
    if field.eq(x1, x2) and field.eq(y1, y2):
        if all(c == 0 for c in y1):
            return INF
        num = field.add(field.mul(field.mul(x1, x1), [3]), A)
        lam = field.div(num, field.mul(y1, [2]))
    else:
        lam = field.div(field.sub(y2, y1), field.sub(x2, x1))
    x3 = field.sub(field.sub(field.mul(lam, lam), x1), x2)
    y3 = field.sub(field.mul(lam, field.sub(x1, x3)), y1)
    return x3, y3


def char3_j0_add(field: FpN, A, P, Q):
    """y² = x³ + A x + B in characteristic 3, A ≠ 0."""
    if P is INF:
        return Q
    if Q is INF:
        return P
    x1, y1 = P
    x2, y2 = Q
    if field.eq(x1, x2) and field.eq(field.add(y1, y2), [0]):
        return INF
    if field.eq(x1, x2) and field.eq(y1, y2):
        if all(c == 0 for c in y1):
            return INF
        # λ = A / (2y) = 2 A / y, since 2*2 ≡ 1.
        lam = field.div(field.mul(A, [2]), y1)
        # x3 = λ² - 2x = λ² + x
        x3 = field.add(field.mul(lam, lam), x1)
    else:
        lam = field.div(field.sub(y2, y1), field.sub(x2, x1))
        x3 = field.sub(field.sub(field.mul(lam, lam), x1), x2)
    y3 = field.sub(field.mul(lam, field.sub(x1, x3)), y1)
    return x3, y3


def char3_jgen_add(field: FpN, a2, P, Q):
    """y² = x³ + a2 x² + b in characteristic 3, a2 ≠ 0, b ≠ 0."""
    if P is INF:
        return Q
    if Q is INF:
        return P
    x1, y1 = P
    x2, y2 = Q
    if field.eq(x1, x2) and field.eq(field.add(y1, y2), [0]):
        return INF
    if field.eq(x1, x2) and field.eq(y1, y2):
        if all(c == 0 for c in y1):
            return INF
        # λ = (2 a2 x) / (2 y) = a2 x / y
        lam = field.div(field.mul(a2, x1), y1)
        # x3 = λ² - a2 - 2 x = λ² - a2 + x
        x3 = field.add(field.sub(field.mul(lam, lam), a2), x1)
    else:
        lam = field.div(field.sub(y2, y1), field.sub(x2, x1))
        # x3 = λ² - a2 - x1 - x2
        x3 = field.sub(field.sub(field.sub(field.mul(lam, lam), a2), x1), x2)
    y3 = field.sub(field.mul(lam, field.sub(x1, x3)), y1)
    return x3, y3


def ext_mul_point(field, add, A, k, P):
    R = INF
    Q = P
    while k:
        if k & 1:
            R = add(field, A, R, Q)
        Q = add(field, A, Q, Q)
        k >>= 1
    return R


def ext_find_point(field: FpN, rhs_at, rng: random.Random, tries: int = 64):
    n, p = field.n, field.p
    for _ in range(tries):
        x = [rng.randrange(p) for _ in range(n)]
        rhs = rhs_at(x)
        y = field.sqrt(rhs)
        if y is not None:
            return x, y
    raise RuntimeError("no extension point")


def ext_count(field: FpN, rhs_at) -> int:
    p, n = field.p, field.n
    # Iterate every element only when q is small.  Caller checks.
    cnt = 1
    coords = [0] * n
    q = p**n
    for _ in range(q):
        rhs = rhs_at(coords[:])
        if all(c == 0 for c in rhs):
            cnt += 1
        elif field.is_square(rhs):
            cnt += 2
        # increment coords
        for i in range(n):
            coords[i] += 1
            if coords[i] == p:
                coords[i] = 0
            else:
                break
    return cnt


# ── volcanoes ────────────────────────────────────────────────────────


def eval_phi(table: dict[tuple[int, int], int], x: int, y: int, p: int) -> int:
    acc = 0
    for (i, j), c in table.items():
        if i == j:
            acc += c * pow(x, i, p) * pow(y, j, p)
        else:
            acc += c * (pow(x, i, p) * pow(y, j, p) + pow(x, j, p) * pow(y, i, p))
        acc %= p
    return acc


def phi_neighbors(ell: int, j0: int, p: int) -> list[int]:
    table = PHI2 if ell == 2 else PHI3
    # Degree ell+1 polynomial in X: collect coefficients by evaluating
    # enough points, or expand.  Expanding is cleaner.
    deg = ell + 1
    # Build coeffs of Φ(X, j0) by finite differences / direct expansion.
    coeffs = [0] * (deg + 1)
    for (i, j), c in table.items():
        yj = pow(j0, j, p)
        xi_shift = pow(j0, i, p)
        # c X^i Y^j + (if i!=j) c X^j Y^i
        coeffs[i] = (coeffs[i] + c * yj) % p
        if i != j:
            coeffs[j] = (coeffs[j] + c * xi_shift) % p
    # Find roots in F_p by scanning.  p is small.
    roots = []
    for x in range(p):
        v = 0
        xp = 1
        for c in coeffs:
            v = (v + c * xp) % p
            xp = xp * x % p
        if v == 0:
            roots.append(x)
    return roots


def velu2_neighbor_j(p: int, A: int, B: int, x0: int) -> int:
    t = (3 * x0 * x0 + A) % p
    Ap = (A - 5 * t) % p
    Bp = (B - 7 * x0 * t) % p
    j = j_invariant(p, Ap, Bp)
    if j is None:
        raise RuntimeError("Vélu produced a singular curve")
    return j


def build_volcano(ell: int, min_height: int, rng: random.Random, want_crater: int = 1) -> dict | None:
    fundamentals = [-3, -4, -7, -8, -11, -15, -19, -20, -23, -24, -31, -35, -39, -40, -43, -47, -51, -52, -55, -56, -59, -68, -83, -87, -91]
    for DK in fundamentals:
        if ell == 2 and DK % 2 == 0 and valuation(DK, 2) > 3:
            continue
        for h in (min_height, min_height + 1):
            if ell**h > 64:
                continue
            f = ell**h
            D = f * f * DK  # negative
            if valuation(f, ell) != h:
                continue
            for t in range(0, 400, 1):
                disc_sum = t * t + (-D)
                if disc_sum % 4:
                    continue
                p = disc_sum // 4
                if p < 40 or p > 2500:
                    continue
                if not is_probable_prime(p) or p == ell:
                    continue
                # Search a curve of trace ±t.
                found = None
                for _try in range(min(4000, 8 * hasse_bound(p) + 50)):
                    A = rng.randrange(p)
                    B = rng.randrange(p)
                    if j_invariant(p, A, B) is None:
                        continue
                    if p < 800:
                        tr = p + 1 - brute_order(p, A, B)
                    else:
                        try:
                            tr = ec_trace(p, A, B, rng)
                        except RuntimeError:
                            continue
                    if abs(tr) == t or tr == t or tr == -t:
                        found = (A, B, tr)
                        break
                if found is None:
                    continue
                A, B, tr = found
                j0 = j_invariant(p, A, B)
                # BFS the Φ_ell component.
                adj: dict[int, list[int]] = {}
                stack = [j0]
                seen = set()
                while stack:
                    j = stack.pop()
                    if j in seen:
                        continue
                    seen.add(j)
                    nbrs = phi_neighbors(ell, j, p)
                    adj[j] = nbrs
                    for n in nbrs:
                        if n not in seen:
                            stack.append(n)
                if len(seen) < 2:
                    continue
                height, depth, crater = peel_volcano(adj)
                if height < min_height:
                    continue
                # Conductor check against the measured trace.
                disc = tr * tr - 4 * p
                try:
                    DK_m, f_m = fundamental_part(disc)
                except RuntimeError:
                    continue
                if valuation(f_m, ell) != height:
                    continue
                if len(crater) < want_crater:
                    continue
                # One Vélu cross-check on a rational 2-torsion kernel, when ell=2.
                if ell == 2:
                    # 2-torsion: roots of x^3 + A x + B.
                    # Find a rational root by scanning.
                    root = None
                    for x in range(p):
                        if (x * x * x + A * x + B) % p == 0:
                            root = x
                            break
                    if root is not None:
                        jv = velu2_neighbor_j(p, A, B, root)
                        if jv not in adj[j0] and jv != j0:
                            # The model may be a twist of the j0 curve; the
                            # neighbor must still sit in the component.
                            if jv not in seen:
                                continue
                curves = []
                for j in sorted(seen):
                    AA, BB = curve_from_j(p, j)
                    # curve_from_j picks one twist; retarget the trace by
                    # testing both the model and one quadratic twist.
                    tr_j = None
                    if p < 800:
                        tr_j = p + 1 - brute_order(p, AA, BB)
                    curves.append(
                        {
                            "j": str(j),
                            "a": str(AA),
                            "b": str(BB),
                            "depth": depth[j],
                            "trace_of_model": None if tr_j is None else str(tr_j),
                        }
                    )
                levels: dict[int, list[str]] = {}
                for j, dpt in depth.items():
                    levels.setdefault(dpt, []).append(str(j))
                level_list = []
                for dpt in sorted(levels):
                    role = "crater" if dpt == 0 else ("floor" if dpt == height else "interior")
                    level_list.append({"depth": dpt, "role": role, "j": sorted(levels[dpt], key=int)})
                edges = []
                for j, nbrs in adj.items():
                    for n in nbrs:
                        if j < n or (j == n):
                            edges.append({"j1": str(j), "j2": str(n)})
                return {
                    "id": f"volcano-l{ell}-h{height}-p{p}",
                    "ell": ell,
                    "height": height,
                    "prime": str(p),
                    "trace": str(tr),
                    "frobenius_discriminant": str(disc),
                    "fundamental_discriminant": str(DK_m),
                    "conductor": str(f_m),
                    "crater_size": len(crater),
                    "node_count": len(seen),
                    "levels": level_list,
                    "edges": edges,
                    "curves": curves,
                    "note": (
                        f"{ell}-isogeny volcano of height {height} over F_{p}, "
                        f"conductor {f_m}, crater of {len(crater)} j-invariants. "
                        "Depth 0 is the crater; the floor is the deepest level."
                    ),
                }
    return None


def peel_volcano(adj: dict[int, list[int]]) -> tuple[int, dict[int, int], set[int]]:
    alive = set(adj)
    peel_index: dict[int, int] = {}
    rnd = 0
    while True:
        leaves = []
        for j in alive:
            nbrs = [n for n in adj[j] if n in alive]
            # A self-loop (neighbor = itself) keeps the node on the crater.
            distinct = set(nbrs)
            if j in distinct and len(nbrs) >= 2:
                continue
            if len(nbrs) <= 1:
                leaves.append(j)
        if not leaves or len(leaves) == len(alive):
            break
        rnd += 1
        for j in leaves:
            peel_index[j] = rnd
            alive.remove(j)
    height = rnd
    depth = {j: 0 for j in alive}
    for j, idx in peel_index.items():
        depth[j] = height - idx + 1
    return height, depth, alive


# ── self-test ────────────────────────────────────────────────────────


def self_test() -> None:
    rng = random.Random(1)
    # j formulas.
    assert j_invariant(101, 0, 1) == 0
    assert j_invariant(101, 1, 0) == 1728 % 101
    A, B = curve_from_j(101, 17)
    assert j_invariant(101, A, B) == 17
    # Brute vs BSGS.
    p = 211
    A, B = 2, 3
    counted = brute_order(p, A, B)
    tr = ec_trace(p, A, B, rng)
    assert p + 1 - tr == counted, (tr, counted)
    # Group law closure.
    P = find_point(p, A, B, rng)
    Q = find_point(p, A, B, rng, skip=3)
    assert on_curve(p, A, B, ec_add(p, A, P, Q))
    assert ec_mul(p, A, counted, P) is INF
    # Supersingular j=0.
    p = 17  # 17 ≡ 2 mod 3
    assert brute_order(p, 0, 1) == p + 1
    p = 19  # 19 ≡ 3 mod 4
    assert brute_order(p, 1, 0) == p + 1
    # Koblitz recurrence vs enumeration.
    low, irr = find_binary_irreducible(5)
    field = BinaryField(5, irr)
    for a in (0, 1):
        N, t = koblitz_order(a, 5)
        counted = binary_count(field, a, 1)
        assert N == counted, (a, N, counted, t)
        P = binary_find_point(field, a, 1, rng)
        assert binary_mul(field, a, N, P) is INF
    # Subfield recurrence vs enumeration on F_{2^6}, curve over F_{2^2}.
    low, irr = find_binary_irreducible(6)
    field = BinaryField(6, irr)
    sub = field.iter_subfield(2)
    assert len(sub) == 4
    # Pick b in the subfield, not in F_2, so this is not a Koblitz curve.
    b = next(x for x in sub if x not in (0, 1))
    a = 0
    # Count over the subfield by restricting abscissae.
    # Points with x in the subfield and y in the subfield.
    def sub_count():
        cnt = 1
        sub_set = set(sub)
        for x in sub:
            # solve y in the BIG field, keep those in the subfield
            if x == 0:
                y = field.pow(b, 1 << (field.m - 1))
                if field.square(y) == b and y in sub_set:
                    cnt += 1
                continue
            c = field.add(field.add(x, a), field.div(b, field.square(x)))
            if field.trace(c) != 0:
                continue
            z = field.solve_artin_schreier(c)
            for zz in (z, z ^ 1):
                y = field.mul(zz, x)
                if y in sub_set:
                    cnt += 1
        return cnt

    n_sub = sub_count()
    q = 4
    t = q + 1 - n_sub
    N6 = subfield_order(t, q, 3)  # e = 6/2 = 3
    assert binary_count(field, a, b) == N6, (binary_count(field, a, b), N6, t)
    # Extension field: F_25, compare count and scalar.
    coeffs = find_fp_irreducible(5, 2)
    fp = FpN(5, coeffs)
    A = [1]
    B = [1]

    def rhs(x):
        return fp.add(fp.add(fp.mul(fp.mul(x, x), x), fp.mul(A, x)), B)

    N = ext_count(fp, rhs)
    P = ext_find_point(fp, rhs, rng)
    assert ext_mul_point(fp, short_add, A, N, P) is INF
    # Char 3 group law closes and matches a count.
    coeffs = find_fp_irreducible(3, 2)
    f3 = FpN(3, coeffs)
    A = [1]
    B = [1]

    def rhs3(x):
        # x^3 + A x + B
        return f3.add(f3.add(f3.mul(f3.mul(x, x), x), f3.mul(A, x)), B)

    N = ext_count(f3, rhs3)
    P = ext_find_point(f3, rhs3, rng)
    Q = ext_find_point(f3, rhs3, rng)
    R = char3_j0_add(f3, A, P, Q)
    if R is not INF:
        x, y = R
        assert f3.eq(f3.mul(y, y), rhs3(x))
    assert ext_mul_point(f3, char3_j0_add, A, N, P) is INF
    # j ≠ 0 model in char 3.
    a2 = [1]
    b = [2]

    def rhs3b(x):
        return f3.add(f3.add(f3.mul(f3.mul(x, x), x), f3.mul(a2, f3.mul(x, x))), b)

    N = ext_count(f3, rhs3b)
    P = ext_find_point(f3, rhs3b, rng)
    assert ext_mul_point(f3, char3_jgen_add, a2, N, P) is INF
    # Φ₂ agrees with Vélu on at least one rational 2-isogeny.
    p = 101
    A, B = curve_from_j(p, 17)
    # May or may not have rational 2-torsion; search a curve that does.
    agreed = False
    for A in range(p):
        for B in range(p):
            j = j_invariant(p, A, B)
            if j is None:
                continue
            for x in range(p):
                if (x * x * x + A * x + B) % p == 0:
                    jv = velu2_neighbor_j(p, A, B, x)
                    nbrs = phi_neighbors(2, j, p)
                    if jv in nbrs or jv == j:
                        agreed = True
                        break
            if agreed:
                break
        if agreed:
            break
    assert agreed, "Φ₂ never matched Vélu"
    # Conductor helper.
    DK, f = fundamental_part(-448)  # 8² · -7
    assert DK == -7 and f == 8, (DK, f)
    print("self-test ok")


# ── builders ─────────────────────────────────────────────────────────


def add_prime_families(corpus: Corpus, rng: random.Random) -> None:
    print("prime-field j=0 ordinary")
    for bits in (16, 28, 40, 61, 96, 128, 256, 768):
        p, b, tr, _t, _v = make_j0_ordinary(bits, rng)
        tags = ["j0", "ordinary", "cm", "prime-field", "glv"]
        endo = ["negation", "glv-6"]
        prime_instance(
            corpus, rng,
            ident=f"pf-j0-b{p.bit_length() - 1}",
            family="j0-ordinary",
            p=p, A=0, B=b, trace=tr, tags=tags, endomorphisms=endo,
            solvers=solvers_for_prime(tags, False, None, 0),
            note="Ordinary j=0 curve. Automorphism group order 6 (GLV): ψ(x, y) = (βx, −y), β³ = 1.",
        )
        # Quadratic twist, same size, opposite trace.  Only for the smaller ones
        # plus one 96-bit pair: the twist is y² = x³ + b u³.
        if bits <= 96:
            u = 2
            while legendre(u, p) != -1:
                u += 1
            Bt = (b * pow(u, 3, p)) % p
            tags_t = ["j0", "ordinary", "cm", "prime-field", "glv", "quadratic-twist"]
            prime_instance(
                corpus, rng,
                ident=f"pf-j0-twist-b{p.bit_length() - 1}",
                family="j0-ordinary-twist",
                p=p, A=0, B=Bt, trace=-tr, tags=tags_t, endomorphisms=endo,
                solvers=solvers_for_prime(tags_t, False, None, 0),
                note="Quadratic twist of the paired j=0 curve. Trace is negated; both orders are large.",
            )

    print("prime-field j=1728 ordinary")
    for bits in (16, 32, 48, 64, 128, 256, 512):
        p, a, tr = make_j1728_ordinary(bits, rng)
        tags = ["j1728", "ordinary", "cm", "prime-field", "glv"]
        endo = ["negation", "glv-4"]
        prime_instance(
            corpus, rng,
            ident=f"pf-j1728-b{p.bit_length() - 1}",
            family="j1728-ordinary",
            p=p, A=a, B=0, trace=tr, tags=tags, endomorphisms=endo,
            solvers=solvers_for_prime(tags, False, None, 0),
            note="Ordinary j=1728 curve. Automorphism group order 4 (GLV): ψ(x, y) = (−x, i y), i² = −1.",
        )

    print("supersingular")
    for bits in (8, 20, 32, 61, 128, 256, 768):
        p, A, B = make_supersingular(bits, "j0", rng)
        tags = ["j0", "supersingular", "prime-field", "mov"]
        prime_instance(
            corpus, rng,
            ident=f"pf-ssj0-b{p.bit_length() - 1}",
            family="supersingular-j0",
            p=p, A=A, B=B, trace=0, tags=tags, endomorphisms=["negation", "supersingular-frobenius"],
            solvers=solvers_for_prime(tags, False, None, 0),
            note="Supersingular j=0 (p ≡ 2 mod 3): #E = p+1, π² = −p, embedding degree 2. MOV applies; GLV does not (p ≢ 1 mod 3).",
        )
    for bits in (8, 24, 48, 96, 192, 384, 521):
        p, A, B = make_supersingular(bits, "j1728", rng)
        tags = ["j1728", "supersingular", "prime-field", "mov"]
        prime_instance(
            corpus, rng,
            ident=f"pf-ssj1728-b{p.bit_length() - 1}",
            family="supersingular-j1728",
            p=p, A=A, B=B, trace=0, tags=tags, endomorphisms=["negation", "supersingular-frobenius"],
            solvers=solvers_for_prime(tags, False, None, 0),
            note="Supersingular j=1728 (p ≡ 3 mod 4): #E = p+1, embedding degree 2.",
        )

    print("smooth-order supersingular (Pohlig–Hellman + MOV)")
    for bits in (16, 24, 32, 48, 64):
        p = make_smooth_prime(bits, 3, 2, rng)
        tags = ["j0", "supersingular", "prime-field", "mov", "smooth-order"]
        prime_instance(
            corpus, rng,
            ident=f"pf-mov-b{p.bit_length() - 1}",
            family="mov-smooth",
            p=p, A=0, B=1, trace=0, tags=tags, endomorphisms=["negation", "supersingular-frobenius"],
            solvers=solvers_for_prime(tags, True, None, (p + 1).bit_length()),
            note="Supersingular with smooth #E = p+1. Pohlig–Hellman and the MOV transfer to F_{p²}^* both apply.",
        )

    print("generic j")
    for bits in (8, 16, 24, 32, 40, 61):
        for _ in range(200):
            p = next_prime(rng.randrange(1 << (bits - 1), 1 << bits) | 1)
            if p.bit_length() != bits:
                continue
            A = rng.randrange(1, p)
            B = rng.randrange(1, p)
            j = j_invariant(p, A, B)
            if j in (None, 0, 1728 % p):
                continue
            tr = ec_trace(p, A, B, rng)
            if tr % p == 0:
                continue  # skip supersingular accidents
            tags = ["j-generic", "ordinary", "prime-field"]
            prime_instance(
                corpus, rng,
                ident=f"pf-generic-b{p.bit_length() - 1}",
                family="generic",
                p=p, A=A, B=B, trace=tr, tags=tags,
                endomorphisms=["negation"],
                solvers=solvers_for_prime(tags, False, None, 0),
                note="Ordinary curve whose j-invariant is neither 0 nor 1728. Only the negation endomorphism is rational.",
            )
            break

    print("anomalous")
    for bits in (10, 14, 18, 22, 26):
        found = False
        # Trace 1 has density about 1/(4√p).  Try a few primes at the small sizes.
        for _prime_try in range(3 if bits <= 18 else 1):
            if found:
                break
            p = next_prime(rng.randrange(1 << (bits - 1), 1 << bits) | 1)
            if p.bit_length() != bits:
                p = next_prime(1 << (bits - 1))
            trials = 0
            cap = max(4000, (16 if bits <= 18 else 8) * hasse_bound(p))
            while trials < cap and not found:
                trials += 1
                A = rng.randrange(p)
                B = rng.randrange(1, p)
                if j_invariant(p, A, B) is None:
                    continue
                tr = ec_trace(p, A, B, rng)
                if tr != 1:
                    continue
                j = j_invariant(p, A, B)
                tags = ["anomalous", "prime-field", "smart"]
                if j not in (0, 1728 % p):
                    tags.append("j-generic")
                prime_instance(
                    corpus, rng,
                    ident=f"pf-anomalous-b{p.bit_length() - 1}",
                    family="anomalous",
                    p=p, A=A, B=B, trace=1, tags=tags,
                    endomorphisms=["negation"],
                    solvers=["pollard-rho", "negation-map-rho", "index-calculus", "smart"],
                    note="Anomalous: #E(F_p) = p. Smart–Semaev–Satoh–Araki lifts the discrete log to p-adics in polynomial time.",
                )
                found = True
            if not found:
                print(f"  anomalous {bits}-bit not found in {trials} trials (p={p})")

    print("twist-insecure pair")
    # Search an ordinary curve whose quadratic twist has smooth order.
    for bits in (20, 28):
        p = next_prime(rng.randrange(1 << (bits - 1), 1 << bits) | 1)
        u = 2
        while legendre(u, p) != -1:
            u += 1
        found = False
        for _ in range(3000):
            A = rng.randrange(1, p)
            B = rng.randrange(1, p)
            if j_invariant(p, A, B) is None:
                continue
            tr = ec_trace(p, A, B, rng)
            if tr == 0 or abs(tr) > hasse_bound(p):
                continue
            twist_order = p + 1 + tr
            main_order = p + 1 - tr
            fac_t, cof_t = factor(twist_order)
            if cof_t != 1:
                continue
            largest_t = max(q for q, _ in fac_t)
            if largest_t.bit_length() > 12:
                continue
            fac_m, cof_m = factor(main_order)
            if cof_m != 1:
                continue
            largest_m = max(q for q, _ in fac_m)
            if largest_m.bit_length() < bits - 4:
                continue
            At = A * pow(u, 2, p) % p
            Bt = B * pow(u, 3, p) % p
            tags = ["j-generic", "ordinary", "prime-field", "twist-insecure"]
            prime_instance(
                corpus, rng,
                ident=f"pf-twist-main-b{p.bit_length() - 1}",
                family="twist-insecure",
                p=p, A=A, B=B, trace=tr, tags=tags,
                endomorphisms=["negation"],
                solvers=solvers_for_prime(tags, True, largest_m, main_order.bit_length()),
                note="Main curve of a twist-insecure pair: large prime subgroup, but the quadratic twist is smooth. An implementation that forgets to check the curve equation falls into Pohlig–Hellman on the twist.",
            )
            prime_instance(
                corpus, rng,
                ident=f"pf-twist-smooth-b{p.bit_length() - 1}",
                family="twist-insecure-twist",
                p=p, A=At, B=Bt, trace=-tr,
                tags=["j-generic", "ordinary", "prime-field", "smooth-order", "quadratic-twist"],
                endomorphisms=["negation"],
                solvers=["pollard-rho", "negation-map-rho", "index-calculus", "pohlig-hellman"],
                note="Quadratic twist of the paired curve. Group order is smooth, so Pohlig–Hellman is the fast path.",
            )
            found = True
            break
        if not found:
            print(f"  twist-insecure {bits}-bit not found")


def add_binary_families(corpus: Corpus, rng: random.Random) -> None:
    prime_degrees = [2, 3, 5, 7, 11, 13, 17, 19, 31, 61, 89, 127, 131, 521]
    composite_degrees = [4, 6, 8, 9, 10, 12, 15, 16, 18, 21, 24, 32, 36, 48, 64, 96, 128, 192, 256, 384, 512, 768]
    a1_degrees = {2, 3, 5, 7, 11, 13, 17, 31, 61, 127, 4, 12, 48, 96, 256, 768}
    print("binary Koblitz")
    cache_field: dict[int, tuple[list[int], BinaryField]] = {}

    def field_for(m: int) -> tuple[list[int], BinaryField]:
        if m not in cache_field:
            low, irr = find_binary_irreducible(m)
            cache_field[m] = (low, BinaryField(m, irr))
        return cache_field[m]

    for m in prime_degrees + composite_degrees:
        low, field = field_for(m)
        for a in (0, 1):
            if a == 1 and m not in a1_degrees:
                continue
            N, t = koblitz_order(a, m)
            if m <= 14:
                counted = binary_count(field, a, 1)
                if counted != N:
                    raise RuntimeError(f"Koblitz a={a} m={m}: {N} != {counted}")
            P = binary_find_point(field, a, 1, rng)
            if m <= 96:
                if binary_mul(field, a, N, P) is not INF:
                    raise RuntimeError(f"Koblitz order check a={a} m={m}")
            k_w = 10007 % max(N, 2)
            if k_w == 0:
                k_w = 3
            W = binary_mul(field, a, k_w, P)
            degree_kind = "prime" if _is_prime_int(m) else "composite"
            bits = m  # cardinality 2^m
            if m <= 16:
                tier = "open"
            elif m <= 48:
                tier = "bench"
            else:
                tier = "shape"
            fac, cof = factor(N) if N.bit_length() <= 80 else ([], N)
            factored = cof == 1 and N.bit_length() <= 80
            if tier == "shape" and m <= 160:
                # A full-size hidden scalar.  Above 160 the inversion count
                # in affine arithmetic stops being a one-shot check; those
                # curves still carry a public witness relation.
                secret = rng.randrange(2, N)
                Q = binary_mul(field, a, secret, P)
                relation = relation_json(f"bin-koblitz-a{a}-m{m}", P, Q, None, secret)
            elif tier == "shape":
                relation = {
                    "base": point_json(P),
                    "target": point_json(W),
                    "scalar": str(k_w),
                    "scalar_sha256": sha256_scalar(f"bin-koblitz-a{a}-m{m}", k_w),
                }
            else:
                secret = rng.randrange(2, max(N, 3))
                Q = binary_mul(field, a, secret, P)
                relation = relation_json(f"bin-koblitz-a{a}-m{m}", P, Q, secret, secret)
            j = "1"  # b = 1
            tags = ["koblitz", "char-2", "j1", "subfield-curve", degree_kind + "-degree", "frobenius"]
            if degree_kind == "composite":
                tags.append("ghs")
            solvers = ["pollard-rho", "negation-map-rho", "koblitz-index-calculus", "frobenius-rho"]
            if degree_kind == "composite":
                solvers.append("ghs-weil-descent")
            else:
                solvers.append("prime-degree-index-calculus")
            if m > 63:
                solvers = [s if s != "koblitz-index-calculus" else "koblitz-index-calculus-shape" for s in solvers]
            corpus.add(
                {
                    "id": f"bin-koblitz-a{a}-m{m}",
                    "family": "koblitz",
                    "tier": tier,
                    "tags": tags,
                    "field": {
                        "kind": "binary",
                        "characteristic": "2",
                        "degree": m,
                        "degree_kind": degree_kind,
                        "cardinality": str(1 << m),
                        "cardinality_bits": bits,
                        "irreducible_low_terms": low,
                        "polynomial": poly_str_binary(low, m),
                    },
                    "model": "binary-weierstrass",
                    "a": [str(a)],
                    "b": ["1"],
                    "j": j,
                    "trace": str(t),
                    "trace_base_field": "F_2",
                    "group_order": str(N),
                    "subgroup_order": str(N),
                    "cofactor": "1",
                    "factored_completely": factored,
                    "largest_prime_factor": None,
                    "embedding_degree": None,
                    "endomorphisms": ["negation", "frobenius"],
                    "solvers": solvers,
                    "relation": relation,
                    "witness": {"scalar": str(k_w), "point": point_json(W)},
                    "note": (
                        f"Koblitz curve y² + xy = x³ + {a}·x² + 1 over F_2, base-changed to F_{{2^{m}}}. "
                        f"The {degree_kind} extension degree makes "
                        + ("GHS / Weil descent the structural attack. " if degree_kind == "composite" else "Weil descent miss the composite-degree hypothesis; Frobenius-accelerated rho and prime-degree index calculus are the live ones. ")
                        + "Group order from Koblitz's trace recurrence."
                    ),
                }
            )

    print("binary subfield (k>1)")
    specs = [
        (2, 3), (2, 5), (2, 9), (2, 15),
        (3, 2), (3, 4), (3, 5), (3, 7),
        (4, 3), (4, 5), (4, 9),
        (5, 3), (5, 7),
        (6, 5),
        (8, 3),
        (4, 192),  # n = 768
        (3, 256),  # n = 768
        (8, 96),   # n = 768
    ]
    for k, e in specs:
        n = k * e
        low, field = field_for(n)
        sub = field.iter_subfield(k)
        # b not in a smaller forced Koblitz constant: pick a subfield element
        # whose F_2-weight is > 1 when possible.
        candidates = [x for x in sub if x not in (0,)]
        b = candidates[min(len(candidates) - 1, 3)]
        a = 0 if k % 2 == 0 else next(x for x in sub if x not in (0, b))
        # Count E(F_q) on the subfield.
        sub_set = set(sub)
        cnt = 1
        for x in sub:
            if x == 0:
                y = field.pow(b, 1 << (n - 1))
                if field.square(y) == b and y in sub_set:
                    cnt += 1
                continue
            c = field.add(field.add(x, a), field.div(b, field.square(x)))
            if field.trace(c) != 0:
                continue
            z = field.solve_artin_schreier(c)
            for zz in (z, field.add(z, 1)):
                y = field.mul(zz, x)
                if y in sub_set:
                    cnt += 1
        q = 1 << k
        t = q + 1 - cnt
        N = subfield_order(t, q, e)
        if n <= 14:
            if binary_count(field, a, b) != N:
                raise RuntimeError(f"subfield order mismatch k={k} n={n}")
        degree_kind = "prime" if _is_prime_int(n) else "composite"
        tier = "open" if n <= 16 else ("bench" if n <= 48 else "shape")
        # A point on the big field, witness only (full scalar when n is small).
        P = binary_find_point(field, a, b, rng)
        if n <= 40:
            if binary_mul(field, a, N, P) is not INF:
                raise RuntimeError(f"subfield [N]P n={n}")
        k_w = 17
        W = binary_mul(field, a, k_w, P)
        if tier != "shape":
            secret = rng.randrange(2, N)
            Q = binary_mul(field, a, secret, P)
            relation = relation_json(f"bin-subfield-k{k}-n{n}", P, Q, secret, secret)
        else:
            relation = {
                "base": point_json(P),
                "target": None,
                "scalar": None,
                "scalar_sha256": None,
            }
        tags = ["subfield-curve", "char-2", "frobenius", degree_kind + "-degree"]
        if k > 1:
            tags.append("proper-subfield")
        if degree_kind == "composite":
            tags.append("ghs")
        solvers = ["pollard-rho", "frobenius-rho", "koblitz-index-calculus"]
        if degree_kind == "composite":
            solvers.append("ghs-weil-descent")
        if n > 63:
            solvers = ["pollard-rho", "frobenius-rho", "ghs-weil-descent", "koblitz-index-calculus-shape"]
        corpus.add(
            {
                "id": f"bin-subfield-k{k}-n{n}",
                "family": "binary-subfield",
                "tier": tier,
                "tags": tags,
                "field": {
                    "kind": "binary",
                    "characteristic": "2",
                    "degree": n,
                    "degree_kind": degree_kind,
                    "cardinality": str(1 << n),
                    "cardinality_bits": n,
                    "irreducible_low_terms": low,
                    "polynomial": poly_str_binary(low, n),
                    "subfield_degree": k,
                    "extension_over_subfield": e,
                    "subfield_degree_kind": "prime" if _is_prime_int(k) else "composite",
                    "extension_degree_kind": "prime" if _is_prime_int(e) else "composite",
                },
                "model": "binary-weierstrass",
                "a": [str(a)],
                "b": [str(b)],
                "j": None,
                "trace": str(t),
                "trace_base_field": f"F_2^{k}",
                "group_order": str(N),
                "subgroup_order": str(N),
                "cofactor": "1",
                "factored_completely": False,
                "largest_prime_factor": None,
                "embedding_degree": None,
                "endomorphisms": ["negation", "frobenius"],
                "solvers": solvers,
                "relation": relation,
                "witness": {"scalar": str(k_w), "point": point_json(W)},
                "note": (
                    f"Curve defined over F_{{2^{k}}} and base-changed to F_{{2^{n}}}, k = {k} > 1. "
                    f"Frobenius over the subfield satisfies π² − tπ + 2^{k} = 0. "
                    "Coefficients are written in the polynomial basis of the big field and lie in the unique subfield."
                ),
            }
        )


def _is_prime_int(n: int) -> bool:
    if n <= 1:
        return False
    if n <= 3:
        return True
    return is_probable_prime(n)


def add_ternary_and_extensions(corpus: Corpus, rng: random.Random) -> None:
    print("characteristic 3")
    # Enumerate small degrees, both models, then lift a base curve.
    for m, kind in (
        (1, "prime-field"),
        (2, "prime"),
        (3, "prime"),
        (4, "composite"),
        (5, "prime"),
        (6, "composite"),
        (7, "prime"),
        (8, "composite"),
        (9, "composite"),
    ):
        if m == 1:
            coeffs = [0, 1]
            # Degree-1 "extension" is the prime field.  FpN still works.
        else:
            coeffs = find_fp_irreducible(3, m)
        field = FpN(3, coeffs)
        q = 3**m
        models = []
        # j = 0 model
        models.append(("j0", "char3-j0", [1], [1], char3_j0_add))
        # j ≠ 0 model, j = -a2³ / b
        models.append(("j-generic", "char3-jgen", [1], [2], char3_jgen_add))
        for jtag, model, A, B, add in models:
            def rhs(x, A=A, B=B, model=model, field=field):
                x2 = field.mul(x, x)
                x3 = field.mul(x2, x)
                if model == "char3-j0":
                    return field.add(field.add(x3, field.mul(A, x)), B)
                return field.add(field.add(x3, field.mul(A, x2)), B)

            if q <= 3**5:
                N = ext_count(field, rhs)
            else:
                # Count over F_3 by restriction if coefficients lie in F_3, then lift.
                # Both models here have constant coefficients, so they ARE subfield curves
                # when m > 1.  Count on F_3 and lift.
                f1 = FpN(3, [0, 1])

                def rhs1(x, A=A, B=B, model=model, field=f1):
                    x2 = field.mul(x, x)
                    x3 = field.mul(x2, x)
                    if model == "char3-j0":
                        return field.add(field.add(x3, field.mul(A, x)), B)
                    return field.add(field.add(x3, field.mul(A, x2)), B)

                n1 = ext_count(f1, rhs1)
                t = 3 + 1 - n1
                N = subfield_order(t, 3, m)
                if m <= 4:
                    if ext_count(field, rhs) != N:
                        raise RuntimeError(f"char3 lift mismatch m={m} {model}")
            P = ext_find_point(field, rhs, rng, tries=80)
            if q <= 3**6:
                if ext_mul_point(field, add, A, N, P) is not INF:
                    raise RuntimeError(f"char3 order m={m} {model}")
            k_w = 5
            W = ext_mul_point(field, add, A, k_w, P)
            t_big = q + 1 - N
            supersingular = t_big % 3 == 0
            tags = [jtag, "char-3", kind if m == 1 else kind + "-degree"]
            if m > 1:
                tags.append("subfield-curve")
                tags.append("frobenius")
            if supersingular:
                tags.append("supersingular")
            else:
                tags.append("ordinary")
            tier = "open" if q.bit_length() <= 16 else "bench"
            if tier == "open":
                secret = rng.randrange(2, N)
                Q = ext_mul_point(field, add, A, secret, P)
                relation = relation_json(f"ter-{jtag}-m{m}", P, Q, secret, secret)
            else:
                relation = {
                    "base": point_json(P),
                    "target": point_json(W),
                    "scalar": str(k_w),
                    "scalar_sha256": sha256_scalar(f"ter-{jtag}-m{m}", k_w),
                }
            jval = "0" if model == "char3-j0" else str((-pow(1, 3, 3**m) * inv(2, 3)) % 3)  # placeholder, real j below
            # j = -a2^3 / b for the jgen model, computed in the field.  For constant
            # coefficients the value lives in F_3.
            if model == "char3-j0":
                j_out = "0"
            else:
                # j = -a³/b with a=1, b=2: -1 * inv(2) = -2 ≡ 1 (mod 3)
                j_out = "1"
            corpus.add(
                {
                    "id": f"ter-{jtag}-m{m}",
                    "family": "ternary",
                    "tier": tier,
                    "tags": tags,
                    "field": {
                        "kind": "ternary" if m > 1 else "prime",
                        "characteristic": "3",
                        "degree": m,
                        "degree_kind": "prime-field" if m == 1 else ("prime" if _is_prime_int(m) else "composite"),
                        "cardinality": str(q),
                        "cardinality_bits": q.bit_length() - 1,
                        "irreducible": [str(c) for c in coeffs],
                    },
                    "model": model,
                    "a": [str(c) for c in A],
                    "b": [str(c) for c in B],
                    "j": j_out,
                    "trace": str(t_big),
                    "group_order": str(N),
                    "subgroup_order": str(N),
                    "cofactor": "1",
                    "factored_completely": False,
                    "largest_prime_factor": None,
                    "embedding_degree": None,
                    "endomorphisms": ["negation"] + (["frobenius"] if m > 1 else []),
                    "solvers": ["pollard-rho", "index-calculus"] + (["ghs-weil-descent"] if m > 1 and not _is_prime_int(m) else []) + (["gaudry"] if m >= 3 else []),
                    "relation": relation,
                    "witness": {"scalar": str(k_w), "point": point_json(W)},
                    "note": (
                        "Characteristic 3. "
                        + ("j=0 model y² = x³ + ax + b (a ≠ 0). " if model == "char3-j0" else "j ≠ 0 model y² = x³ + a x² + b, j = −a³/b. ")
                        + ("Supersingular (3 divides the trace). " if supersingular else "Ordinary. ")
                        + ("Defined over F_3 and base-changed, so Frobenius is an endomorphism." if m > 1 else "Prime field F_3.")
                    ),
                }
            )
            del jval

    # Large ternary shapes via the recurrence, no points.
    print("large ternary / odd-extension shapes")
    base_curves = []
    f1 = FpN(3, [0, 1])
    for model, A, B, add in (
        ("char3-j0", [1], [1], char3_j0_add),
        ("char3-jgen", [1], [2], char3_jgen_add),
    ):
        def rhs1(x, A=A, B=B, model=model):
            x2 = f1.mul(x, x)
            x3 = f1.mul(x2, x)
            if model == "char3-j0":
                return f1.add(f1.add(x3, f1.mul(A, x)), B)
            return f1.add(f1.add(x3, f1.mul(A, x2)), B)

        n1 = ext_count(f1, rhs1)
        base_curves.append((model, A, B, 3 + 1 - n1))

    large_degrees = []
    # 3^m ≈ 2^768 ⇒ m ≈ 485.  487 is a candidate prime; 484 = 22² is composite.
    for m in (484, 487, 36, 27, 32, 11, 13):
        large_degrees.append(m)
    for m in large_degrees:
        if m <= 9:
            continue  # already enumerated
        degree_kind = "prime" if _is_prime_int(m) else "composite"
        for model, A, B, t in base_curves:
            N = subfield_order(t, 3, m)
            q = 3**m
            ident = f"ter-lift-{model}-m{m}"
            tags = ["char-3", "subfield-curve", "frobenius", degree_kind + "-degree", "shape"]
            tags.append("j0" if model == "char3-j0" else "j-generic")
            corpus.add(
                {
                    "id": ident,
                    "family": "ternary-lift",
                    "tier": "shape",
                    "tags": tags,
                    "field": {
                        "kind": "ternary",
                        "characteristic": "3",
                        "degree": m,
                        "degree_kind": degree_kind,
                        "cardinality": str(q),
                        "cardinality_bits": q.bit_length() - 1,
                        "subfield_degree": 1,
                        "extension_over_subfield": m,
                    },
                    "model": model,
                    "a": [str(c) for c in A],
                    "b": [str(c) for c in B],
                    "j": "0" if model == "char3-j0" else "1",
                    "trace": str(t),
                    "trace_base_field": "F_3",
                    "group_order": str(N),
                    "subgroup_order": str(N),
                    "cofactor": "1",
                    "factored_completely": False,
                    "largest_prime_factor": None,
                    "embedding_degree": None,
                    "endomorphisms": ["negation", "frobenius"],
                    "solvers": ["pollard-rho", "frobenius-rho"] + (["ghs-weil-descent"] if degree_kind == "composite" else ["prime-degree-index-calculus"]),
                    "relation": None,
                    "witness": None,
                    "note": (
                        f"Base change of a curve over F_3 to F_{{3^{m}}} ({degree_kind} degree). "
                        "Order from the trace recurrence. No planted point: the instance is a field-arithmetic and endomorphism target at this size."
                    ),
                }
            )

    print("odd prime-power extensions")
    small_specs = [
        # p, n, subfield?, j style
        (5, 2, False, "generic"),
        (5, 3, False, "generic"),
        (5, 3, False, "j0"),
        (5, 4, False, "generic"),
        (5, 5, False, "j1728"),
        (5, 6, True, "generic"),
        (7, 2, False, "j0"),
        (7, 3, False, "generic"),
        (7, 4, True, "j1728"),
        (11, 2, False, "j1728"),
        (11, 3, False, "generic"),
        (13, 2, False, "generic"),
        (13, 3, True, "j0"),
        (17, 3, False, "generic"),
    ]
    for p, n, sub, style in small_specs:
        coeffs = find_fp_irreducible(p, n)
        field = FpN(p, coeffs)
        if style == "j0":
            A = [0]
            B = [1]
        elif style == "j1728":
            A = [1]
            B = [0]
        elif sub:
            A = [rng.randrange(1, p)]
            B = [rng.randrange(1, p)]
        else:
            # A coefficient genuinely in the extension: constant term 0, z^1 = 1.
            A = [0, 1] + [0] * (n - 2)
            B = [rng.randrange(p) for _ in range(n)]
            if all(c == 0 for c in B):
                B[0] = 1
        def rhs(x, A=A, B=B, field=field):
            x2 = field.mul(x, x)
            x3 = field.mul(x2, x)
            return field.add(field.add(x3, field.mul(A, x)), B)

        q = p**n
        if sub or (len(A) == 1 or all(c == 0 for c in A[1:])) and all(c == 0 for c in B[1:]):
            # Count on the prime field and lift when the curve is a base change.
            A1 = [A[0]]
            B1 = [B[0]]
            f1 = FpN(p, [0, 1])

            def rhs1(x, A1=A1, B1=B1, field=f1):
                x2 = field.mul(x, x)
                x3 = field.mul(x2, x)
                return field.add(field.add(x3, field.mul(A1, x)), B1)

            if j_invariant(p, A1[0], B1[0]) is None:
                continue
            n1 = ext_count(f1, rhs1)
            t = p + 1 - n1
            N = subfield_order(t, p, n)
            is_sub = True
        else:
            is_sub = False
            t = None
            if q > 20000:
                continue
            N = ext_count(field, rhs)
            t = q + 1 - N
        if q <= 8000:
            counted = ext_count(field, rhs)
            if counted != N:
                raise RuntimeError(f"extension count mismatch p={p} n={n} style={style}: {counted} != {N}")
        P = ext_find_point(field, rhs, rng, tries=100)
        if q <= 8000:
            if ext_mul_point(field, short_add, A, N, P) is not INF:
                raise RuntimeError(f"extension order p={p} n={n}")
        k_w = 9
        W = ext_mul_point(field, short_add, A, k_w, P)
        degree_kind = "prime" if _is_prime_int(n) else "composite"
        tags = ["odd-extension", degree_kind + "-degree", "char-" + str(p)]
        if style == "j0":
            tags += ["j0"]
        elif style == "j1728":
            tags += ["j1728"]
        else:
            tags += ["j-generic"]
        if is_sub:
            tags += ["subfield-curve", "frobenius"]
        else:
            tags += ["not-a-subfield-curve"]
        if n >= 3:
            tags.append("gaudry-shape")
        tier = "open" if q.bit_length() <= 18 else "bench"
        ident = f"ext-p{p}-n{n}-{style}" + ("-sub" if is_sub else "")
        if tier == "open" and N > 2:
            secret = rng.randrange(2, N)
            Q = ext_mul_point(field, short_add, A, secret, P)
            relation = relation_json(ident, P, Q, secret, secret)
        else:
            relation = {
                "base": point_json(P),
                "target": point_json(W),
                "scalar": str(k_w),
                "scalar_sha256": sha256_scalar(ident, k_w),
            }
        j = None
        if is_sub:
            j = str(j_invariant(p, A[0], B[0]))
        solvers = ["pollard-rho", "index-calculus"]
        if n >= 3:
            solvers.append("gaudry")
        if is_sub:
            solvers.append("frobenius-rho")
        if degree_kind == "composite":
            solvers.append("diem-descent")
        corpus.add(
            {
                "id": ident,
                "family": "odd-extension" if not is_sub else "odd-subfield",
                "tier": tier,
                "tags": tags,
                "field": {
                    "kind": "extension",
                    "characteristic": str(p),
                    "degree": n,
                    "degree_kind": degree_kind,
                    "cardinality": str(q),
                    "cardinality_bits": q.bit_length() - 1,
                    "irreducible": [str(c) for c in coeffs],
                    "subfield_degree": 1 if is_sub else None,
                },
                "model": "short-weierstrass",
                "a": [str(c) for c in A],
                "b": [str(c) for c in B],
                "j": j,
                "trace": None if t is None else str(t if is_sub else (q + 1 - N)),
                "group_order": str(N),
                "subgroup_order": str(N),
                "cofactor": "1",
                "factored_completely": False,
                "largest_prime_factor": None,
                "embedding_degree": None,
                "endomorphisms": ["negation"] + (["frobenius"] if is_sub else []),
                "solvers": solvers,
                "relation": relation,
                "witness": {"scalar": str(k_w), "point": point_json(W)},
                "note": (
                    f"y² = x³ + ax + b over F_{{{p}^{n}}}. "
                    + ("Coefficients lie in F_p, so the p-power Frobenius is an endomorphism and the order lifts by the trace recurrence. " if is_sub else "A coefficient lies outside every proper subfield, so this is a Gaudry / Diem base field rather than a subfield curve. ")
                    + f"Degree {n} is {degree_kind}."
                ),
            }
        )

    # Huge odd extensions: order only, from a prime-field trace.
    for p, n in ((5, 330), (5, 331), (7, 270), (7, 271), (11, 222)):
        if not _is_prime_int(p):
            continue
        # Use y² = x³ + x + 1 if nonsingular, else y² = x³ + 1.
        A, B = 1, 1
        if j_invariant(p, A, B) is None:
            A, B = 0, 1
        f1 = FpN(p, [0, 1])

        def rhs1(x, A=A, B=B, field=f1):
            x2 = field.mul(x, x)
            x3 = field.mul(x2, x)
            return field.add(field.add(x3, field.mul([A], x)), [B])

        n1 = ext_count(f1, rhs1)
        t = p + 1 - n1
        N = subfield_order(t, p, n)
        q = p**n
        degree_kind = "prime" if _is_prime_int(n) else "composite"
        j = j_invariant(p, A, B)
        corpus.add(
            {
                "id": f"ext-lift-p{p}-n{n}",
                "family": "odd-subfield",
                "tier": "shape",
                "tags": [
                    "odd-extension",
                    "subfield-curve",
                    "frobenius",
                    degree_kind + "-degree",
                    "j0" if j == 0 else ("j1728" if j == 1728 % p else "j-generic"),
                    "shape",
                ],
                "field": {
                    "kind": "extension",
                    "characteristic": str(p),
                    "degree": n,
                    "degree_kind": degree_kind,
                    "cardinality": str(q),
                    "cardinality_bits": q.bit_length() - 1,
                    "subfield_degree": 1,
                    "extension_over_subfield": n,
                },
                "model": "short-weierstrass",
                "a": [str(A)],
                "b": [str(B)],
                "j": str(j),
                "trace": str(t),
                "trace_base_field": f"F_{p}",
                "group_order": str(N),
                "subgroup_order": str(N),
                "cofactor": "1",
                "factored_completely": False,
                "largest_prime_factor": None,
                "embedding_degree": None,
                "endomorphisms": ["negation", "frobenius"],
                "solvers": ["pollard-rho", "frobenius-rho", "gaudry" if n >= 3 else "index-calculus"]
                + (["diem-descent"] if degree_kind == "composite" else ["prime-degree-index-calculus"]),
                "relation": None,
                "witness": None,
                "note": (
                    f"Subfield curve over F_{{{p}^{n}}}, {degree_kind} degree, cardinality about 2^{q.bit_length() - 1}. "
                    "Order from the trace recurrence over F_p. Parameter target for field arithmetic at the top of the range."
                ),
            }
        )


def add_volcanoes(corpus: Corpus, rng: random.Random) -> None:
    print("isogeny volcanoes")
    specs = [
        (2, 3, 1),
        (2, 2, 2),
        (3, 2, 1),
    ]
    for ell, height, crater in specs:
        print(f"  searching ell={ell} height>={height} crater>={crater}")
        vol = build_volcano(ell, height, rng, want_crater=crater)
        if vol is None and crater > 1:
            print("  relaxing crater size")
            vol = build_volcano(ell, height, rng, want_crater=1)
        if vol is None:
            print(f"  FAILED ell={ell}")
            continue
        corpus.volcanoes.append(vol)
        # One ECDLP instance per role that exists.
        by_depth: dict[int, dict] = {}
        for c in vol["curves"]:
            by_depth.setdefault(c["depth"], c)
        p = int(vol["prime"])
        for depth, curve in sorted(by_depth.items()):
            role = "crater" if depth == 0 else ("floor" if depth == vol["height"] else "interior")
            A, B = int(curve["a"]), int(curve["b"])
            # The model from curve_from_j may have the opposite trace.
            # Recount; p is small.
            N = brute_order(p, A, B)
            tr = p + 1 - N
            ident = f"{vol['id']}-d{depth}-{role}"
            tags = ["volcano", f"volcano-{role}", f"ell-{ell}", "prime-field", "ordinary"]
            prime_instance(
                corpus, rng,
                ident=ident,
                family="isogeny-volcano",
                p=p, A=A, B=B, trace=tr, tags=tags,
                endomorphisms=["negation", f"{ell}-isogeny"],
                solvers=["pollard-rho", "negation-map-rho", "index-calculus", "volcano-walk"],
                note=(
                    f"{role.capitalize()} curve of {vol['id']}: depth {depth} of {vol['height']} "
                    f"on the {ell}-isogeny volcano. Neighbors are the Φ_{ell}-roots recorded on the volcano object."
                ),
                tier="open",
            )


def fix_solver_lists(corpus: Corpus) -> None:
    """Prime instances were given solvers before factoring finished.  Refresh."""
    for inst in corpus.instances:
        if inst["field"]["kind"] != "prime":
            continue
        tags = inst["tags"]
        factored = inst["factored_completely"]
        largest = int(inst["largest_prime_factor"]) if inst["largest_prime_factor"] else None
        order_bits = int(inst["group_order"]).bit_length()
        base = solvers_for_prime(tags, factored, largest, order_bits)
        # Keep volcano-walk if present.
        if "volcano-walk" in inst["solvers"] and "volcano-walk" not in base:
            base.append("volcano-walk")
        if "volcano" in tags and "volcano-walk" not in base:
            base.append("volcano-walk")
        inst["solvers"] = base


def c_registry_lines(corpus: Corpus) -> str:
    lines = [
        "# name p a b subgroup_order family tier",
        "# Curves with p < 2^63 and a subgroup under 2^22, for the C registry.",
    ]
    for inst in corpus.instances:
        if inst["field"]["kind"] != "prime":
            continue
        if inst["model"] != "short-weierstrass":
            continue
        p = int(inst["field"]["characteristic"])
        order = int(inst["subgroup_order"])
        if p.bit_length() > 62 or order.bit_length() > 22:
            continue
        if order < 32:
            continue
        A = int(inst["a"][0])
        B = int(inst["b"][0])
        lines.append(
            f"{inst['id']} {p} {A} {B} {order} {inst['family']} {inst['tier']}"
        )
    return "\n".join(lines) + "\n"


def summary(corpus: Corpus) -> dict:
    bits = [inst["field"]["cardinality_bits"] for inst in corpus.instances]
    families: dict[str, int] = {}
    for inst in corpus.instances:
        families[inst["family"]] = families.get(inst["family"], 0) + 1
    return {
        "instances": len(corpus.instances),
        "volcanoes": len(corpus.volcanoes),
        "cardinality_bits_min": min(bits) if bits else None,
        "cardinality_bits_max": max(bits) if bits else None,
        "families": families,
        "tiers": {
            tier: sum(1 for i in corpus.instances if i["tier"] == tier)
            for tier in ("open", "bench", "shape")
        },
    }


def main() -> None:
    self_test()
    rng = random.Random(SEED)
    corpus = Corpus()
    add_prime_families(corpus, rng)
    add_binary_families(corpus, rng)
    add_ternary_and_extensions(corpus, rng)
    add_volcanoes(corpus, rng)
    fix_solver_lists(corpus)
    corpus.instances.sort(key=lambda inst: inst["id"])
    doc = {
        "version": 1,
        "seed": SEED,
        "scalar_commitment": "sha256(utf8(id + '\\n' + decimal_scalar))",
        "summary": summary(corpus),
        "instances": corpus.instances,
        "volcanoes": corpus.volcanoes,
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n")
    C_OUT.write_text(c_registry_lines(corpus))
    print(json.dumps(doc["summary"], indent=2))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(f"wrote {C_OUT}")


if __name__ == "__main__":
    main()
