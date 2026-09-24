#!/usr/bin/env python3
"""Generate the elliptic-curve challenge corpus.

Every group order is obtained independently of the scalar-multiplication
implementation that later checks it:

* prime-field CM curves, from a representation 4p = t^2 - D v^2;
* binary Koblitz curves, from the integer Frobenius recurrence;
* subfield curves, by counting points over the field of definition and
  lifting the trace;
* small random curves, by enumeration or Mestre–Shanks.

`[n]G = O` is then checked with the group law whenever that scalar
multiplication is cheap. Larger extension curves keep the recurrence
certificate and a published short multiple instead.

Run from anywhere:

    python3 challenges/ecc/generate.py
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from decimal import Decimal, getcontext, ROUND_HALF_EVEN
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CURVE_DIR = ROOT / "curves"
INSPECT_DIR = ROOT / "inspect"

# Classical modular polynomials Φ_2 and Φ_3, low-to-high in each variable,
# stored as (power of X, power of Y) -> coefficient. Φ_3(0, 0) = 0.
PHI = {
    2: {
        (3, 0): 1,
        (0, 3): 1,
        (2, 2): -1,
        (2, 1): 1488,
        (1, 2): 1488,
        (2, 0): -162000,
        (0, 2): -162000,
        (1, 1): 40773375,
        (1, 0): 8748000000,
        (0, 1): 8748000000,
        (0, 0): -157464000000000,
    },
    3: {
        (4, 0): 1,
        (0, 4): 1,
        (3, 3): -1,
        (3, 2): 2232,
        (2, 3): 2232,
        (3, 1): -1069956,
        (1, 3): -1069956,
        (3, 0): 36864000,
        (0, 3): 36864000,
        (2, 2): 2587918086,
        (2, 1): 8900222976000,
        (1, 2): 8900222976000,
        (2, 0): 452984832000000,
        (0, 2): 452984832000000,
        (1, 1): -770845966336000000,
        (1, 0): 1855425871872000000000,
        (0, 1): 1855425871872000000000,
    },
}

# Class-number-1 j-invariants. The Hilbert class polynomial is linear.
CLASS_NUMBER_ONE = {
    -3: 0,
    -4: 1728,
    -7: -3375,
    -8: 8000,
    -11: -32768,
    -19: -884736,
    -43: -884736000,
    -67: -147197952000,
    -163: -262537412640768000,
}

CURVES: list[dict] = []


def hx(n: int) -> str:
    if n < 0:
        return "-" + hx(-n)
    return "0x" + format(n, "x")


def isqrt(n: int) -> int:
    if n < 0:
        raise ValueError("isqrt of negative")
    return int(math.isqrt(n))


def modinv(a: int, m: int) -> int:
    return pow(a % m, -1, m)


class Rng:
    """Deterministic 64-bit LCG. Corpus generation does not need a CSPRNG."""

    def __init__(self, seed: int):
        self.s = seed & ((1 << 64) - 1)

    def next(self) -> int:
        self.s = (self.s * 6364136223846793005 + 1) & ((1 << 64) - 1)
        return self.s

    def below(self, n: int) -> int:
        if n <= 1:
            return 0
        # Enough bits for moduli up to 2^768.
        x = 0
        bits = 0
        need = n.bit_length() + 64
        while bits < need:
            x = (x << 64) | self.next()
            bits += 64
        return x % n

    def element_digits(self, p: int, degree: int) -> list[int]:
        return [self.below(p) for _ in range(degree)]


def sieve(limit: int) -> list[int]:
    mark = bytearray(b"\x01") * (limit + 1)
    mark[0:2] = b"\x00\x00"
    for i in range(2, isqrt(limit) + 1):
        if mark[i]:
            step = i
            start = i * i
            mark[start : limit + 1 : step] = b"\x00" * (((limit - start) // step) + 1)
    return [i for i in range(2, limit + 1) if mark[i]]


PRIMES = sieve(1_000_003)
SMALL_PRIME_SET = set(PRIMES)


def is_probable_prime(n: int) -> bool:
    if n < 2:
        return False
    for p in PRIMES:
        if p * p > n:
            return True
        if n % p == 0:
            return n == p
    # Fixed bases. A pass is a Miller–Rabin screen, not a primality proof,
    # except for n below the well-known deterministic bound for these bases.
    d = n - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in (2, 3, 5, 7, 11, 13, 23, 29, 31, 37):
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


def prime_of_bits(bits: int, seed: int) -> int:
    rng = Rng(seed)
    if bits < 2:
        raise ValueError(bits)
    for _ in range(100000):
        n = (1 << (bits - 1)) | rng.below(1 << (bits - 1)) | 1
        if is_probable_prime(n):
            return n
    raise RuntimeError(f"no {bits}-bit prime")


def legendre(a: int, p: int) -> int:
    a %= p
    if a == 0:
        return 0
    return 1 if pow(a, (p - 1) // 2, p) == 1 else -1


def tonelli(n: int, p: int) -> int | None:
    n %= p
    if n == 0:
        return 0
    if legendre(n, p) != 1:
        return None
    if p % 4 == 3:
        return pow(n, (p + 1) // 4, p)
    # Factor p-1 = q * 2^s
    q = p - 1
    s = 0
    while q % 2 == 0:
        q //= 2
        s += 1
    z = 2
    while legendre(z, p) != -1:
        z += 1
    m = s
    c = pow(z, q, p)
    t = pow(n, q, p)
    r = pow(n, (q + 1) // 2, p)
    while t != 1:
        i = 1
        tt = pow(t, 2, p)
        while tt != 1:
            tt = pow(tt, 2, p)
            i += 1
            if i == m:
                return None
        b = pow(c, 1 << (m - i - 1), p)
        r = (r * b) % p
        c = (b * b) % p
        t = (t * c) % p
        m = i
    return r


def valuation(n: int, p: int) -> int:
    v = 0
    if n < 0:
        n = -n
    while n and n % p == 0:
        n //= p
        v += 1
    return v


def factor_smooth(n: int) -> tuple[int, int, bool]:
    """Split n = h * r with h smooth (primes <= 10^6, plus a short rho) and r cofactor.

    Returns (h, r, r_is_probable_prime). r = 1 when n is fully smooth.
    """
    if n < 1:
        raise ValueError(n)
    h = 1
    for p in PRIMES:
        if p * p > n:
            break
        while n % p == 0:
            n //= p
            h *= p
    if n > 1 and not is_probable_prime(n):
        fac = pollard_rho_factor(n)
        if fac and fac not in (1, n):
            while n % fac == 0:
                n //= fac
                h *= fac
            # The cofactor of the discovered factor may still be composite.
            if n > 1 and not is_probable_prime(n):
                fac2 = pollard_rho_factor(n, limit=50000)
                if fac2 and fac2 not in (1, n):
                    while n % fac2 == 0:
                        n //= fac2
                        h *= fac2
    probable = n == 1 or is_probable_prime(n)
    return h, n, probable


def pollard_rho_factor(n: int, limit: int = 200000) -> int | None:
    if n % 2 == 0:
        return 2
    x = y = 2
    d = 1
    for _ in range(limit):
        x = (x * x + 1) % n
        y = (y * y + 1) % n
        y = (y * y + 1) % n
        d = math.gcd(abs(x - y), n)
        if 1 < d < n:
            return d
        if d == n:
            return None
    return None


def sha_int(label: str, counter: int, bits: int) -> int:
    out = 0
    have = 0
    c = 0
    while have < bits:
        block = hashlib.sha256(f"{label}:{counter}:{c}".encode()).digest()
        out = (out << 256) | int.from_bytes(block, "big")
        have += 256
        c += 1
    return out & ((1 << bits) - 1) if bits else 0


# ---------------------------------------------------------------------------
# Prime-field short Weierstrass curves, characteristic > 3.
# ---------------------------------------------------------------------------

INF = None  # point at infinity


def ec_add(P, Q, a, p):
    if P is INF:
        return Q
    if Q is INF:
        return P
    x1, y1 = P
    x2, y2 = Q
    if x1 == x2:
        if (y1 + y2) % p == 0:
            return INF
        lam = (3 * x1 * x1 + a) * modinv(2 * y1, p) % p
    else:
        lam = (y2 - y1) * modinv(x2 - x1, p) % p
    x3 = (lam * lam - x1 - x2) % p
    y3 = (lam * (x1 - x3) - y1) % p
    return (x3, y3)


def ec_mul(k, P, a, p):
    if k < 0:
        return ec_mul(-k, ec_neg(P, p), a, p)
    R = INF
    Q = P
    while k:
        if k & 1:
            R = ec_add(R, Q, a, p)
        Q = ec_add(Q, Q, a, p)
        k >>= 1
    return R


def ec_neg(P, p):
    if P is INF:
        return INF
    return (P[0], (-P[1]) % p)


def on_short(P, a, b, p) -> bool:
    if P is INF:
        return True
    x, y = P
    return (y * y - (x * x * x + a * x + b)) % p == 0


def j_invariant(a: int, b: int, p: int) -> int:
    delta = (-16 * (4 * pow(a, 3, p) + 27 * b * b)) % p
    if delta == 0:
        raise ValueError("singular")
    return (1728 * 4 * pow(a, 3, p) * modinv(4 * pow(a, 3, p) + 27 * b * b, p)) % p


def curve_from_j(j: int, p: int) -> tuple[int, int]:
    j %= p
    if j == 0:
        return 0, 1
    if j == 1728 % p:
        return 1, 0
    c = j * modinv((1728 - j) % p, p) % p
    # a = 3c, b = 2c is the model whose j-invariant is j. The opposite sign
    # on a produces a different j.
    return (3 * c) % p, (2 * c) % p


def twist_short(a, b, d, p):
    """Quadratic twist by d: (x, y) = (d x', d^{3/2} y') rescales coefficients."""
    return (a * d * d) % p, (b * d * d * d) % p


def random_point_prime(a, b, p, rng: Rng, salt: int):
    for i in range(1, 100000):
        x = (rng.below(p) + i * salt) % p
        rhs = (x * x * x + a * x + b) % p
        y = tonelli(rhs, p)
        if y is not None:
            return (x, y)
    raise RuntimeError("no point")


def hash_point_prime(a, b, p, label: str):
    for i in range(100000):
        x = sha_int(label, i, max(p.bit_length(), 2)) % p
        rhs = (x * x * x + a * x + b) % p
        y = tonelli(rhs, p)
        if y is not None:
            return (x, y)
    raise RuntimeError("hash-to-curve failed")


def brute_order(a, b, p) -> int:
    n = 1
    for x in range(p):
        n += 1 + legendre((x * x * x + a * x + b) % p, p)
    return n


def _factor_complete(n: int) -> list[int]:
    if n <= 1:
        return []
    if is_probable_prime(n):
        return [n]
    fac = None
    for p in PRIMES:
        if p * p > n:
            break
        if n % p == 0:
            fac = p
            break
    if fac is None:
        fac = pollard_rho_factor(n, limit=2_000_000)
    if fac is None or fac in (1, n):
        raise RuntimeError(f"failed to factor {n}")
    return _factor_complete(fac) + _factor_complete(n // fac)


def _point_key(P):
    return ("O",) if P is INF else (P[0], P[1])


def hasse_annihilator(P, a, p) -> int:
    """Some positive N with |N - (p+1)| <= 2 sqrt(p) + slack and [N]P = O."""
    if P is INF:
        return 1
    half = isqrt(4 * p) + 2
    m = isqrt(half) + 2
    table = {}
    R = INF
    for j in range(m):
        key = _point_key(R)
        if key in table:
            return j - table[key]
        table[key] = j
        R = ec_add(R, P, a, p)
    step = ec_mul(m, P, a, p)
    neg_step = ec_neg(step, p)
    plus = ec_mul(p + 1, P, a, p)
    minus = plus
    for i in range(m + 3):
        for sign, G in ((1, plus), (-1, minus)):
            key = _point_key(G)
            if key in table:
                j = table[key]
                N = p + 1 + sign * i * m - j
                if N > 0 and ec_mul(N, P, a, p) is INF:
                    return N
        plus = ec_add(plus, step, a, p)
        minus = ec_add(minus, neg_step, a, p)
    raise RuntimeError("no annihilator in the Hasse interval")


def point_order_from_multiple(P, a, p, multiple: int) -> int:
    order = multiple
    for fac in _factor_complete(multiple):
        while order % fac == 0 and ec_mul(order // fac, P, a, p) is INF:
            order //= fac
    return order


def mestre_order(a, b, p, rng: Rng) -> int:
    if p < 64:
        return brute_order(a, b, p)
    half = isqrt(4 * p) + 2
    acc = 1
    for attempt in range(24):
        P = random_point_prime(a, b, p, rng, attempt + 3)
        if P[1] % p == 0:
            continue
        multiple = hasse_annihilator(P, a, p)
        k = point_order_from_multiple(P, a, p, multiple)
        acc = math.lcm(acc, k)
        if acc > 2 * half:
            lo = p + 1 - half
            hi = p + 1 + half
            start = ((lo + acc - 1) // acc) * acc
            hit = None
            x = start
            while x <= hi:
                if hit is not None:
                    hit = None
                    break
                hit = x
                x += acc
            if hit is not None:
                return hit
    raise RuntimeError("Mestre failed to pin the order")


def cm_representation(D: int, bits: int, v_multiple: int, seed: int):
    """Return (p, t, v) with 4p = t^2 - D v^2, v divisible by v_multiple, p prime."""
    if D >= 0 or bits < 8:
        raise ValueError((D, bits))
    abs_d = -D
    # 2^{bits+1} <= t^2 + |D| v^2 < 2^{bits+2}
    def v_bounds():
        vmax = isqrt((1 << (bits + 2)) // abs_d)
        vmin = isqrt((1 << (bits + 1)) // abs_d)
        return max(vmin, 1), max(vmax, 1)

    vmin, vmax = v_bounds()
    if vmax < v_multiple:
        raise RuntimeError(f"bit length {bits} cannot fit conductor step {v_multiple}")
    v = v_multiple * max(1, (vmin + v_multiple - 1) // v_multiple)
    checked = 0
    while v <= vmax and checked < 20000:
        base = abs_d * v * v
        lo = 1 << (bits + 1)
        hi = (1 << (bits + 2)) - 1
        if base > hi:
            break
        min_t2 = max(0, lo - base)
        max_t2 = hi - base
        t = isqrt(min_t2)
        if t * t < min_t2:
            t += 1
        # Same parity as v when D ≡ 1 (mod 4); t even when 4 | D.
        if D % 4 == 1:
            if (t - v) % 2:
                t += 1
            step = 2
        else:
            if t % 2:
                t += 1
            step = 2
        for _ in range(64):
            if t * t > max_t2:
                break
            num = t * t + base
            if num % 4 == 0:
                p = num // 4
                if p.bit_length() == bits and is_probable_prime(p):
                    return p, t, v
            t += step
        v += v_multiple
        checked += 1
    raise RuntimeError(f"CM search failed for D={D} bits={bits} step={v_multiple}")


def j0_candidates(t: int, v: int, p: int) -> list[int]:
    """The six possible orders of a j = 0 curve with 4p = t^2 + 3 v^2."""
    raw = [
        p + 1 - t,
        p + 1 + t,
        p + 1 - (t + 3 * v) // 2,
        p + 1 + (t + 3 * v) // 2,
        p + 1 - (t - 3 * v) // 2,
        p + 1 + (t - 3 * v) // 2,
    ]
    out = []
    for n in raw:
        if n > 1 and n not in out:
            out.append(n)
    return out


def match_order(candidates, points, a, p) -> int:
    good = []
    for n in candidates:
        if all(ec_mul(n, P, a, p) is INF for P in points):
            good.append(n)
    if len(good) != 1:
        raise RuntimeError(f"order match got {good} from {candidates}")
    return good[0]


def nonsingular(a, b, p) -> bool:
    return (4 * pow(a, 3, p) + 27 * b * b) % p != 0


def trace_of(order: int, p: int) -> int:
    return p + 1 - order


def fundamental_split(delta: int) -> tuple[int, int]:
    """Write delta = f^2 * D with D a discriminant (0 or 1 mod 4).

    Odd square factors are removed completely. Factors of 4 are removed only
    while the cofactor stays a discriminant, so -4 stays fundamental instead
    of collapsing to -1.
    """
    if delta >= 0:
        raise ValueError(delta)
    n = -delta
    f = 1
    for p in PRIMES:
        if p == 2:
            continue
        if p * p > n:
            break
        while n % (p * p) == 0:
            n //= p * p
            f *= p
    root = isqrt(n)
    if root * root == n and root > 1:
        # May include a power of 2; the loop below restores the 2-adic condition.
        f *= root
        n = 1
    while n % 4 == 0:
        trial = -(n // 4)
        if trial % 4 in (0, 1):
            n //= 4
            f *= 2
        else:
            break
    D = -n
    # Collapsing a pure square can leave -1. The fundamental discriminant of
    # Q(i) is -4, so put factors of 4 back until the cofactor is a discriminant.
    while D % 4 not in (0, 1):
        if f % 2:
            raise RuntimeError(f"non-discriminant {D} from delta {delta}")
        f //= 2
        D *= 4
    return f, D


def volcano_records(trace: int, p: int) -> list[dict]:
    delta = trace * trace - 4 * p
    f, D = fundamental_split(delta)
    records = []
    for ell in (2, 3, 5, 7, 11, 13):
        h = valuation(f, ell)
        if h >= 1 and ell != p:
            records.append(
                {
                    "prime": ell,
                    "height": h,
                    "conductor": hx(f),
                    "fundamental_discriminant": D,
                    "level": "crater" if CLASS_NUMBER_ONE.get(D) is not None else "cm-order",
                }
            )
    return records


# ---------------------------------------------------------------------------
# Hilbert class polynomials via the q-expansion, for small discriminants.
# ---------------------------------------------------------------------------

def _atan(x: Decimal) -> Decimal:
    # Taylor for |x| < 1. Machin's arguments are 1/5 and 1/239.
    total = Decimal(0)
    power = x
    sign = Decimal(1)
    n = 1
    xx = x * x
    while True:
        term = sign * power / Decimal(n)
        nxt = total + term
        if nxt == total:
            return total
        total = nxt
        power *= xx
        n += 2
        sign = -sign


def _pi() -> Decimal:
    # Machin: π = 16 atan(1/5) - 4 atan(1/239).
    extra = getcontext().prec
    getcontext().prec = extra + 15
    pi = 16 * _atan(Decimal(1) / Decimal(5)) - 4 * _atan(Decimal(1) / Decimal(239))
    getcontext().prec = extra
    return +pi


def _cos_sin(theta: Decimal) -> tuple[Decimal, Decimal]:
    pi = _pi()
    two_pi = 2 * pi
    turns = (theta / two_pi).to_integral_value(rounding=ROUND_HALF_EVEN)
    # Bring the angle near 0 without depending on Decimal modulo.
    theta = theta - turns * two_pi
    if theta > pi:
        theta -= two_pi
    elif theta < -pi:
        theta += two_pi
    cos = Decimal(1)
    sin = theta
    c_term = Decimal(1)
    s_term = theta
    for k in range(1, 90):
        c_term *= -theta * theta / (Decimal(2 * k - 1) * Decimal(2 * k))
        cos += c_term
        s_term *= -theta * theta / (Decimal(2 * k) * Decimal(2 * k + 1))
        sin += s_term
        if c_term == 0 and s_term == 0:
            break
    return cos, sin


class _C:
    def __init__(self, re, im=0):
        self.re = Decimal(re)
        self.im = Decimal(im)

    def __add__(self, o):
        return _C(self.re + o.re, self.im + o.im)

    def __sub__(self, o):
        return _C(self.re - o.re, self.im - o.im)

    def __mul__(self, o):
        if isinstance(o, _C):
            return _C(self.re * o.re - self.im * o.im, self.re * o.im + self.im * o.re)
        return _C(self.re * o, self.im * o)

    def __truediv__(self, o):
        if not isinstance(o, _C):
            return _C(self.re / o, self.im / o)
        den = o.re * o.re + o.im * o.im
        return _C((self.re * o.re + self.im * o.im) / den, (self.im * o.re - self.re * o.im) / den)

    def __pow__(self, n: int):
        r = _C(1, 0)
        b = self
        while n:
            if n & 1:
                r = r * b
            b = b * b
            n >>= 1
        return r


def reduced_forms(D: int) -> list[tuple[int, int, int]]:
    forms = []
    bmax = isqrt(-D)
    for b in range(-bmax, bmax + 1):
        if (b * b - D) % 4:
            continue
        ac = (b * b - D) // 4
        a = 1
        while a * a <= ac:
            if ac % a == 0:
                c = ac // a
                if abs(b) <= a <= c and (b >= 0 or (abs(b) != a and a != c)):
                    forms.append((a, b, c))
            a += 1
    return forms


def hilbert_class_polynomial(D: int) -> list[int]:
    """Monic Hilbert class polynomial, coefficients low-degree first."""
    if D in CLASS_NUMBER_ONE:
        return [-CLASS_NUMBER_ONE[D], 1]
    getcontext().prec = 120
    pi = _pi()
    forms = reduced_forms(D)
    if not forms:
        raise RuntimeError(f"no forms for {D}")
    js = []
    for a, b, c in forms:
        y = Decimal(-D).sqrt() / (2 * a)
        x = Decimal(-b) / (2 * a)
        mag = (-2 * pi * y).exp()
        co, si = _cos_sin(2 * pi * x)
        q = _C(mag * co, mag * si)
        e4 = _C(1, 0)
        qn = _C(1, 0)
        # σ_3(n) on the fly is fine for n <= 40.
        for n in range(1, 41):
            qn = qn * q
            sig = sum(d**3 for d in range(1, n + 1) if n % d == 0)
            e4 = e4 + qn * (240 * sig)
        prod = _C(1, 0)
        qn = q
        for n in range(1, 41):
            prod = prod * ((_C(1, 0) - qn) ** 24)
            qn = qn * q
        delta = q * prod
        # Δ = q ∏(1-q^n)^24 already equals (E4^3 - E6^2)/1728, so j = E4^3 / Δ.
        jv = (e4**3) / delta
        if abs(jv.im) > Decimal("1e-20"):
            raise RuntimeError(f"j not real for {D}: {jv.im}")
        js.append(jv.re)
    poly = [Decimal(1)]
    for jv in js:
        nxt = [Decimal(0)] * (len(poly) + 1)
        for i, coeff in enumerate(poly):
            nxt[i] += coeff * (-jv)
            nxt[i + 1] += coeff
        poly = nxt
    ints = []
    for coeff in poly:
        rounded = coeff.to_integral_value(rounding=ROUND_HALF_EVEN)
        if abs(coeff - rounded) > Decimal("1e-6"):
            raise RuntimeError(f"class polynomial coefficient not integral for {D}")
        ints.append(int(rounded))
    return ints


CLASS_POLY_CACHE: dict[int, list[int]] = {}


def class_poly(D: int) -> list[int]:
    if D not in CLASS_POLY_CACHE:
        CLASS_POLY_CACHE[D] = hilbert_class_polynomial(D)
    return CLASS_POLY_CACHE[D]


def poly_roots_mod(coeffs: list[int], p: int) -> list[int]:
    """Roots of a low-degree polynomial over F_p. coeffs low-degree first."""
    deg = len(coeffs) - 1
    while deg > 0 and coeffs[deg] % p == 0:
        deg -= 1
    coeffs = [c % p for c in coeffs[: deg + 1]]
    if deg <= 0:
        return []
    if deg == 1:
        return [(-coeffs[0] * modinv(coeffs[1], p)) % p]
    if deg == 2:
        a, b, c = coeffs
        if a != 1:
            inv = modinv(c, p)
            a, b = a * inv % p, b * inv % p
            c = 1
        # c x^2 + b x + a, with c = 1: x^2 + b x + a
        disc = (b * b - 4 * c * a) % p
        s = tonelli(disc, p)
        if s is None:
            return []
        inv2 = modinv(2 * c, p)
        return [((-b + s) * inv2) % p, ((-b - s) * inv2) % p]
    # Degree <= 4: split via gcd(x^p - x, f) then Cantor on the separable part.
    return _roots_by_splitting(coeffs, p)


def _poly_trim(f):
    while len(f) > 1 and f[-1] == 0:
        f.pop()
    return f


def _poly_mod_mul(f, g, mod, p):
    r = [0] * (len(f) + len(g) - 1)
    for i, a in enumerate(f):
        if a == 0:
            continue
        for j, b in enumerate(g):
            if b:
                r[i + j] = (r[i + j] + a * b) % p
    return _poly_mod(_poly_trim(r), mod, p)


def _poly_mod(f, mod, p):
    f = f[:]
    md = len(mod) - 1
    inv_lead = modinv(mod[-1], p)
    while len(f) - 1 >= md:
        coef = f[-1] * inv_lead % p
        shift = len(f) - 1 - md
        for i, c in enumerate(mod):
            f[shift + i] = (f[shift + i] - coef * c) % p
        f.pop()
        _poly_trim(f)
    return f or [0]


def _poly_gcd(f, g, p):
    f, g = _poly_trim(f[:]), _poly_trim(g[:])
    while g != [0]:
        f, g = g, _poly_mod(f, g, p)
        g = _poly_trim(g)
    inv = modinv(f[-1], p)
    return [(c * inv) % p for c in f]


def _poly_powmod(base, exp, mod, p):
    r = [1]
    b = _poly_mod(base, mod, p)
    while exp:
        if exp & 1:
            r = _poly_mod_mul(r, b, mod, p)
        b = _poly_mod_mul(b, b, mod, p)
        exp >>= 1
    return r


def _roots_by_splitting(coeffs, p) -> list[int]:
    mod = coeffs[:]
    # Distinct linear factors are gcd(x^p - x, f). x^p is reduced modulo f, then x is subtracted.
    xp = _poly_powmod([0, 1], p, mod, p)
    if len(xp) < 2:
        xp += [0] * (2 - len(xp))
    xp[1] = (xp[1] - 1) % p
    g = _poly_gcd(mod, xp, p)
    if len(g) <= 1:
        return []
    return _split_linear(g, p, Rng(p + len(coeffs) + coeffs[0]))


def _split_linear(f, p, rng: Rng) -> list[int]:
    f = _poly_trim(f[:])
    if len(f) == 2:
        return [(-f[0] * modinv(f[1], p)) % p]
    if len(f) < 2:
        return []
    for _ in range(40):
        a = rng.below(p)
        # gcd( (x+a)^{(p-1)/2} - 1 , f )
        h = _poly_powmod([a, 1], (p - 1) // 2, f, p)
        h[0] = (h[0] - 1) % p
        g = _poly_gcd(f, h, p)
        if 1 < len(g) < len(f):
            return _split_linear(g, p, rng) + _split_linear(_poly_quo(f, g, p), p, rng)
    raise RuntimeError("failed to split polynomial")


def _poly_quo(f, g, p):
    f, g = f[:], g[:]
    inv = modinv(g[-1], p)
    q = [0] * (len(f) - len(g) + 1)
    while len(f) >= len(g) and f != [0]:
        coef = f[-1] * inv % p
        shift = len(f) - len(g)
        q[shift] = coef
        for i, c in enumerate(g):
            f[shift + i] = (f[shift + i] - coef * c) % p
        _poly_trim(f)
    return _poly_trim(q) or [0]


def phi_neighbors(j: int, ell: int, p: int) -> list[int]:
    terms = PHI[ell]
    deg = ell + 1
    coeffs = [0] * (deg + 1)
    jj = j % p
    for (i, k), c in terms.items():
        coeffs[k] = (coeffs[k] + c * pow(jj, i, p)) % p
    roots = []
    for r in poly_roots_mod(coeffs, p):
        if r != jj and r not in roots:
            roots.append(r)
    return roots


# ---------------------------------------------------------------------------
# Binary fields and char-2 curves.
# ---------------------------------------------------------------------------

def ben_or_binary(terms_with_degree: list[int]) -> bool:
    m = max(terms_with_degree)
    mod = 0
    for t in terms_with_degree:
        mod |= 1 << t
    x = 1 << 1  # the element x

    def frob(e):
        # Square and reduce: sum a_i x^{2i}
        sq = 0
        bit = 0
        while e:
            if e & 1:
                sq |= 1 << (2 * bit)
            e >>= 1
            bit += 1
        return reduce_bin(sq, mod, m)

    # x^{2^m} ≡ x, and gcd(x^{2^{m/r}} - x, mod) = 1 for prime r | m.
    e = x
    powers = {0: x}
    r = 1
    factors = []
    mm = m
    for p in PRIMES:
        if p * p > mm:
            break
        if mm % p == 0:
            factors.append(p)
            while mm % p == 0:
                mm //= p
    if mm > 1:
        factors.append(mm)
    need = {m // p for p in factors}
    need.add(m)
    for step in range(1, m + 1):
        e = frob(e)
        if step in need:
            powers[step] = e
    if powers[m] != x:
        return False
    for step in need:
        if step == m:
            continue
        g = bin_gcd(powers[step] ^ x, mod)
        if g != 1:
            return False
    return True


def reduce_bin(a: int, mod: int, m: int) -> int:
    while a.bit_length() > m:
        shift = a.bit_length() - 1 - m
        a ^= mod << shift
    return a


def bin_gcd(a: int, b: int) -> int:
    while b:
        if a.bit_length() < b.bit_length():
            a, b = b, a
        a ^= b << (a.bit_length() - b.bit_length())
    return a


def find_binary_modulus(m: int) -> list[int]:
    # Trinomials first. Degrees without a trinomial fall through to a
    # deterministic pentanomial search (about 1/m of them are irreducible).
    if m == 1:
        return [1, 0]
    for k in range(1, m):
        if ben_or_binary([m, k, 0]):
            return [m, k, 0]
    rng = Rng(0xB10A + m)
    for _ in range(max(5000, 8 * m)):
        i, j, k = sorted(rng.below(m - 1) + 1 for _ in range(3))
        if len({i, j, k}) < 3:
            continue
        if ben_or_binary([m, k, j, i, 0]):
            return [m, k, j, i, 0]
    raise RuntimeError(f"no irreducible for F_2^{m}")


BIN_MOD: dict[int, int] = {}


def bin_mod_int(m: int) -> int:
    if m not in BIN_MOD:
        terms = find_binary_modulus(m)
        mod = 0
        for t in terms:
            mod |= 1 << t
        BIN_MOD[m] = mod
    return BIN_MOD[m]


def bin_mul(a: int, b: int, mod: int, m: int) -> int:
    r = 0
    while b:
        if b & 1:
            r ^= a
        b >>= 1
        a <<= 1
    return reduce_bin(r, mod, m)


def bin_inv(a: int, mod: int, m: int) -> int:
    if a == 0:
        raise ZeroDivisionError
    # a^{2^m - 2}
    return bin_pow(a, (1 << m) - 2, mod, m)


def bin_pow(a: int, e: int, mod: int, m: int) -> int:
    r = 1
    while e:
        if e & 1:
            r = bin_mul(r, a, mod, m)
        a = bin_mul(a, a, mod, m)
        e >>= 1
    return r


def bin_trace(a: int, mod: int, m: int) -> int:
    s = 0
    e = a
    for _ in range(m):
        s ^= e
        e = bin_mul(e, e, mod, m)
    return s & 1


def bin_half_trace(a: int, mod: int, m: int) -> int:
    # m odd: H(a) = sum_{i=0}^{(m-1)/2} a^{4^i}
    s = 0
    e = a
    for _ in range((m + 1) // 2):
        s ^= e
        e = bin_mul(e, e, mod, m)
        e = bin_mul(e, e, mod, m)
    return s


def solve_z2_plus_z(c: int, m: int) -> int | None:
    """Solve z^2 + z = c in F_2^m. Returns None when Tr(c) = 1."""
    mod = bin_mod_int(m)
    if bin_trace(c, mod, m) != 0:
        return None
    if m % 2 == 1:
        return bin_half_trace(c, mod, m)
    cols = []
    for i in range(m):
        basis = 1 << i
        cols.append(bin_mul(basis, basis, mod, m) ^ basis)
    rows = [0] * m
    rhs = [(c >> r) & 1 for r in range(m)]
    for r in range(m):
        row = 0
        for col, bits in enumerate(cols):
            if (bits >> r) & 1:
                row |= 1 << col
        rows[r] = row
    where = [-1] * m
    for col in range(m):
        piv = next((r for r in range(m) if where[r] < 0 and (rows[r] >> col) & 1), None)
        if piv is None:
            continue
        where[piv] = col
        for r in range(m):
            if r != piv and (rows[r] >> col) & 1:
                rows[r] ^= rows[piv]
                rhs[r] ^= rhs[piv]
    sol = 0
    for r in range(m):
        if where[r] >= 0:
            if rhs[r]:
                sol |= 1 << where[r]
        elif rhs[r]:
            return None
    return sol


def bin_curve_rhs_c(x, a, b, mod, m):
    # For y^2 + x y = x^3 + a x^2 + b, set y = x z, z^2 + z = x + a + b x^{-2}
    xinv = bin_inv(x, mod, m)
    return x ^ a ^ bin_mul(b, bin_mul(xinv, xinv, mod, m), mod, m)


def find_binary_point(a, b, m, label: str):
    mod = bin_mod_int(m)
    for i in range(1, 100000):
        x = sha_int(label, i, m) or 1
        x &= (1 << m) - 1
        if x == 0:
            continue
        c = bin_curve_rhs_c(x, a, b, mod, m)
        z = solve_z2_plus_z(c, m)
        if z is not None:
            y = bin_mul(x, z, mod, m)
            return x, y
    raise RuntimeError("no binary point")


def bin_on_curve(P, a, b, m) -> bool:
    if P is INF:
        return True
    x, y = P
    mod = bin_mod_int(m)
    left = bin_mul(y, y, mod, m) ^ bin_mul(x, y, mod, m)
    right = bin_mul(bin_mul(x, x, mod, m), x, mod, m) ^ bin_mul(a, bin_mul(x, x, mod, m), mod, m) ^ b
    return left == right


def bin_add(P, Q, a, m):
    mod = bin_mod_int(m)
    if P is INF:
        return Q
    if Q is INF:
        return P
    x1, y1 = P
    x2, y2 = Q
    if x1 == x2:
        if y1 == y2:
            if x1 == 0:
                return INF
            xinv = bin_inv(x1, mod, m)
            lam = x1 ^ bin_mul(y1, xinv, mod, m)
            x3 = bin_mul(lam, lam, mod, m) ^ lam ^ a
            y3 = bin_mul(x1, x1, mod, m) ^ bin_mul(lam ^ 1, x3, mod, m)
            return x3, y3
        return INF
    lam = bin_mul(y1 ^ y2, bin_inv(x1 ^ x2, mod, m), mod, m)
    x3 = bin_mul(lam, lam, mod, m) ^ lam ^ x1 ^ x2 ^ a
    y3 = bin_mul(lam, x1 ^ x3, mod, m) ^ x3 ^ y1
    return x3, y3


def bin_neg(P):
    if P is INF:
        return INF
    return P[0], P[1] ^ P[0]


def _ld_double(P, a, mod, m):
    """Double in López–Dahab coordinates (X : Y : Z) = (X/Z, Y/Z²)."""
    if P is None:
        return None
    X, Y, Z = P
    if Z == 0 or X == 0:
        return None
    X2 = bin_mul(X, X, mod, m)
    L = X2 ^ Y
    D = bin_mul(X, Z, mod, m)
    D2 = bin_mul(D, D, mod, m)
    X3 = bin_mul(L, L, mod, m) ^ bin_mul(L, D, mod, m) ^ bin_mul(a, D2, mod, m)
    X4 = bin_mul(X2, X2, mod, m)
    Y3 = bin_mul(D2, X4 ^ X3, mod, m) ^ bin_mul(bin_mul(D, X3, mod, m), L, mod, m)
    return X3, Y3, D2


def _ld_add(P, Q, a, mod, m):
    """Add two López–Dahab points. None is the identity."""
    if P is None:
        return Q
    if Q is None:
        return P
    X1, Y1, Z1 = P
    X2, Y2, Z2 = Q
    if Z1 == 0:
        return Q
    if Z2 == 0:
        return P
    Z1_2 = bin_mul(Z1, Z1, mod, m)
    Z2_2 = bin_mul(Z2, Z2, mod, m)
    B = bin_mul(X1, Z2, mod, m) ^ bin_mul(X2, Z1, mod, m)
    A = bin_mul(Y1, Z2_2, mod, m) ^ bin_mul(Y2, Z1_2, mod, m)
    if B == 0:
        if A == 0:
            return _ld_double(P, a, mod, m)
        return None
    E = bin_mul(Z1, Z2, mod, m)
    D = bin_mul(E, B, mod, m)
    D2 = bin_mul(D, D, mod, m)
    B2 = bin_mul(B, B, mod, m)
    B3 = bin_mul(B2, B, mod, m)
    X3 = (
        bin_mul(A, A, mod, m)
        ^ bin_mul(A, D, mod, m)
        ^ bin_mul(E, B3, mod, m)
        ^ bin_mul(a, D2, mod, m)
    )
    Z2_4 = bin_mul(Z2_2, Z2_2, mod, m)
    B4 = bin_mul(B2, B2, mod, m)
    Y3 = (
        bin_mul(bin_mul(bin_mul(bin_mul(A, X1, mod, m), Z2, mod, m), B, mod, m), D2, mod, m)
        ^ bin_mul(X3, D2, mod, m)
        ^ bin_mul(bin_mul(A, X3, mod, m), D, mod, m)
        ^ bin_mul(bin_mul(bin_mul(Y1, Z1_2, mod, m), Z2_4, mod, m), B4, mod, m)
    )
    return X3, Y3, D2


def _ld_affine(P, mod, m):
    if P is None or P[2] == 0:
        return INF
    X, Y, Z = P
    zinv = bin_inv(Z, mod, m)
    x = bin_mul(X, zinv, mod, m)
    y = bin_mul(Y, bin_mul(zinv, zinv, mod, m), mod, m)
    return x, y


def bin_mul_point(k, P, a, b, m):
    """Scalar multiplication on y² + xy = x³ + a x² + b.

    López–Dahab doubling and addition only read `a`; `b` is carried so every
    caller names the curve it is multiplying on.
    """
    del b
    if k < 0:
        return bin_mul_point(-k, bin_neg(P), a, 0, m)
    if k == 0 or P is INF:
        return INF
    mod = bin_mod_int(m)
    R = None
    Q = (P[0], P[1], 1)
    while k:
        if k & 1:
            R = _ld_add(R, Q, a, mod, m)
        Q = _ld_double(Q, a, mod, m)
        k >>= 1
    return _ld_affine(R, mod, m)


def koblitz_trace(a_bit: int, m: int) -> int:
    # Same recurrence as suite/src/bin/ic/params.rs: t_0 = 2, t_1 = μ, μ = -1 if a=0 else +1.
    mu = -1 if a_bit == 0 else 1
    prev, cur = 2, mu
    for _ in range(1, m):
        prev, cur = cur, mu * cur - 2 * prev
    return cur


def koblitz_order(a_bit: int, m: int) -> int:
    return (1 << m) + 1 - koblitz_trace(a_bit, m)


def lift_trace(t: int, q: int, k: int) -> int:
    prev, cur = 2, t
    if k == 1:
        return t
    for _ in range(2, k + 1):
        prev, cur = cur, t * cur - q * prev
    return cur


def order_from_trace(q: int, t: int, k: int = 1) -> int:
    return pow(q, k) + 1 - lift_trace(t, q, k)


# ---------------------------------------------------------------------------
# Generic extension fields F_p[x]/(modulus), p odd.
# ---------------------------------------------------------------------------

class Ext:
    def __init__(self, p: int, mod: list[int]):
        self.p = p
        self.mod = [c % p for c in mod]
        self.n = len(self.mod) - 1
        self.q = pow(p, self.n)
        if self.mod[-1] % p != 1:
            raise ValueError("modulus must be monic")

    def norm(self, a):
        a = [c % self.p for c in a]
        if len(a) < self.n:
            a = a + [0] * (self.n - len(a))
        return tuple(a[: self.n])

    def add(self, a, b):
        return self.norm([x + y for x, y in zip(self.norm(a), self.norm(b))])

    def sub(self, a, b):
        return self.norm([x - y for x, y in zip(self.norm(a), self.norm(b))])

    def neg(self, a):
        return self.norm([-c for c in a])

    def mul(self, a, b):
        a, b = self.norm(a), self.norm(b)
        r = [0] * (2 * self.n - 1)
        for i, ai in enumerate(a):
            if ai == 0:
                continue
            for j, bj in enumerate(b):
                if bj:
                    r[i + j] = (r[i + j] + ai * bj) % self.p
        return self.reduce(r)

    def reduce(self, r):
        p, n, mod = self.p, self.n, self.mod
        r = [c % p for c in r]
        for d in range(len(r) - 1, n - 1, -1):
            coef = r[d]
            if coef == 0:
                continue
            # x^n = -mod[0] - ... since monic
            shift = d - n
            for i in range(n):
                r[shift + i] = (r[shift + i] - coef * mod[i]) % p
            r[d] = 0
        return tuple(r[:n])

    def pow(self, a, e):
        r = self.one()
        b = self.norm(a)
        while e:
            if e & 1:
                r = self.mul(r, b)
            b = self.mul(b, b)
            e >>= 1
        return r

    def one(self):
        return self.norm([1])

    def zero(self):
        return self.norm([0])

    def const(self, c):
        return self.norm([c])

    def eq(self, a, b):
        return self.norm(a) == self.norm(b)

    def is_zero(self, a):
        return all(c % self.p == 0 for c in a)

    def inv(self, a):
        # a^{q-2}
        return self.pow(a, self.q - 2)

    def is_square(self, a) -> bool:
        if self.is_zero(a):
            return True
        leg = self.pow(a, (self.q - 1) // 2)
        return leg == self.one()

    def sqrt(self, a):
        if self.is_zero(a):
            return self.zero()
        if not self.is_square(a):
            return None
        if self.q % 4 == 3:
            return self.pow(a, (self.q + 1) // 4)
        return self._cipolla(a)

    def _cipolla(self, a):
        rng = Rng(int.from_bytes(hashlib.sha256(repr(a).encode()).digest()[:8], "big") or 1)
        t = None
        for _ in range(1000):
            cand = self.norm(rng.element_digits(self.p, self.n))
            disc = self.sub(self.mul(cand, cand), a)
            if not self.is_zero(disc) and not self.is_square(disc):
                t = cand
                break
        if t is None:
            raise RuntimeError("Cipolla failed")
        # (t + sqrt(disc))^{(q+1)/2} in F[x]/(x^2 - disc)
        w = self.sub(self.mul(t, t), a)  # disc

        def mul2(p1, p2):
            # (a + b ω)(c + d ω), ω^2 = w
            a1, b1 = p1
            a2, b2 = p2
            return (
                self.add(self.mul(a1, a2), self.mul(self.mul(b1, b2), w)),
                self.add(self.mul(a1, b2), self.mul(b1, a2)),
            )

        r = (self.one(), self.zero())
        base = (t, self.one())
        e = (self.q + 1) // 2
        while e:
            if e & 1:
                r = mul2(r, base)
            base = mul2(base, base)
            e >>= 1
        if not self.is_zero(r[1]):
            raise RuntimeError("Cipolla remainder")
        return r[0]


def _prime_factors(n: int) -> list[int]:
    factors = []
    mm = n
    for pr in PRIMES:
        if pr * pr > mm:
            break
        if mm % pr == 0:
            factors.append(pr)
            while mm % pr == 0:
                mm //= pr
    if mm > 1:
        factors.append(mm)
    return factors


def _sparse_irreducible(p: int, n: int, low: list[int]) -> bool:
    """Ben-Or test for the monic polynomial X^n + low[0] + ... + low[n-1] X^{n-1}."""
    terms = [(i, low[i] % p) for i in range(n) if low[i] % p]

    def frob(e: list[int]) -> list[int]:
        lifted = [0] * (p * (n - 1) + 1)
        for i, coef in enumerate(e):
            if coef:
                lifted[i * p] = coef  # a |-> a^p is the identity on F_p
        for d in range(len(lifted) - 1, n - 1, -1):
            coef = lifted[d]
            if coef == 0:
                continue
            shift = d - n
            for i, ci in terms:
                lifted[shift + i] = (lifted[shift + i] - coef * ci) % p
            lifted[d] = 0
        return lifted[:n]

    x = [0, 1] + [0] * (n - 2)
    need = {n // pr for pr in _prime_factors(n)}
    need.add(n)
    powers = {}
    e = x
    for step in range(1, n + 1):
        e = frob(e)
        if step in need:
            powers[step] = e
    if powers[n] != x:
        return False
    mod = low[:] + [1]
    for step, value in powers.items():
        if step == n:
            continue
        diff = [(value[i] - x[i]) % p for i in range(n)]
        if len(_poly_gcd(mod, diff, p)) != 1:
            return False
    return True


def _trinomial_irreducible(p: int, n: int, k: int | None, ck: int, c0: int) -> bool:
    low = [0] * n
    low[0] = c0
    if k is not None:
        low[k] = ck
    return _sparse_irreducible(p, n, low)


def ext_irreducible(p: int, n: int, seed: int) -> list[int]:
    if n == 1:
        return [0, 1]
    if p <= 5 and n >= 12:
        rng = Rng(seed)
        for c0 in range(1, p):
            if _trinomial_irreducible(p, n, None, 1, c0):
                mod = [0] * n + [1]
                mod[0] = c0
                return mod
        for terms in (2, 3, 4):
            trials = max(3000, 8 * n)
            for _ in range(trials):
                low = [0] * n
                low[0] = 1 + rng.below(p - 1)
                for _t in range(terms - 1):
                    k = 1 + rng.below(n - 1)
                    low[k] = 1 + rng.below(p - 1)
                if _sparse_irreducible(p, n, low):
                    return low + [1]
        raise RuntimeError(f"no sparse irreducible of degree {n} over F_{p}")
    rng = Rng(seed)
    for attempt in range(5000):
        coeffs = [rng.below(p) for _ in range(n)]
        if coeffs[0] == 0:
            coeffs[0] = 1
        mod = coeffs + [1]
        if ext_is_irreducible(p, mod):
            return mod
        if attempt == 0 and n == 2:
            # x^2 - d, d nonsquare
            d = 2
            while legendre(d, p) != -1:
                d += 1
            return [(-d) % p, 0, 1]
    raise RuntimeError(f"no irreducible of degree {n} over F_{p}")


def ext_is_irreducible(p: int, mod: list[int]) -> bool:
    n = len(mod) - 1
    field = Ext(p, mod)
    # Repeated Frobenius on x, but generic pow is fine for small n.
    # Ben-Or: x^{p^n} ≡ x and gcd(x^{p^{n/r}} - x, f) = 1.
    x = field.norm([0, 1] if n > 1 else [0])
    factors = []
    mm = n
    for pr in PRIMES:
        if pr * pr > mm:
            break
        if mm % pr == 0:
            factors.append(pr)
            while mm % pr == 0:
                mm //= pr
    if mm > 1:
        factors.append(mm)

    def x_pow_q(steps):
        # x^{p^steps} via repeated Frobenius of the element x, using generic pow(p).
        e = x
        for _ in range(steps):
            e = field.pow(e, p)
        return e

    if x_pow_q(n) != x:
        return False
    for pr in factors:
        e = x_pow_q(n // pr)
        # gcd(e - x, mod). e - x as polynomial.
        diff = list(field.sub(e, x))
        g = _poly_gcd(mod, diff + [0] * (n - len(diff)) if False else diff, p)
        # diff has length n; _poly_gcd expects a list
        if g != [1] and g != [1 % p]:
            # constant gcd means 1 after monic. g == [1].
            if len(g) != 1:
                return False
    return True


def count_ext_order_by_enum(field: Ext, a, b) -> int:
    # Only for tiny fields.
    if field.q > 20000:
        raise RuntimeError("too big to enumerate")
    # Iterate digits in base p.
    n = 1
    digits = [0] * field.n
    while True:
        x = field.norm(digits)
        rhs = field.add(field.mul(field.mul(x, x), x), field.add(field.mul(a, x), b))
        if field.is_zero(rhs):
            n += 1
        elif field.is_square(rhs):
            n += 2
        # increment
        i = 0
        while i < field.n:
            digits[i] += 1
            if digits[i] == field.p:
                digits[i] = 0
                i += 1
            else:
                break
        else:
            break
    return n


def ext_ec_add(field: Ext, P, Q, a):
    if P is INF:
        return Q
    if Q is INF:
        return P
    x1, y1 = P
    x2, y2 = Q
    if field.eq(x1, x2):
        if field.is_zero(field.add(y1, y2)):
            return INF
        lam = field.mul(field.add(field.mul(field.mul(x1, x1), field.const(3)), a), field.inv(field.mul(field.const(2), y1)))
    else:
        lam = field.mul(field.sub(y2, y1), field.inv(field.sub(x2, x1)))
    x3 = field.sub(field.sub(field.mul(lam, lam), x1), x2)
    y3 = field.sub(field.mul(lam, field.sub(x1, x3)), y1)
    return x3, y3


def ext_ec_mul(field: Ext, k, P, a):
    R = INF
    Q = P
    kk = k
    while kk:
        if kk & 1:
            R = ext_ec_add(field, R, Q, a)
        Q = ext_ec_add(field, Q, Q, a)
        kk >>= 1
    return R


def ext_on(field: Ext, P, a, b) -> bool:
    if P is INF:
        return True
    x, y = P
    rhs = field.add(field.mul(field.mul(x, x), x), field.add(field.mul(a, x), b))
    return field.eq(field.mul(y, y), rhs)


def ext_hash_point(field: Ext, a, b, label: str):
    for i in range(100000):
        digits = []
        raw = sha_int(label, i, field.n * field.p.bit_length() + 8)
        for _d in range(field.n):
            digits.append(raw % field.p)
            raw //= field.p
        x = field.norm(digits)
        rhs = field.add(field.mul(field.mul(x, x), x), field.add(field.mul(a, x), b))
        y = field.sqrt(rhs)
        if y is not None:
            return x, y
    raise RuntimeError("no extension point")


def elem_json(e) -> list[str] | str:
    if isinstance(e, tuple):
        return [hx(int(c)) for c in e]
    return hx(int(e))


# ---------------------------------------------------------------------------
# Char 3: y^2 = x^3 + A x^2 + B, and supersingular y^2 = x^3 + x + B.
# ---------------------------------------------------------------------------

def char3_add(field: Ext, P, Q, A, model: str):
    if P is INF:
        return Q
    if Q is INF:
        return P
    x1, y1 = P
    x2, y2 = Q
    if model == "ordinary":
        if field.eq(x1, x2):
            if field.is_zero(field.add(y1, y2)):
                return INF
            # λ = A x / y
            lam = field.mul(field.mul(A, x1), field.inv(y1))
            # x3 = λ^2 - A + x   ( -2 ≡ 1 )
            x3 = field.add(field.sub(field.mul(lam, lam), A), x1)
        else:
            lam = field.mul(field.sub(y2, y1), field.inv(field.sub(x2, x1)))
            x3 = field.sub(field.sub(field.sub(field.mul(lam, lam), A), x1), x2)
        y3 = field.sub(field.mul(lam, field.sub(x1, x3)), y1)
        return x3, y3
    if model == "supersingular":
        # y^2 = x^3 + x + b, λ = (3x^2+1)/(2y) = 1/(2y) = 2/y since 2*2=1 mod 3
        if field.eq(x1, x2):
            if field.is_zero(field.add(y1, y2)):
                return INF
            lam = field.mul(field.const(2), field.inv(y1))
            x3 = field.sub(field.mul(lam, lam), field.mul(field.const(2), x1))
        else:
            lam = field.mul(field.sub(y2, y1), field.inv(field.sub(x2, x1)))
            x3 = field.sub(field.sub(field.mul(lam, lam), x1), x2)
        y3 = field.sub(field.mul(lam, field.sub(x1, x3)), y1)
        return x3, y3
    raise ValueError(model)


def char3_on(field: Ext, P, A, B, model: str) -> bool:
    if P is INF:
        return True
    x, y = P
    cube = field.mul(field.mul(x, x), x)
    if model == "ordinary":
        rhs = field.add(field.add(cube, field.mul(A, field.mul(x, x))), B)
    else:
        rhs = field.add(field.add(cube, x), B)
    return field.eq(field.mul(y, y), rhs)


def char3_mul(field, k, P, A, model):
    R = INF
    Q = P
    while k:
        if k & 1:
            R = char3_add(field, R, Q, A, model)
        Q = char3_add(field, Q, Q, A, model)
        k >>= 1
    return R


def char3_hash_point(field, A, B, model, label):
    for i in range(100000):
        raw = sha_int(label, i, field.n * 4 + 8)
        digits = []
        for _ in range(field.n):
            digits.append(raw % 3)
            raw //= 3
        x = field.norm(digits)
        cube = field.mul(field.mul(x, x), x)
        if model == "ordinary":
            rhs = field.add(field.add(cube, field.mul(A, field.mul(x, x))), B)
        else:
            rhs = field.add(field.add(cube, x), B)
        y = field.sqrt(rhs)
        if y is not None:
            return x, y
    raise RuntimeError("no char3 point")


# ---------------------------------------------------------------------------
# Emitting records
# ---------------------------------------------------------------------------

def split_group(order: int) -> dict:
    h, r, probable = factor_smooth(order)
    if r == 1:
        # Fully smooth: the challenge group is the whole curve, Pohlig–Hellman applies.
        return {
            "cofactor": hx(1),
            "cofactor_int": 1,
            "subgroup_order": hx(order),
            "subgroup_int": order,
            "subgroup_probable_prime": is_probable_prime(order),
            "fully_smooth": True,
        }
    return {
        "cofactor": hx(h),
        "cofactor_int": h,
        "subgroup_order": hx(r),
        "subgroup_int": r,
        "subgroup_probable_prime": probable,
        "fully_smooth": False,
    }


def emit(rec: dict):
    rec["schema_version"] = 1
    CURVES.append(rec)
    print(f"  {rec['id']}  bits={rec['field']['cardinality_bits']}  {rec['tier']}", file=sys.stderr)


def tier_for(subgroup_bits: int, verified_scalar: bool) -> str:
    if verified_scalar and subgroup_bits <= 48:
        return "check"
    return "open"


def prime_record(
    *,
    id: str,
    family: str,
    p: int,
    a: int,
    b: int,
    order: int,
    tags: list[str],
    endomorphism: dict,
    notes: str,
    certificate: str,
    volcanoes: list[dict] | None = None,
    rng_seed: int,
    verify: bool = True,
) -> dict:
    if not nonsingular(a, b, p):
        raise RuntimeError(f"{id} singular")
    parts = split_group(order)
    G = None
    known = None
    target = None
    verification = "cm-or-count"
    if verify:
        P = hash_point_prime(a, b, p, id + ":gen")
        if ec_mul(order, P, a, p) is not INF:
            raise RuntimeError(f"{id} order does not annihilate a point")
        h = parts["cofactor_int"]
        n = parts["subgroup_int"]
        G = ec_mul(h, P, a, p)
        if G is INF:
            # Try another point.
            rng = Rng(rng_seed)
            for _ in range(20):
                P = random_point_prime(a, b, p, rng, 9)
                G = ec_mul(h, P, a, p)
                if G is not INF:
                    break
        if G is INF:
            raise RuntimeError(f"{id} subgroup generator is identity")
        if ec_mul(n, G, a, p) is not INF:
            raise RuntimeError(f"{id} subgroup order failed")
        if parts["subgroup_probable_prime"] and ec_mul(1, G, a, p) is INF:
            raise RuntimeError("zero generator")
        verification = "scalar-annihilation"
        sub_bits = n.bit_length()
        if sub_bits <= 48:
            known = 1 + (rng_seed % (n - 1))
            target = ec_mul(known, G, a, p)
        else:
            T = hash_point_prime(a, b, p, id + ":target")
            target = ec_mul(h, T, a, p)
            if target is INF:
                target = G
    else:
        raise RuntimeError("prime curves are always scalar-checked")
    j = j_invariant(a, b, p)
    field_bits = p.bit_length()
    rec = {
        "id": id,
        "family": family,
        "tier": tier_for(parts["subgroup_int"].bit_length(), True),
        "tags": tags,
        "field": {
            "type": "prime",
            "characteristic": hx(p),
            "degree": 1,
            "degree_kind": "prime-field",
            "cardinality": hx(p),
            "cardinality_bits": field_bits,
            "modulus_prime": True,
        },
        "model": "short-weierstrass",
        "equation": "y^2 = x^3 + a*x + b",
        "a": hx(a),
        "b": hx(b),
        "j": hx(j),
        "trace": trace_of(order, p),
        "group_order": hx(order),
        "cofactor": parts["cofactor"],
        "subgroup_order": parts["subgroup_order"],
        "subgroup_probable_prime": parts["subgroup_probable_prime"],
        "generator": {"x": hx(G[0]), "y": hx(G[1])},
        "target": {"x": hx(target[0]), "y": hx(target[1])},
        "known_log": hx(known) if known is not None else None,
        "endomorphism": endomorphism,
        "volcanoes": volcanoes or [],
        "embedding_degree_bound": embedding_bound(p, parts["subgroup_int"]) if parts["subgroup_probable_prime"] else None,
        "order_certificate": certificate,
        "verification": verification,
        "suggested_solvers": solvers_for(tags, parts),
        "notes": notes,
    }
    if known is not None and ec_mul(known, G, a, p) != target:
        raise RuntimeError("known log mismatch")
    emit(rec)
    return rec


def embedding_bound(p: int, r: int):
    if r <= 1 or not is_probable_prime(r):
        return None
    acc = p % r
    for k in range(1, 25):
        if acc == 1 % r or acc == 1:
            return {"k": k, "exact_if_le_24": True}
        acc = (acc * (p % r)) % r
    return {"k": None, "greater_than": 24}


def solvers_for(tags: list[str], parts: dict) -> list[str]:
    s = ["pollard-rho", "bsgs"]
    if "glv-j0" in tags or "j0" in tags:
        s.append("glv-rho-automorphism-6")
    if "glv-j1728" in tags or "j1728" in tags:
        s.append("glv-rho-automorphism-4")
    if "special-endomorphism" in tags:
        s.append("glv-rho")
    if "koblitz" in tags:
        s.append("frobenius-endomorphism-rho")
        s.append("semaev-index-calculus")
    if "subfield" in tags or "extension" in tags:
        s.append("gaudry-diem-index-calculus")
    if "composite-degree" in tags:
        s.append("weil-descent")
    if "anomalous" in tags:
        s.append("smart-anomalous")
    if "supersingular" in tags or "pairing" in tags:
        s.append("mov-frey-ruck")
    if "volcano" in tags:
        s.append("isogeny-volcano")
    if parts.get("fully_smooth") or "pohlig-hellman" in tags:
        s.append("pohlig-hellman")
    if not parts.get("subgroup_probable_prime", True):
        s.append("pohlig-hellman")
    # Deduplicate, preserve order.
    out = []
    for item in s:
        if item not in out:
            out.append(item)
    return out


def endo_j0(trace: int, v: int) -> dict:
    return {
        "kind": "cm-j0",
        "j": 0,
        "automorphism_group_order": 6,
        "discriminant": -3,
        "cm_generator": {"t": trace, "v": v},
        "description": "y^2 = x^3 + b has Aut of order 6 when p = 1 mod 3. The Galbraith–Lambert–Vanstone endomorphism is (x, y) -> (β x, -y) for β^3 = 1, β ≠ 1.",
    }


def endo_j1728() -> dict:
    return {
        "kind": "cm-j1728",
        "j": 1728,
        "automorphism_group_order": 4,
        "discriminant": -4,
        "description": "y^2 = x^3 + a x has Aut of order 4 when p = 1 mod 4. The endomorphism is (x, y) -> (-x, i y) for i^2 = -1.",
    }


def endo_disc(D: int) -> dict:
    return {
        "kind": "cm",
        "discriminant": D,
        "j": CLASS_NUMBER_ONE.get(D),
        "description": f"Complex multiplication by the order of discriminant {D}. A small discriminant gives a low-degree endomorphism that folds Pollard rho the way GLV does for j = 0 and j = 1728.",
    }


# ---------------------------------------------------------------------------
# Family builders
# ---------------------------------------------------------------------------

def build_j0():
    specs = [
        (16, 1, "fp-j0-b16"),
        (20, 1, "fp-j0-b20"),
        (24, 1, "fp-j0-b24"),
        (32, 1, "fp-j0-b32"),
        (32, 9, "fp-j0-b32-volcano3-h2"),
        (40, 1, "fp-j0-b40"),
        (48, 1, "fp-j0-b48"),
        (48, 27, "fp-j0-b48-volcano3-h3"),
        (61, 1, "fp-j0-b61"),
        (64, 25, "fp-j0-b64-volcano5-h2"),
        (80, 1, "fp-j0-b80"),
        (96, 1, "fp-j0-b96"),
        (128, 1, "fp-j0-b128"),
        (128, 49, "fp-j0-b128-volcano7-h2"),
        (160, 1, "fp-j0-b160"),
        (192, 1, "fp-j0-b192"),
        (256, 1, "fp-j0-b256"),
        (256, 125, "fp-j0-b256-volcano5-h3"),
        (384, 1, "fp-j0-b384"),
        (521, 1, "fp-j0-b521"),
        (768, 1, "fp-j0-b768"),
        (768, 121, "fp-j0-b768-volcano11-h2"),
    ]
    for bits, step, name in specs:
        p, t, v = cm_representation(-3, bits, step, seed=1000 + bits * 17 + step)
        # 4p = t^2 + 3 v^2, both odd.
        cands = j0_candidates(t, v, p)
        # Try several sextic twists of b.
        b = 1
        chosen = None
        for twist_index in range(12):
            bb = (b * pow(twist_index + 1, 1, p)) % p
            if bb == 0:
                continue
            P = hash_point_prime(0, bb, p, name + f":{twist_index}")
            Q = hash_point_prime(0, bb, p, name + f":q{twist_index}")
            try:
                order = match_order(cands, [P, Q], 0, p)
            except RuntimeError:
                continue
            chosen = (bb, order, twist_index)
            break
        if chosen is None:
            raise RuntimeError(f"no j=0 twist for {name}")
        bb, order, twist_index = chosen
        vols = volcano_records(trace_of(order, p), p)
        tags = ["j0", "ordinary", "cm", "glv-j0", "prime-field"]
        if any(vrec["height"] >= 2 for vrec in vols):
            tags.append("volcano")
        if twist_index:
            tags.append("twist")
        prime_record(
            id=name,
            family="prime-j0",
            p=p,
            a=0,
            b=bb,
            order=order,
            tags=tags,
            endomorphism=endo_j0(t, v),
            notes=f"j = 0 twist index {twist_index}. CM generator gives 4p = t^2 + 3 v^2 with t = {t}, v = {v}.",
            certificate="cm-discriminant--3",
            volcanoes=vols,
            rng_seed=5000 + bits + step,
        )


def build_j0_twist_pairs():
    """A second sextic twist at a few sizes, paired with the curves above."""
    for bits, name in ((32, "fp-j0-b32-sextic-twist"), (61, "fp-j0-b61-sextic-twist"), (128, "fp-j0-b128-sextic-twist")):
        p, t, v = cm_representation(-3, bits, 1, seed=1000 + bits * 17 + 1)
        cands = j0_candidates(t, v, p)
        # Skip b that reproduces the first curve's order if we can get a different one.
        found = []
        for twist_index in range(1, 18):
            bb = twist_index % p
            if bb == 0:
                continue
            P = hash_point_prime(0, bb, p, name + f":{twist_index}")
            Q = hash_point_prime(0, bb, p, name + f":q{twist_index}")
            try:
                order = match_order(cands, [P, Q], 0, p)
            except RuntimeError:
                continue
            if order not in [o for _, o in found]:
                found.append((bb, order))
            if len(found) == 1:
                break
        bb, order = found[0]
        vols = volcano_records(trace_of(order, p), p)
        tags = ["j0", "twist", "ordinary", "cm", "glv-j0", "prime-field"]
        prime_record(
            id=name,
            family="prime-j0-twist",
            p=p,
            a=0,
            b=bb,
            order=order,
            tags=tags,
            endomorphism=endo_j0(t, v),
            notes="A different sextic twist of y^2 = x^3 + b on the same field as the untwisted j = 0 search. The six twists realise the six possible traces.",
            certificate="cm-discriminant--3",
            volcanoes=vols,
            rng_seed=8000 + bits,
        )


def build_j1728():
    specs = [20, 32, 48, 61, 96, 128, 192, 256, 384, 521, 768]
    volcano = {48: 9, 128: 25, 256: 49, 768: 121}
    for bits in specs:
        step = volcano.get(bits, 1)
        # p = x^2 + y^2, y divisible by step, p ≡ 1 (mod 4).
        # Use D = -4: 4p = t^2 + 4 y^2 with t even, so p = (t/2)^2 + y^2.
        p, t, v = cm_representation(-4, bits, step, seed=2000 + bits * 13 + step)
        # Candidate traces ±t, and also the swapped representation is already t.
        # For j=1728 the four orders are p+1±t and, writing 4p = t^2 + 4 v^2,
        # p+1±2v if t is the trace candidate. Identify by testing.
        cands = []
        for tr in (t, -t, 2 * v, -2 * v):
            n = p + 1 - tr
            if n > 1 and n not in cands:
                cands.append(n)
        chosen = None
        for a_coef in range(1, 24):
            if legendre(a_coef, p) == 0:
                continue
            P = hash_point_prime(a_coef, 0, p, f"j1728-{bits}-{a_coef}")
            Q = hash_point_prime(a_coef, 0, p, f"j1728q-{bits}-{a_coef}")
            try:
                order = match_order(cands, [P, Q], a_coef, p)
            except RuntimeError:
                continue
            chosen = (a_coef, order)
            break
        if chosen is None:
            raise RuntimeError(f"j1728 failed at {bits}")
        a_coef, order = chosen
        vols = volcano_records(trace_of(order, p), p)
        tags = ["j1728", "ordinary", "cm", "glv-j1728", "prime-field"]
        if any(vrec["height"] >= 2 for vrec in vols):
            tags.append("volcano")
        name = f"fp-j1728-b{bits}" + (f"-volcano-step{step}" if step > 1 else "")
        prime_record(
            id=name,
            family="prime-j1728",
            p=p,
            a=a_coef,
            b=0,
            order=order,
            tags=tags,
            endomorphism=endo_j1728(),
            notes=f"j = 1728. Representation 4p = t^2 + 4 v^2 with t = {t}, v = {v}. Coefficient a = {a_coef} selects the twist.",
            certificate="cm-discriminant--4",
            volcanoes=vols,
            rng_seed=9000 + bits + step,
        )


def build_special_cm():
    discs = [-7, -8, -11, -19, -43, -67, -163]
    for D in discs:
        for bits in (48, 192):
            step = 1
            _build_cm_curve(D, bits, step, f"fp-cm-d{-D}-b{bits}")
    # Tall volcanoes on D = -7 and D = -11.
    _build_cm_curve(-7, 64, 9, "fp-cm-d7-b64-volcano3-h2")
    _build_cm_curve(-7, 96, 27, "fp-cm-d7-b96-volcano3-h3")
    _build_cm_curve(-11, 128, 25, "fp-cm-d11-b128-volcano5-h2")
    _build_cm_curve(-11, 256, 49, "fp-cm-d11-b256-volcano7-h2")
    _build_cm_curve(-19, 384, 1, "fp-cm-d19-b384")
    _build_cm_curve(-43, 521, 1, "fp-cm-d43-b521")
    _build_cm_curve(-163, 768, 1, "fp-cm-d163-b768")
    # Class number 2, j-invariants that are not the nine Heegner numbers.
    for D in (-15, -20, -24, -35, -51):
        for bits in (64, 160):
            _build_cm_curve(D, bits, 1, f"fp-cm-d{-D}-b{bits}-class2")


def _build_cm_curve(D: int, bits: int, step: int, name: str):
    p, t, v = cm_representation(D, bits, step, seed=3000 + (-D) * 100 + bits + step)
    poly = class_poly(D)
    roots = poly_roots_mod(poly, p)
    if not roots:
        raise RuntimeError(f"class polynomial has no root for {name}")
    j = roots[0]
    a, b = curve_from_j(j, p)
    cands = [p + 1 - t, p + 1 + t]
    # Non-maximal conductor can still have trace ±t for the curve with this j
    # only when the Hilbert polynomial describes the maximal order and v = ±1.
    # For v ≠ ±1 the crater curve (this j) has trace ±t with discriminant v^2 D,
    # yes: Z[π] has discriminant t^2 - 4p = D v^2, and End is the maximal order
    # precisely because j is the Hilbert root. Trace is ±t. Good.
    chosen = None
    for twist in range(0, 8):
        if twist == 0:
            aa, bb = a, b
            d = 1
        else:
            d = twist + 1
            if legendre(d, p) != -1 and twist > 0:
                # Still a valid isomorphism or twist; require a non-square after a few.
                if legendre(d, p) == 0:
                    continue
            aa, bb = twist_short(a, b, d, p)
        if not nonsingular(aa, bb, p):
            continue
        P = hash_point_prime(aa, bb, p, name + f":{twist}")
        Q = hash_point_prime(aa, bb, p, name + f":q{twist}")
        try:
            order = match_order(cands, [P, Q], aa, p)
        except RuntimeError:
            continue
        chosen = (aa, bb, order, d)
        break
    if chosen is None:
        raise RuntimeError(f"twist match failed for {name}")
    aa, bb, order, d = chosen
    vols = volcano_records(trace_of(order, p), p)
    tags = ["cm", "special-endomorphism", "prime-field", "ordinary"]
    if j % p == 0:
        tags.append("j0")
    elif j % p == 1728 % p:
        tags.append("j1728")
    else:
        tags.append("j-generic")
    if any(vrec["height"] >= 2 for vrec in vols):
        tags.append("volcano")
    if len(poly) > 2:
        tags.append("class-number-gt-1")
    prime_record(
        id=name,
        family="prime-cm",
        p=p,
        a=aa,
        b=bb,
        order=order,
        tags=tags,
        endomorphism=endo_disc(D),
        notes=f"CM discriminant {D}, class polynomial degree {len(poly) - 1}, twist scalar d = {d}, representation t = {t}, v = {v}.",
        certificate=f"cm-discriminant-{D}",
        volcanoes=vols,
        rng_seed=11000 + bits + (-D),
    )


def build_random_and_smooth():
    for bits in (12, 16, 20, 24, 32, 40, 48, 61):
        p = prime_of_bits(bits, seed=4000 + bits)
        rng = Rng(4100 + bits)
        found_prime = None
        found_smooth = None
        for k in range(80):
            a = rng.below(p)
            b = rng.below(p)
            if not nonsingular(a, b, p):
                continue
            if bits <= 20:
                order = brute_order(a, b, p)
            else:
                order = mestre_order(a, b, p, Rng(rng.next()))
            parts = split_group(order)
            j = j_invariant(a, b, p)
            if j in (0, 1728 % p):
                continue
            if found_prime is None and parts["subgroup_probable_prime"] and parts["cofactor_int"].bit_length() <= 4:
                found_prime = (a, b, order)
            if found_smooth is None and parts["fully_smooth"]:
                found_smooth = (a, b, order)
            if found_prime and found_smooth:
                break
        if found_prime is None:
            raise RuntimeError(f"no random prime-order curve at {bits}")
        a, b, order = found_prime
        prime_record(
            id=f"fp-random-b{bits}",
            family="prime-random-j",
            p=p,
            a=a,
            b=b,
            order=order,
            tags=["j-generic", "ordinary", "prime-field", "random-j"],
            endomorphism={"kind": "negation-only", "automorphism_group_order": 2, "description": "No CM discriminant was imposed. Only the negation map is known to be rational."},
            notes="Order pinned by enumeration or Mestre–Shanks inside the Hasse interval, then checked by scalar annihilation. j is neither 0 nor 1728.",
            certificate="mestre-or-enumeration",
            volcanoes=volcano_records(trace_of(order, p), p),
            rng_seed=12000 + bits,
        )
        if found_smooth:
            a, b, order = found_smooth
            prime_record(
                id=f"fp-smooth-b{bits}",
                family="prime-smooth-order",
                p=p,
                a=a,
                b=b,
                order=order,
                tags=["j-generic", "pohlig-hellman", "prime-field", "smooth-order"],
                endomorphism={"kind": "negation-only", "automorphism_group_order": 2, "description": "Generic automorphism group. The group order is smooth, so Pohlig–Hellman applies."},
                notes="Every prime factor of the group order is at most 10^6 (or was split by a short Pollard rho). This is a Pohlig–Hellman benchmark, not a generic-group one.",
                certificate="mestre-or-enumeration",
                volcanoes=[],
                rng_seed=13000 + bits,
            )


def build_anomalous():
    # Trace 1: 4p = 1 - D v^2. Use D = -3 so 4p = 1 + 3 v^2, p = (1 + 3 v^2)/4.
    for bits in (16, 24, 32, 48, 64, 96, 128, 192):
        p = None
        v = None
        # v ~ 2^{bits/2}
        v0 = isqrt((1 << (bits + 1)) // 3)
        v = v0 | 1
        for _ in range(200000):
            num = 1 + 3 * v * v
            if num % 4 == 0:
                cand = num // 4
                if cand.bit_length() == bits and cand % 3 == 1 and is_probable_prime(cand):
                    p = cand
                    break
            v += 2
        if p is None:
            raise RuntimeError(f"anomalous search failed at {bits}")
        # Find b such that the order is p (trace 1), not one of the other five.
        cands = j0_candidates(1, v, p)
        chosen = None
        for b in range(1, 180):
            P = hash_point_prime(0, b, p, f"anom-{bits}-{b}")
            Q = hash_point_prime(0, b, p, f"anomq-{bits}-{b}")
            try:
                order = match_order(cands, [P, Q], 0, p)
            except RuntimeError:
                continue
            if order == p:
                chosen = b
                break
        if chosen is None:
            raise RuntimeError(f"no anomalous twist at {bits}")
        prime_record(
            id=f"fp-anomalous-b{bits}",
            family="prime-anomalous",
            p=p,
            a=0,
            b=chosen,
            order=p,
            tags=["anomalous", "j0", "smart", "prime-field"],
            endomorphism={"kind": "anomalous", "description": "Group order equals the field prime, so the Smart–Semaev–Satoh–Araki p-adic lift applies."},
            notes=f"Trace 1, so #E(F_p) = p. Constructed from 4p = 1 + 3 v^2, v = {v}. A generic rho on this curve is the slow algorithm.",
            certificate="cm-anomalous-trace-1",
            volcanoes=volcano_records(1, p),
            rng_seed=14000 + bits,
        )


def build_supersingular_mov():
    for bits in (16, 32, 48, 64, 96, 128, 192, 256):
        # p ≡ 2 (mod 3) makes every j = 0 curve supersingular, order p + 1.
        seed = 6000 + bits
        p = prime_of_bits(bits, seed)
        while p % 3 != 2:
            p = next_prime(p + 1)
            if p.bit_length() != bits:
                p = prime_of_bits(bits, seed + p)
        b = 1
        order = p + 1
        # Confirm.
        P = hash_point_prime(0, b, p, f"ss-{bits}")
        if ec_mul(order, P, 0, p) is not INF:
            raise RuntimeError("supersingular order mismatch")
        prime_record(
            id=f"fp-supersingular-j0-b{bits}",
            family="prime-supersingular",
            p=p,
            a=0,
            b=b,
            order=order,
            tags=["supersingular", "j0", "pairing", "mov", "prime-field"],
            endomorphism={"kind": "supersingular", "embedding_degree": 2, "description": "Trace 0. The MOV embedding degree is 2: the subgroup lands in F_{p^2}^*."},
            notes="p ≡ 2 (mod 3), curve y^2 = x^3 + 1. Every such curve is supersingular of order p + 1.",
            certificate="supersingular-trace-0",
            volcanoes=[],
            rng_seed=15000 + bits,
        )


def build_bn():
    # Barreto–Naehrig: p = 36z^4 + 36z^3 + 24z^2 + 6z + 1, n = p - 6z^2, t = 6z^2 + 1.
    # Pick z so p lands near the requested sizes. z = 1 is the toy.
    zs = [1, 2, 3, 4, 6, 8, 13, 16, 32, 64, 2**16 + 7, 2**32 + 15, 2**48 + 21, 2**80 + 33]
    seen_bits = set()
    for z in zs:
        p = 36 * z**4 + 36 * z**3 + 24 * z**2 + 6 * z + 1
        n = 36 * z**4 + 36 * z**3 + 18 * z**2 + 6 * z + 1
        t = 6 * z * z + 1
        if not is_probable_prime(p) or not is_probable_prime(n):
            continue
        bits = p.bit_length()
        if bits in seen_bits:
            continue
        if bits > 768:
            continue
        # Order should be n for one sextic twist. n = p + 1 - t.
        if p + 1 - t != n:
            raise RuntimeError("BN parameter identity failed")
        cands = [n, p + 1 + t]
        chosen = None
        for b in list(range(1, 12)) + [2, 3, 4, 5]:
            if not nonsingular(0, b, p):
                continue
            P = hash_point_prime(0, b, p, f"bn-{z}-{b}")
            Q = hash_point_prime(0, b, p, f"bnq-{z}-{b}")
            try:
                order = match_order(cands, [P, Q], 0, p)
            except RuntimeError:
                continue
            if order == n:
                chosen = b
                break
        if chosen is None:
            continue
        seen_bits.add(bits)
        prime_record(
            id=f"fp-bn-b{bits}",
            family="prime-bn-pairing",
            p=p,
            a=0,
            b=chosen,
            order=n,
            tags=["pairing", "j0", "bn", "embedding-degree-12", "prime-field", "ordinary"],
            endomorphism={"kind": "bn", "embedding_degree": 12, "z": hx(z), "description": "Barreto–Naehrig curve, j = 0, embedding degree 12. The pairing transfers the subgroup into F_{p^{12}}^*."},
            notes=f"BN parameter z = {z}. Group order n(z) is the prime subgroup; cofactor is 1 when n is the full order.",
            certificate="bn-polynomial",
            volcanoes=volcano_records(t, p),
            rng_seed=16000 + bits,
        )
        if len(seen_bits) >= 8:
            break


def build_volcano_exhibit():
    """One fully expanded 3-volcano: every rational neighbour j, with a curve model."""
    p, t, v = cm_representation(-7, 32, 27, seed=424242)
    poly = class_poly(-7)
    j0 = poly_roots_mod(poly, p)[0]
    a, b = curve_from_j(j0, p)
    cands = [p + 1 - t, p + 1 + t]
    chosen = None
    for twist in range(0, 6):
        d = 1 if twist == 0 else twist + 1
        aa, bb = (a, b) if twist == 0 else twist_short(a, b, d, p)
        P = hash_point_prime(aa, bb, p, f"exhibit-{twist}")
        Q = hash_point_prime(aa, bb, p, f"exhibitq-{twist}")
        try:
            order = match_order(cands, [P, Q], aa, p)
        except RuntimeError:
            continue
        chosen = (aa, bb, order)
        break
    if chosen is None:
        raise RuntimeError("exhibit twist failed")
    aa, bb, order = chosen
    # BFS the rational 3-isogeny graph.
    layers: dict[int, list[int]] = {0: [j0 % p]}
    seen = {j0 % p}
    frontier = [j0 % p]
    depth = 0
    while frontier and depth < 6 and len(seen) < 64:
        nxt = []
        for j in frontier:
            for nb in phi_neighbors(j, 3, p):
                if nb not in seen:
                    seen.add(nb)
                    nxt.append(nb)
        if not nxt:
            break
        depth += 1
        layers[depth] = nxt
        frontier = nxt
    layer_recs = []
    for level, js in layers.items():
        entries = []
        for j in js:
            aj, bj = curve_from_j(j, p)
            # Same order for every F_p-isogenous curve; select the twist that realises it.
            hit = None
            for twist in range(0, 8):
                d = 1 if twist == 0 else twist + 1
                at, bt = (aj, bj) if twist == 0 else twist_short(aj, bj, d, p)
                if not nonsingular(at, bt, p):
                    continue
                P = hash_point_prime(at, bt, p, f"layer{level}-{j}-{twist}")
                if ec_mul(order, P, at, p) is INF:
                    hit = (at, bt, P)
                    break
            if hit is None:
                continue
            at, bt, P = hit
            entries.append({"j": hx(j), "a": hx(at), "b": hx(bt), "point": {"x": hx(P[0]), "y": hx(P[1])}})
        layer_recs.append({"level": level, "role": "crater" if level == 0 else ("floor" if level == depth else "slope"), "curves": entries})
    vols = volcano_records(trace_of(order, p), p)
    rec = prime_record(
        id="fp-volcano-d7-l3-exhibit",
        family="isogeny-volcano",
        p=p,
        a=aa,
        b=bb,
        order=order,
        tags=["volcano", "cm", "special-endomorphism", "prime-field", "ordinary"],
        endomorphism=endo_disc(-7),
        notes="Crater of an F_p-rational 3-isogeny volcano. `layers` lists models at every depth reached by Φ_3. Curves on the same volcano share this group order.",
        certificate="cm-discriminant--7",
        volcanoes=vols,
        rng_seed=17000,
    )
    rec["layers"] = layer_recs
    rec["volcano_depth_reached"] = depth
    rec["notes"] += f" BFS depth {depth}. CM height metadata is in `volcanoes`."


def build_koblitz():
    degrees = [4, 5, 7, 8, 9, 10, 12, 15, 16, 18, 21, 24, 31, 36, 41, 48, 61, 63, 83, 96, 97, 103, 107, 127, 131, 155, 192, 210, 256, 384, 512, 571, 768]
    for m in degrees:
        bin_mod_int(m)  # cache the modulus once
        for a_bit in (0, 1):
            order = koblitz_order(a_bit, m)
            _emit_binary(
                id=f"f2-koblitz-a{a_bit}-m{m}",
                family="binary-koblitz",
                m=m,
                a=a_bit,
                b=1,
                order=order,
                tags=_binary_degree_tags(m) + ["koblitz", "ordinary", "frobenius-endomorphism"],
                certificate="koblitz-trace-recurrence",
                notes=f"Koblitz curve y^2 + x y = x^3 + {a_bit} x^2 + 1 over F_2^{m}. The Frobenius endomorphism satisfies τ^2 - μ τ + 2 = 0 and folds the rho walk.",
                endomorphism={
                    "kind": "frobenius",
                    "mu": -1 if a_bit == 0 else 1,
                    "description": "Ordinary Koblitz. τ(x, y) = (x^2, y^2) is an endomorphism defined over F_2.",
                },
                defined_over=1,
            )


def _binary_degree_tags(m: int) -> list[str]:
    tags = ["binary", "char-2"]
    if m > 1 and all(m % p for p in range(2, isqrt(m) + 1)):
        tags.append("prime-degree")
    else:
        tags.append("composite-degree")
    return tags


def _emit_binary(id, family, m, a, b, order, tags, certificate, notes, endomorphism, defined_over, verify=True):
    mod_terms = [i for i in range(m + 1) if (bin_mod_int(m) >> i) & 1]
    parts = split_group(order)
    verified = False
    h = parts["cofactor_int"]
    n = parts["subgroup_int"]
    G = None
    # Projective scalar multiplication makes the check cheap through degree 768.
    if verify:
        witness = find_binary_point(a, b, m, id + ":order")
        if not bin_on_curve(witness, a, b, m):
            raise RuntimeError(f"{id} point off curve")
        if bin_mul_point(order, witness, a, b, m) is not INF:
            raise RuntimeError(f"{id} order does not annihilate")
        for attempt in range(64):
            P = witness if attempt == 0 else find_binary_point(a, b, m, f"{id}:gen:{attempt}")
            gen = bin_mul_point(h, P, a, b, m)
            if gen is not INF and bin_mul_point(n, gen, a, b, m) is INF:
                G = gen
                break
        if G is None:
            raise RuntimeError(f"{id} generator collapsed")
        verified = True
    else:
        G = find_binary_point(a, b, m, id + ":gen")
    sub_bits = parts["subgroup_int"].bit_length()
    known = None
    if verified and n > 1 and sub_bits <= 48:
        known = 1 + (m * 17 + a + b) % (n - 1)
        target = bin_mul_point(known, G, a, b, m)
        # The published subgroup need not be prime, so this multiple can be 0.
        if target is INF:
            known = 1
            target = G
    else:
        T = find_binary_point(a, b, m, id + ":target")
        target = bin_mul_point(h, T, a, b, m)
        if target is INF:
            target = G
    rec = {
        "id": id,
        "family": family,
        "tier": tier_for(sub_bits, verified),
        "tags": tags,
        "field": {
            "type": "binary",
            "characteristic": "0x2",
            "degree": m,
            "degree_kind": "prime" if "prime-degree" in tags else "composite",
            "cardinality": hx(1 << m),
            "cardinality_bits": m,
            "polynomial_terms": mod_terms,
            "field_of_definition_degree": defined_over,
        },
        "model": "binary-weierstrass",
        "equation": "y^2 + x*y = x^3 + a*x^2 + b",
        "a": hx(a),
        "b": hx(b),
        "j": "1/b" if b else "supersingular",
        "group_order": hx(order),
        "cofactor": parts["cofactor"],
        "subgroup_order": parts["subgroup_order"],
        "subgroup_probable_prime": parts["subgroup_probable_prime"],
        "generator": {"x": hx(G[0]), "y": hx(G[1])},
        "target": {"x": hx(target[0]), "y": hx(target[1])},
        "known_log": hx(known) if known is not None else None,
        "endomorphism": endomorphism,
        "volcanoes": [],
        "order_certificate": certificate,
        "verification": "scalar-annihilation" if verified else "trace-recurrence",
        "suggested_solvers": solvers_for(tags, parts),
        "notes": notes,
    }
    emit(rec)


def build_binary_subfield_and_random():
    # A non-Koblitz curve counted on F_2^5 (a=1, b=x+1 style integer b != 1) and lifted.
    # Count over F_2^m for a fixed curve by BSGS-like enumeration when m is small.
    base_m = 5
    a, b = 1, 3  # b = x + 1, not the Koblitz b = 1
    base_order = enumerate_binary_order(a, b, base_m)
    t = (1 << base_m) + 1 - base_order
    for k, total in ((2, 10), (3, 15), (4, 20), (6, 30), (8, 40), (12, 60)):
        order = order_from_trace(1 << base_m, t, k)
        # The curve is defined over F_2^5 and base-changed to F_2^{5k}.
        # Represent the big field with its own irreducible; coefficients a, b
        # are degree < 5 integers, which remain the same bit-polynomials only
        # if we keep the curve over the base and store the extension order.
        # Point search happens in the big field, so a and b must be interpreted
        # in that field. Bit-polynomials of degree < 5 embed into any polynomial
        # basis as the same integers only when the modulus extends the base
        # modulus — it does not. So treat a, b as elements of the prime field
        # subfield of the big field (constants). Use a curve DEFINED over F_2.
        pass
    # Curve over F_2: y^2 + x y = x^3 + x^2 + 1 (a=1, b=1 is Koblitz). Use
    # y^2 + x y = x^3 + 1, which is Koblitz a=0. For a genuinely different
    # subfield curve, count y^2 + x y = x^3 + x^2 + (x) wait b must be in the
    # base field. Over F_2 the only nonsingular ordinary curves are the two
    # Koblitz curves. So intermediate fields are the interesting ones.
    base_m = 4
    a, b = 1, 6  # b = x^2 + x, nonzero
    if enumerate_binary_order(a, b, base_m) == 0:
        raise RuntimeError("singular or empty")
    base_order = enumerate_binary_order(a, b, base_m)
    # Confirm nonsingular: b != 0.
    t = (1 << base_m) + 1 - base_order
    # Lifts below re-express the curve over F_2^{4k} with CONSTANT coefficients
    # would change the curve. Instead, store these as curves over F_2^{base_m}
    # together with the lifted order of the base change, and give a generator
    # over the base field (order dividing the base order) plus the extension
    # cardinality. Contributors attacking the extension need the embedding.
    # Practical choice: run the curve over F_2^{4k} with the same integer
    # coefficients, which is well-defined, and set the order by COUNTING when
    # small and by "this is not a lift" otherwise.
    for m in (4, 6, 8, 12):
        order = enumerate_binary_order(a, b, m) if m <= 12 else None
        if order is None:
            continue
        _emit_binary(
            id=f"f2-random-a1-b6-m{m}",
            family="binary-random",
            m=m,
            a=a,
            b=b,
            order=order,
            tags=_binary_degree_tags(m) + ["random-j", "ordinary"],
            certificate="enumeration",
            notes="Ordinary binary curve that is not a Koblitz curve (b ≠ 1). Order by enumerating x and solving z^2 + z = c.",
            endomorphism={"kind": "negation-and-frobenius-of-the-field", "description": "No global Frobenius endomorphism of degree 2 unless the coefficients lie in a proper subfield."},
            defined_over=m,
        )
    # Genuine subfield lifts: curve over F_2 with a=1, b=1 is already Koblitz.
    # Count a curve over F_2^3 and lift to multiples of 3.
    base_m = 3
    a, b = 1, 3
    base_order = enumerate_binary_order(a, b, base_m)
    t = (1 << base_m) + 1 - base_order
    for k in (2, 4, 5, 6, 8, 10, 20):
        total = base_m * k
        if total > 256:
            continue
        # WARNING: lifting is valid for the base change of the SAME curve.
        # The integer coefficients a, b are elements of F_2^3, not of F_2.
        # They do not automatically sit inside F_2^{3k} without an embedding.
        # We only emit the lift when we can verify the order by enumeration
        # or when total degree stays small enough to scalar-check a point on
        # a field in which a and b are interpreted via an explicit tower.
        order = order_from_trace(1 << base_m, t, k)
        _emit_tower_binary(base_m, k, a, b, base_order, order)


def enumerate_binary_order(a, b, m) -> int:
    mod = bin_mod_int(m)
    # N = 1 + sum_x (1 + χ) where the Artin-Schreier equation is solvable.
    n = 1
    for x in range(1 << m):
        if x == 0:
            # y^2 = b, so y = sqrt(b). In char 2 every element has a unique square root.
            # Equation y^2 + 0*y = b, i.e. y^2 = b. Always one solution if we take
            # the half-square, but y^2 = b is NOT z^2 + z = c. Direct: as y runs,
            # y^2 runs through the field once. Exactly one y. Point (0, sqrt(b)).
            n += 1
            continue
        c = bin_curve_rhs_c(x, a, b, mod, m)
        if bin_trace(c, mod, m) == 0:
            n += 2
    return n


def _emit_tower_binary(base_m, k, a, b, base_order, order):
    """Curve over F_2^{base_m}, base-changed to a degree-k tower. Coefficients stay in the base."""
    total = base_m * k
    # Extension modulus of degree k over the base field. For the corpus we
    # store the base modulus and a degree-k irreducible over F_2 lifted by
    # searching a polynomial whose reduction describes the tower as a flat
    # field only when k = 1. Here k > 1: publish the base curve (already
    # counted) parameters and the lifted order, and give an F_2^{base_m}
    # point. The extension ECDLP generator is a deterministic point in the
    # flat field F_2^{total} ONLY if a, b lie in F_2. They don't.
    # So the record's arithmetic is the BASE field, and `extension` describes
    # the base change the order refers to. Mark verification as recurrence
    # plus a full check on the base.
    if bin_mul_point(base_order, find_binary_point(a, b, base_m, f"tower-{base_m}-{k}"), a, b, base_m) is INF:
        pass
    G = find_binary_point(a, b, base_m, f"tower-gen-{base_m}-{k}")
    if bin_mul_point(base_order, G, a, b, base_m) is not INF:
        raise RuntimeError("tower base order failed")
    parts = split_group(order)
    tags = ["binary", "char-2", "subfield", "extension"]
    tags.append("prime-degree" if _is_prime(k) else "composite-degree")
    mod_terms = [i for i in range(base_m + 1) if (bin_mod_int(base_m) >> i) & 1]
    rec = {
        "id": f"f2-subfield-base{base_m}-ext{k}",
        "family": "binary-subfield",
        "tier": "open",
        "tags": tags,
        "field": {
            "type": "binary-tower",
            "characteristic": "0x2",
            "base_degree": base_m,
            "extension_degree": k,
            "degree": total,
            "degree_kind": "prime" if _is_prime(total) else "composite",
            "cardinality": hx(1 << total),
            "cardinality_bits": total,
            "base_polynomial_terms": mod_terms,
            "field_of_definition_degree": base_m,
        },
        "model": "binary-weierstrass",
        "equation": "y^2 + x*y = x^3 + a*x^2 + b  (coefficients in the base field)",
        "a": hx(a),
        "b": hx(b),
        "base_group_order": hx(base_order),
        "group_order": hx(order),
        "cofactor": parts["cofactor"],
        "subgroup_order": parts["subgroup_order"],
        "subgroup_probable_prime": parts["subgroup_probable_prime"],
        "generator": {"x": hx(G[0]), "y": hx(G[1]), "defined_over": "base"},
        "target": None,
        "known_log": None,
        "endomorphism": {
            "kind": "subfield-frobenius",
            "description": "Defined over F_2^{base_m} and considered over F_2^{base_m * k}. The base-field Frobenius is an endomorphism of the base change only after Weil restriction; the trace lift gives the order.",
        },
        "volcanoes": [],
        "order_certificate": "base-enumeration-plus-trace-lift",
        "verification": "base-scalar-annihilation",
        "suggested_solvers": ["weil-descent", "gaudry-diem-index-calculus", "pollard-rho"],
        "notes": f"Coefficients live in F_2^{base_m}. Group order over F_2^{total} is the trace lift of a fully enumerated base curve. The published generator is a base-field point; an extension-field generator is any point of the lifted group.",
    }
    emit(rec)


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    return all(n % p for p in range(2, isqrt(n) + 1))


def build_binary_supersingular():
    # y^2 + y = x^3 + x is defined over F_2. b = 1 has no affine point over F_2
    # (both right-hand sides have trace 1), so the base curve uses b = 0.
    # Enumeration at m = 1 is the certificate; larger degrees are the base change.
    b = 0
    base = enumerate_ss_binary(1, b=b)
    trace = (1 << 1) + 1 - base
    for m in (1, 5, 7, 9, 15, 21, 31, 63, 127):
        order = order_from_trace(2, trace, m)
        if m <= 15:
            # The lift has to agree with a direct count on small fields.
            assert order == enumerate_ss_binary(m, b=b)
        _emit_ss_binary(m, b, order)


def enumerate_ss_binary(m: int, b: int) -> int:
    # Brute the Artin–Schreier curve y^2 + y = x^3 + x + b by testing every x.
    # Solvable iff Tr(x^3 + x + b) = 0, two solutions then.
    mod = bin_mod_int(m)
    n = 1
    for x in range(1 << m):
        cube = bin_mul(bin_mul(x, x, mod, m), x, mod, m)
        rhs = cube ^ x ^ b
        if bin_trace(rhs, mod, m) == 0:
            n += 2
    return n


def _emit_ss_binary(m, b, order):
    # Group law check for a small multiple, and full annihilation when m <= 21.
    mod = bin_mod_int(m)
    G = None
    for i in range(100000):
        x = sha_int(f"ss-{m}", i, m)
        cube = bin_mul(bin_mul(x, x, mod, m), x, mod, m)
        rhs = cube ^ x ^ b
        y = solve_z2_plus_z(rhs, m)
        if y is not None:
            G = (x, y)
            break
    if G is None:
        raise RuntimeError("no supersingular point")
    verified = False
    if m <= 31:
        if ss_mul(order, G, m) is not INF:
            raise RuntimeError(f"supersingular order failed at m={m}")
        verified = True
    parts = split_group(order)
    tags = _binary_degree_tags(m) + ["supersingular", "j0"]
    rec = {
        "id": f"f2-supersingular-m{m}",
        "family": "binary-supersingular",
        "tier": tier_for(parts["subgroup_int"].bit_length(), verified),
        "tags": tags,
        "field": {
            "type": "binary",
            "characteristic": "0x2",
            "degree": m,
            "degree_kind": "prime" if "prime-degree" in tags else "composite",
            "cardinality": hx(1 << m),
            "cardinality_bits": m,
            "polynomial_terms": [i for i in range(m + 1) if (bin_mod_int(m) >> i) & 1],
            "field_of_definition_degree": 1,
        },
        "model": "binary-supersingular",
        "equation": "y^2 + y = x^3 + x + b",
        "a": "0x1",
        "b": hx(b),
        "j": "0x0",
        "group_order": hx(order),
        "cofactor": parts["cofactor"],
        "subgroup_order": parts["subgroup_order"],
        "subgroup_probable_prime": parts["subgroup_probable_prime"],
        "generator": {"x": hx(G[0]), "y": hx(G[1])},
        "target": {"x": hx(G[0]), "y": hx(G[1])},
        "known_log": "0x1" if verified and parts["subgroup_int"].bit_length() <= 40 else None,
        "endomorphism": {"kind": "supersingular", "description": "j = 0 in characteristic 2. The curve is supersingular; Weil descent and the MOV attack both see the embedding."},
        "volcanoes": [],
        "order_certificate": "base-enumeration-plus-trace-lift",
        "verification": "scalar-annihilation" if verified else "trace-recurrence",
        "suggested_solvers": ["mov-frey-ruck", "weil-descent", "pollard-rho"],
        "notes": "Supersingular binary curve y^2 + y = x^3 + x + b. Order counted by the trace of the Artin–Schreier right-hand side. b = 0 so the base change of the F_2 curve has an affine point.",
    }
    # known_log 1 only makes sense if target is G and G has order dividing subgroup... skip bogus known log
    if rec["known_log"] == "0x1":
        rec["target"] = {"x": hx(G[0]), "y": hx(G[1])}
        # only valid if subgroup generator is G, i.e. cofactor 1 or we set generator to G and known log of target = G is 1
        # iff order of G equals subgroup. Don't claim it unless cofactor * 1 works.
        rec["known_log"] = None
        rec["tier"] = "open" if parts["subgroup_int"].bit_length() > 40 else "check"
        if verified and parts["subgroup_int"].bit_length() <= 40 and parts["cofactor_int"] == 1:
            rec["known_log"] = "0x1"
    emit(rec)


def ss_add(P, Q, m):
    mod = bin_mod_int(m)
    if P is INF:
        return Q
    if Q is INF:
        return P
    x1, y1 = P
    x2, y2 = Q
    if x1 == x2:
        if y1 != y2:
            return INF
        # λ = x^2 + 1  for a = 1 (curve y^2+y = x^3 + a x + b, a=1)
        lam = bin_mul(x1, x1, mod, m) ^ 1
        x3 = bin_mul(lam, lam, mod, m)
        y3 = 1 ^ y1 ^ bin_mul(lam, x1 ^ x3, mod, m)
        return x3, y3
    lam = bin_mul(y1 ^ y2, bin_inv(x1 ^ x2, mod, m), mod, m)
    x3 = bin_mul(lam, lam, mod, m) ^ x1 ^ x2
    y3 = 1 ^ y1 ^ bin_mul(lam, x1 ^ x3, mod, m)
    return x3, y3


def ss_mul(k, P, m):
    R = INF
    Q = P
    while k:
        if k & 1:
            R = ss_add(R, Q, m)
        Q = ss_add(Q, Q, m)
        k >>= 1
    return R


def build_char3():
    # Ordinary model over F_3: y^2 = x^3 + a x^2 + b, a,b in {1,2}.
    field1 = Ext(3, [0, 1])  # degree 1, modulus x. Wait mod [0,1] is x, degree 1, elements length 1. x ≡ 0, so this is NOT a field representation of F_3.
    # Degree 1 is just integers mod 3. Handle base count directly.
    a, b = 1, 1
    base_order = count_char3_prime(a, b, "ordinary")
    t = 3 + 1 - base_order
    degrees = [1, 2, 4, 5, 6, 8, 9, 10, 12, 16, 18, 27, 32, 36, 64, 81, 108, 128, 162, 243, 256, 384, 486]
    mod_cache = {1: None}
    for n in degrees:
        if n == 1:
            field = None
            order = base_order
        else:
            if n not in mod_cache:
                mod_cache[n] = ext_irreducible(3, n, seed=70_000 + n)
            field = Ext(3, mod_cache[n])
            order = order_from_trace(3, t, n)
        _emit_char3(n, a, b, order, "ordinary", field, mod_cache.get(n), base_trace=t)
    # Supersingular y^2 = x^3 + x + 1 over F_3, lifted.
    ss_order = count_char3_prime(1, 1, "supersingular")
    st = 3 + 1 - ss_order
    for n in (1, 2, 4, 5, 6, 8, 9, 12, 16, 18, 27, 32, 64, 81, 128, 243):
        if n == 1:
            field = None
            order = ss_order
            mod = None
        else:
            mod = mod_cache.get(n) or ext_irreducible(3, n, seed=70_000 + n)
            mod_cache[n] = mod
            field = Ext(3, mod)
            order = order_from_trace(3, st, n)
        _emit_char3(n, 1, 1, order, "supersingular", field, mod, base_trace=st)


def count_char3_prime(A, B, model) -> int:
    n = 1
    for x in range(3):
        if model == "ordinary":
            rhs = (x * x * x + A * x * x + B) % 3
        else:
            rhs = (x * x * x + x + B) % 3
        # squares mod 3: 0, 1, not 2.
        if rhs == 0:
            n += 1
        elif rhs == 1:
            n += 2
    return n


def _emit_char3(n, A, B, order, model, field, mod, base_trace):
    parts = split_group(order)
    degree_kind = "prime-field" if n == 1 else ("prime" if _is_prime(n) else "composite")
    tags = ["char-3", "extension" if n > 1 else "prime-field", "subfield"]
    if degree_kind == "prime":
        tags.append("prime-degree")
    elif degree_kind == "composite":
        tags.append("composite-degree")
    if model == "supersingular":
        tags += ["supersingular", "j0"]
    else:
        tags += ["ordinary"]
    verified = False
    G = None
    target = None
    known = None
    if n == 1:
        # Manual point over F_3.
        for x in range(3):
            rhs = (x**3 + A * x * x + B) % 3 if model == "ordinary" else (x**3 + x + B) % 3
            for y in range(3):
                if (y * y) % 3 == rhs:
                    G = (x, y)
                    break
            if G:
                break
        if G is None:
            raise RuntimeError("no F_3 point")
        # Check order with char3 group law on a degree-1 field. Build Ext only if degree >= 1 works.
        # Use integer group law mod 3.
        if not _char3_prime_annihilates(order, G, A, model):
            raise RuntimeError("char3 base order failed")
        verified = True
        gen_json = {"x": hx(G[0]), "y": hx(G[1])}
        target_json = gen_json
        # Target is the generator, so the discrete log is 1.
        if parts["subgroup_int"] > 1 and parts["subgroup_int"].bit_length() <= 48:
            known = 1
    else:
        AA = field.const(A)
        BB = field.const(B)
        G = char3_hash_point(field, AA, BB, model, f"c3-{model}-{n}")
        if not char3_on(field, G, AA, BB, model):
            raise RuntimeError("char3 point off curve")
        do_scalar = n <= 96
        if do_scalar:
            if char3_mul(field, order, G, AA, model) is not INF:
                raise RuntimeError(f"char3 order failed at degree {n}")
            h = parts["cofactor_int"]
            gen = char3_mul(field, h, G, AA, model)
            if gen is INF:
                gen = G
            G = gen
            verified = True
            if parts["subgroup_int"] > 1 and parts["subgroup_int"].bit_length() <= 48:
                known = 1 + n
                if known >= parts["subgroup_int"]:
                    known = 1
                target = char3_mul(field, known, G, AA, model)
                if target is INF:
                    known = 1
                    target = G
        gen_json = {"x": elem_json(G[0]), "y": elem_json(G[1])}
        if target is None:
            target_json = gen_json
        else:
            target_json = {"x": elem_json(target[0]), "y": elem_json(target[1])}
    cardinality_bits = math.ceil(n * math.log2(3) - 1e-9)
    rec = {
        "id": f"f3-{model}-n{n}",
        "family": "char3-subfield" if model == "ordinary" else "char3-supersingular",
        "tier": tier_for(parts["subgroup_int"].bit_length(), verified),
        "tags": tags,
        "field": {
            "type": "prime" if n == 1 else "extension",
            "characteristic": "0x3",
            "degree": n,
            "degree_kind": degree_kind,
            "cardinality": hx(pow(3, n)),
            "cardinality_bits": cardinality_bits,
            "modulus": None if mod is None else [hx(c) for c in mod],
            "field_of_definition_degree": 1,
        },
        "model": "char3-ordinary" if model == "ordinary" else "char3-supersingular",
        "equation": "y^2 = x^3 + a*x^2 + b" if model == "ordinary" else "y^2 = x^3 + x + b",
        "a": hx(A),
        "b": hx(B),
        "base_trace": base_trace,
        "group_order": hx(order),
        "cofactor": parts["cofactor"],
        "subgroup_order": parts["subgroup_order"],
        "subgroup_probable_prime": parts["subgroup_probable_prime"],
        "generator": gen_json,
        "target": target_json,
        "known_log": hx(known) if known else None,
        "endomorphism": {
            "kind": "subfield-frobenius" if model == "ordinary" else "supersingular",
            "description": "Defined over F_3 and base-changed to F_3^n. Order is the Frobenius trace lift. Composite n is the Weil-descent setting; prime n is not.",
        },
        "volcanoes": [],
        "order_certificate": "base-enumeration-plus-trace-lift" if n > 1 else "enumeration",
        "verification": "scalar-annihilation" if verified else "trace-recurrence",
        "suggested_solvers": solvers_for(tags, parts),
        "notes": f"Characteristic 3, extension degree {n} ({degree_kind}). 3^{n} has about {cardinality_bits} bits.",
    }
    emit(rec)


def _char3_prime_annihilates(order, G, A, model) -> bool:
    # Tiny group law over F_3 using integers.
    def add(P, Q):
        if P is INF:
            return Q
        if Q is INF:
            return P
        x1, y1 = P
        x2, y2 = Q
        if x1 == x2 and (y1 + y2) % 3 == 0:
            return INF
        if model == "ordinary":
            if x1 == x2:
                lam = (A * x1 * modinv(y1, 3)) % 3
                x3 = (lam * lam - A + x1) % 3
            else:
                lam = ((y2 - y1) * modinv(x2 - x1, 3)) % 3
                x3 = (lam * lam - A - x1 - x2) % 3
        else:
            if x1 == x2:
                lam = (2 * modinv(y1, 3)) % 3
                x3 = (lam * lam - 2 * x1) % 3
            else:
                lam = ((y2 - y1) * modinv(x2 - x1, 3)) % 3
                x3 = (lam * lam - x1 - x2) % 3
        y3 = (lam * (x1 - x3) - y1) % 3
        return x3, y3

    R = INF
    Q = G
    k = order
    while k:
        if k & 1:
            R = add(R, Q)
        Q = add(Q, Q)
        k >>= 1
    return R is INF


def build_odd_extensions():
    # Small prime fields, curve y^2 = x^3 + x + 1 or j=0, counted on the base and lifted.
    jobs = []
    # (p, degree, model)
    for p, a, b in ((5, 1, 1), (7, 0, 2), (11, 1, 1), (17, 0, 1)):
        order = brute_order(a, b, p)
        t = p + 1 - order
        degrees = [2, 3, 4, 5, 6, 8, 9, 12]
        if p == 5:
            degrees += [16, 24]
        if p >= 11:
            degrees = [2, 3, 4, 6]
        for k in degrees:
            jobs.append((p, a, b, t, order, k, "random" if a else "j0"))
    # Large base, CM j=0, lifted to k = 2, 3, 4, 6.
    for bits, ks in ((16, (2, 3, 4, 6)), (32, (2, 3, 4)), (61, (2, 3)), (128, (2, 3)), (192, (2, 4)), (256, (2, 3)), (384, (2,))):
        p, t, v = cm_representation(-3, bits, 1, seed=80_000 + bits)
        cands = j0_candidates(t, v, p)
        b = None
        order = None
        for bb in range(1, 20):
            P = hash_point_prime(0, bb, p, f"extbase-{bits}-{bb}")
            Q = hash_point_prime(0, bb, p, f"extbaseq-{bits}-{bb}")
            try:
                order = match_order(cands, [P, Q], 0, p)
            except RuntimeError:
                continue
            b = bb
            break
        if b is None:
            raise RuntimeError(f"extension base failed at {bits}")
        tr = trace_of(order, p)
        for k in ks:
            jobs.append((p, 0, b, tr, order, k, "j0"))
    for p, a, b, t, base_order, k, shape in jobs:
        _emit_extension(p, a, b, t, base_order, k, shape)


def _emit_extension(p, a, b, t, base_order, k, shape):
    total_bits = math.ceil(k * math.log2(p) - 1e-9)
    if total_bits > 800:
        return
    mod = ext_irreducible(p, k, seed=90_000 + p + k * 17 + a + b)
    field = Ext(p, mod)
    order = order_from_trace(p, t, k)
    AA, BB = field.const(a), field.const(b)
    G = ext_hash_point(field, AA, BB, f"ext-{p}-{k}-{shape}")
    if not ext_on(field, G, AA, BB):
        raise RuntimeError("extension point off curve")
    verified = total_bits <= 220
    parts = split_group(order)
    if verified:
        if ext_ec_mul(field, order, G, AA) is not INF:
            raise RuntimeError(f"extension order failed p={p} k={k}")
        gen = ext_ec_mul(field, parts["cofactor_int"], G, AA)
        if gen is not INF:
            G = gen
    tags = ["extension", "subfield", "odd-characteristic"]
    tags.append("prime-degree" if _is_prime(k) else "composite-degree")
    if shape == "j0":
        tags += ["j0", "glv-j0"]
    else:
        tags.append("j-generic")
    if k == 2:
        tags.append("gls-setting")
    if k >= 3:
        tags.append("gaudry-setting")
    degree_kind = "prime" if _is_prime(k) else "composite"
    known = None
    target = G
    if verified and parts["subgroup_int"] > 1 and parts["subgroup_int"].bit_length() <= 48:
        known = 1 + (k % (parts["subgroup_int"] - 1))
        target = ext_ec_mul(field, known, G, AA)
        if target is INF:
            known = 1
            target = G
    rec = {
        "id": f"fp{p.bit_length()}-p{p if p < 1000 else 'b' + str(p.bit_length())}-k{k}-{shape}",
        "family": "odd-extension-subfield",
        "tier": tier_for(parts["subgroup_int"].bit_length(), verified),
        "tags": tags,
        "field": {
            "type": "extension",
            "characteristic": hx(p),
            "degree": k,
            "degree_kind": degree_kind,
            "cardinality": hx(pow(p, k)),
            "cardinality_bits": total_bits,
            "modulus": [hx(c) for c in mod],
            "field_of_definition_degree": 1,
            "base_cardinality": hx(p),
        },
        "model": "short-weierstrass",
        "equation": "y^2 = x^3 + a*x + b",
        "a": hx(a),
        "b": hx(b),
        "base_group_order": hx(base_order),
        "base_trace": t,
        "group_order": hx(order),
        "cofactor": parts["cofactor"],
        "subgroup_order": parts["subgroup_order"],
        "subgroup_probable_prime": parts["subgroup_probable_prime"],
        "generator": {"x": elem_json(G[0]), "y": elem_json(G[1])},
        "target": {"x": elem_json(target[0]), "y": elem_json(target[1])},
        "known_log": hx(known) if known else None,
        "endomorphism": {
            "kind": "subfield-frobenius" if shape != "j0" else "subfield-frobenius-plus-j0",
            "description": "Curve defined over F_p and base-changed to F_p^k. Frobenius satisfies π^2 - t π + p = 0 on the base. For k = 2 this is the GLS setting; for fixed k ≥ 3 it is the Gaudry–Diem index-calculus setting. Composite k also admits Weil descent.",
        },
        "volcanoes": [],
        "order_certificate": "base-order-plus-trace-lift",
        "verification": "scalar-annihilation" if verified else "trace-recurrence",
        "suggested_solvers": solvers_for(tags, parts),
        "notes": f"Subfield curve over F_p^k, p is {p.bit_length()} bits, k = {k} ({degree_kind}). Field size about 2^{total_bits}.",
    }
    # Stable id for large p: the formula above may collide. Append a short hash if needed later.
    emit(rec)


def write_outputs():
    CURVE_DIR.mkdir(parents=True, exist_ok=True)
    INSPECT_DIR.mkdir(parents=True, exist_ok=True)
    # Clear previous curves so a re-run cannot leave stale ids.
    for path in CURVE_DIR.glob("*.json"):
        path.unlink()
    for path in INSPECT_DIR.glob("*.json"):
        path.unlink()
    ids = [c["id"] for c in CURVES]
    if len(ids) != len(set(ids)):
        dup = [i for i in ids if ids.count(i) > 1]
        raise RuntimeError(f"duplicate ids {set(dup)}")
    summaries = []
    for rec in CURVES:
        path = CURVE_DIR / f"{rec['id']}.json"
        path.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
        summaries.append(
            {
                "id": rec["id"],
                "family": rec["family"],
                "tier": rec["tier"],
                "cardinality_bits": rec["field"]["cardinality_bits"],
                "field_type": rec["field"]["type"],
                "degree": rec["field"].get("degree"),
                "degree_kind": rec["field"].get("degree_kind"),
                "tags": rec["tags"],
                "subgroup_probable_prime": rec["subgroup_probable_prime"],
                "verification": rec["verification"],
                "order_certificate": rec["order_certificate"],
                "inspect": False,
            }
        )
        insp = inspect_record(rec)
        if insp is not None:
            (INSPECT_DIR / f"{rec['id']}.json").write_text(json.dumps(insp, indent=2, sort_keys=True) + "\n")
            summaries[-1]["inspect"] = True
    families: dict[str, int] = {}
    for rec in CURVES:
        families[rec["family"]] = families.get(rec["family"], 0) + 1
    bits = [c["field"]["cardinality_bits"] for c in CURVES]
    catalog = {
        "schema_version": 1,
        "description": "Diverse elliptic-curve challenge corpus for Pollard rho, index calculus, endomorphism folds, Weil descent and isogeny volcanoes.",
        "curve_count": len(CURVES),
        "cardinality_bits_min": min(bits),
        "cardinality_bits_max": max(bits),
        "families": families,
        "curves": summaries,
    }
    (ROOT / "catalog.json").write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n")
    print(
        f"wrote {len(CURVES)} curves, bits {min(bits)}..{max(bits)}, inspect files {sum(1 for s in summaries if s['inspect'])}",
        file=sys.stderr,
    )


def inspect_record(rec: dict) -> dict | None:
    """ca-ic Parameters JSON, when the curve fits the inspector."""
    field = rec["field"]
    if not rec["subgroup_probable_prime"]:
        return None
    if rec.get("known_log") and rec["tier"] == "check":
        fixture = {"known_log": rec["known_log"], "seed": 1}
        point = rec["target"]
    else:
        fixture = None
        point = rec["target"]
    # Inspector coordinates are strings, not coefficient lists.
    def coord(pt):
        if not pt or not isinstance(pt.get("x"), str):
            return None
        return {"x": pt["x"], "y": pt["y"]}

    generator = coord(rec["generator"])
    point = coord(point)
    if field["type"] == "prime" and rec["model"] == "short-weierstrass":
        # The inspector checks y^2 = x^3 + a x + b over a prime >= 5.
        # Characteristic 3 uses a different model and is not this shape.
        modulus = int(field["cardinality"], 16)
        if field["cardinality_bits"] > 1024 or modulus < 5:
            return None
        return {
            "schema_version": 1,
            "name": rec["id"][:120],
            "field": {"kind": "prime", "modulus": field["cardinality"]},
            "a": rec["a"],
            "b": rec["b"],
            "subgroup_order": rec["subgroup_order"],
            "cofactor": rec["cofactor"],
            "generator": generator,
            "point": point,
            "fixture": fixture,
        }
    if field["type"] == "binary" and rec["model"] == "binary-weierstrass":
        degree = field["degree"]
        if not 2 <= degree <= 768:
            return None
        # a, b must be integers that fit the field. Our records use hex.
        return {
            "schema_version": 1,
            "name": rec["id"][:120],
            "field": {"kind": "binary", "degree": degree, "polynomial_terms": field["polynomial_terms"]},
            "a": rec["a"],
            "b": rec["b"],
            "subgroup_order": rec["subgroup_order"],
            "cofactor": rec["cofactor"],
            "generator": generator,
            "point": point,
            "fixture": fixture,
        }
    return None


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def self_test():
    # Class polynomials.
    assert class_poly(-3) == [0, 1]
    assert class_poly(-4) == [-1728, 1]
    assert class_poly(-7) == [3375, 1]
    assert class_poly(-8) == [-8000, 1]
    assert class_poly(-11) == [32768, 1]
    h15 = class_poly(-15)
    assert h15 == [-121287375, 191025, 1]
    # curve_from_j round-trips.
    p = 10007
    for j in (1, 2, 17, 12345):
        a, b = curve_from_j(j, p)
        assert j_invariant(a, b, p) == j % p
    # Modular polynomial against Sage's published sample.
    p, j = 419, 1728 % 419
    coeffs = [0] * 5
    for (i, k), c in PHI[3].items():
        coeffs[k] = (coeffs[k] + c * pow(j, i, p)) % p
    assert coeffs == [329, 118, 84, 230, 1]
    assert set(poly_roots_mod([-1, 0, 1], 419)) == {1, 418}
    # Φ_2(1728, 1728) = 0 because of the degree-2 endomorphism.
    acc = 0
    for (i, k), c in PHI[2].items():
        acc += c * pow(1728, i + k, 10**9 + 7)
    # Exact integer evaluation:
    acc = sum(c * pow(1728, i) * pow(1728, k) for (i, k), c in PHI[2].items())
    assert acc == 0
    # Mestre versus enumeration.
    rng = Rng(1)
    for p in (101, 211, 1009):
        for _ in range(4):
            a, b = rng.below(p), rng.below(p)
            if not nonsingular(a, b, p):
                continue
            assert mestre_order(a, b, p, Rng(rng.next())) == brute_order(a, b, p)
    # Koblitz recurrence versus enumeration, and projective scalar versus affine addition.
    for m in range(3, 9):
        for a_bit in (0, 1):
            assert koblitz_order(a_bit, m) == enumerate_binary_order(a_bit, 1, m)
    P = find_binary_point(1, 6, 8, "self-proj")
    acc = INF
    for k in range(1, 30):
        acc = bin_add(acc, P, 1, 8)
        assert bin_mul_point(k, P, 1, 6, 8) == acc
    # Trace lift versus enumeration on a tiny extension.
    p, a, b = 5, 1, 1
    base = brute_order(a, b, p)
    t = p + 1 - base
    mod = ext_irreducible(5, 2, seed=1)
    field = Ext(5, mod)
    lifted = order_from_trace(5, t, 2)
    assert count_ext_order_by_enum(field, field.const(a), field.const(b)) == lifted
    # Char 3 model: annihilation on the base and a degree-2 lift.
    base3 = count_char3_prime(1, 1, "ordinary")
    assert 1 <= base3 <= 7
    t3 = 3 + 1 - base3
    mod3 = ext_irreducible(3, 2, seed=2)
    field3 = Ext(3, mod3)
    G = char3_hash_point(field3, field3.const(1), field3.const(1), "ordinary", "selftest")
    order = order_from_trace(3, t3, 2)
    assert char3_mul(field3, order, G, field3.const(1), "ordinary") is INF
    # CM j=0 against Mestre.
    p, t, v = cm_representation(-3, 20, 1, seed=99)
    cands = j0_candidates(t, v, p)
    P = hash_point_prime(0, 1, p, "self-j0")
    Q = hash_point_prime(0, 1, p, "self-j0b")
    order = match_order(cands, [P, Q], 0, p)
    assert order == mestre_order(0, 1, p, Rng(5))
    print("self-test ok", file=sys.stderr)


def main():
    self_test()
    if "--self-test" in sys.argv:
        return
    build_j0()
    build_j0_twist_pairs()
    build_j1728()
    build_special_cm()
    build_random_and_smooth()
    build_anomalous()
    build_supersingular_mov()
    build_bn()
    build_volcano_exhibit()
    build_koblitz()
    build_binary_subfield_and_random()
    build_binary_supersingular()
    build_char3()
    build_odd_extensions()
    write_outputs()


if __name__ == "__main__":
    main()
