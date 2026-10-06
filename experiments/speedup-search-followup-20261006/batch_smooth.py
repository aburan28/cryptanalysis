"""Decisive batch-smoothness screen for explicit candidate sets.

Statement being shipped.
Let y be the factor-base bound, W an explicit multiset of candidate norm
values of bit length <= L, and D = sum_{p<=y} p = y^(2+o(1)) the residue-state
inner dimension of the selected-resieve product (selected_resieve.py).
Bernstein's batch smooth-parts algorithm ("How to find smooth parts of
integers", 2004) computes the y-smooth part of every w in W in

    O~(b) bit operations,   b = sum_{p<=y} log p + sum_{w in W} log |w|
                             = y^(1+o(1)) + |W| L,

and a descent through the factor-base product tree returns the prime labels
and exponent vectors of accepted values with polylogarithmic overhead per
output symbol.  With L = O(log N) this is O~(D^(1/2) + |W|) word operations.
Against the AVW route (avw_model.py: N^2/D^0.063 + |W| D^0.437):

  * in the preprocessing-dominated range |W| <= N^2 / sqrt(D) the direct
    method costs at most O~(N^2/sqrt(D)) and AVW at least N^2/D^0.063, so
    the direct method is faster by D^(0.437 - o(1));
  * outside that range the AVW query term |W| D^0.437 already exceeds the
    direct method's linear |W| term.

So for *explicit* candidates with fixed or slowly growing norm degree the
exact method dominates everywhere AVW is defined, and returns strictly more
(cofactors, exponent vectors).  This is a scoped dominance statement: it says
nothing about candidate sets that are implicit, or whose norms are not cheap
to write down.

What this module does.
  * Implements product tree / remainder tree smooth-parts (gmpy2 if present,
    Python ints otherwise) and checks it against trial division on random
    candidates (exact).
  * Implements the product-tree descent that recovers exponent vectors for
    accepted values and checks them by recomputation (exact).
  * Measures wall time of the batch test as |W| and y grow, so the
    quasi-linear scaling is a measurement rather than a citation
    (measurement, this host, Python-level; reported as a scaling diagnostic).
  * Evaluates the two cost models over a grid and reports the dominance
    factor (derived from the premise exponents).
"""

from __future__ import annotations

import json
import math
import os
import random
import time

from avw_model import MAX_D_EXP, PRE_EXP, QUERY_EXP
from selected_resieve import primes_upto

try:
    import gmpy2
    from gmpy2 import mpz

    BACKEND = f"gmpy2 {gmpy2.version()}"
except Exception:  # pragma: no cover - fallback path
    mpz = int
    BACKEND = "python-int"

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "batch_smooth.json")


def product_tree(leaves):
    tree = [[mpz(v) for v in leaves]]
    while len(tree[-1]) > 1:
        lvl = tree[-1]
        tree.append([lvl[i] * lvl[i + 1] if i + 1 < len(lvl) else lvl[i] for i in range(0, len(lvl), 2)])
    return tree


def remainder_tree(z, tree):
    """Return [z mod leaf for leaf in tree[0]] using the product tree."""
    rems = [mpz(z) % tree[-1][0]]
    for level in range(len(tree) - 2, -1, -1):
        nxt = []
        for i, node in enumerate(tree[level]):
            nxt.append(rems[i // 2] % node)
        rems = nxt
    return rems


def smooth_parts(primes, values):
    """Bernstein's algorithm: y-smooth part of every value, batch."""
    if not values:
        return []
    z = product_tree(primes)[-1][0]
    tree = product_tree(values)
    rems = remainder_tree(z, tree)
    out = []
    for w, r in zip(tree[0], rems):
        if w <= 1:
            out.append(mpz(1))
            continue
        # repeated squaring until 2^(2^e) >= w covers every prime-power exponent
        e = max(1, int(w.bit_length() - 1).bit_length())
        x = r
        for _ in range(e):
            x = (x * x) % w
        out.append(math.gcd(int(x), int(w)))
    return [mpz(s) for s in out]


def descend_exponents(w, ptree, prime_index):
    """Exponent vector of a y-smooth w by descending the factor-base product tree.

    Only the branches whose subtree product shares a factor with w are
    visited, so the work is output-sensitive up to the tree depth.
    """
    exps = {}
    stack = [(len(ptree) - 1, 0, mpz(w))]
    while stack:
        level, idx, rem = stack.pop()
        node = ptree[level][idx]
        g = math.gcd(int(rem), int(node))
        if g == 1:
            continue
        if level == 0:
            p = int(node)
            k = 0
            while rem % p == 0:
                rem //= p
                k += 1
            exps[prime_index[p]] = k
            continue
        for child in (2 * idx, 2 * idx + 1):
            if child < len(ptree[level - 1]):
                stack.append((level - 1, child, rem))
    return exps


def trial_smooth_part(primes, w):
    w = int(w)
    s = 1
    for p in primes:
        while w % p == 0:
            w //= p
            s *= p
        if w == 1:
            break
    return s


def correctness(rng: random.Random) -> dict:
    checks = 0
    for y in (50, 300, 2000):
        primes = primes_upto(y)
        ptree = product_tree(primes)
        pidx = {p: i for i, p in enumerate(primes)}
        values = []
        for _ in range(300):
            kind = rng.random()
            if kind < 0.4:  # fully smooth, with repeated primes
                v = 1
                for _ in range(rng.randint(1, 12)):
                    v *= rng.choice(primes)
            elif kind < 0.7:  # smooth times one large prime
                v = rng.choice(primes) ** rng.randint(1, 5) * (y * 7 + 6 * rng.randint(1, 50) + 1)
            else:
                v = rng.getrandbits(rng.randint(8, 120)) | 1
            values.append(v)
        sp = smooth_parts(primes, values)
        for v, s in zip(values, sp):
            if int(s) != trial_smooth_part(primes, v):
                raise AssertionError(f"smooth part mismatch y={y} v={v}")
            if int(s) == v and v > 1:
                ex = descend_exponents(v, ptree, pidx)
                recon = 1
                for i, k in ex.items():
                    recon *= primes[i] ** k
                if recon != v:
                    raise AssertionError(f"exponent descent mismatch v={v}")
            checks += 1
    return {"values_checked": checks, "status": "checked", "backend": BACKEND}


def scaling(rng: random.Random) -> list[dict]:
    rows = []
    for y, logW, L in ((2**12, 10, 64), (2**12, 12, 64), (2**12, 14, 64), (2**12, 16, 64),
                       (2**14, 14, 64), (2**16, 14, 64), (2**18, 14, 64), (2**20, 14, 64),
                       (2**16, 14, 128), (2**16, 14, 256)):
        primes = primes_upto(y)
        values = [rng.getrandbits(L) | 1 for _ in range(2**logW)]
        best = None
        for _ in range(3):
            t0 = time.perf_counter()
            sp = smooth_parts(primes, values)
            dt = time.perf_counter() - t0
            best = dt if best is None else min(best, dt)
        b_bits = sum(p.bit_length() for p in primes) + len(values) * L
        rows.append(
            {
                "y": y,
                "num_primes": len(primes),
                "log2_W": logW,
                "L_bits": L,
                "b_bits": b_bits,
                "min_wall_s_of_3": round(best, 4),
                "ns_per_b_bit": round(best * 1e9 / b_bits, 2),
                "accepted_fully_smooth": sum(1 for v, s in zip(values, sp) if int(s) == v),
            }
        )
        print(f"y=2^{int(math.log2(y))} |W|=2^{logW} L={L}: {best:.3f}s  ({rows[-1]['ns_per_b_bit']} ns per bit of b)")
    return rows


def dominance_grid() -> list[dict]:
    """Cost exponents in base N.  D = N^d, |W| = N^w; L = O(log N) words."""
    rows = []
    for d in (MAX_D_EXP / 4, MAX_D_EXP / 2, MAX_D_EXP):
        for w in (0.0, 0.5, 1.0, 2.0 - d / 2, 2.0 - d / 4, 2.0):
            direct = max(d / 2, w)
            avw_pre = 2.0 - PRE_EXP * d
            avw_query = w + QUERY_EXP * d
            avw = max(avw_pre, avw_query)
            rows.append(
                {
                    "d_exp": round(d, 5),
                    "w_exp": round(w, 5),
                    "in_preprocessing_range": w <= 2.0 - d / 2 + 1e-12,
                    "direct_exp": round(direct, 5),
                    "avw_pre_exp": round(avw_pre, 5),
                    "avw_query_exp": round(avw_query, 5),
                    "avw_exp": round(avw, 5),
                    "advantage_exp_over_D": round((avw - direct) / d, 4) if d else None,
                }
            )
    return rows


def main() -> None:
    rng = random.Random(20261006)
    res = {
        "statement": "explicit candidate sets: batch smooth-parts O~(D^1/2 + |W|) dominates AVW N^2/D^0.063 + |W| D^0.437 by D^(0.437-o(1)) in the preprocessing range, and by the query term outside it",
        "premise": {"PRE_EXP": PRE_EXP, "QUERY_EXP": QUERY_EXP, "MAX_D_EXP": MAX_D_EXP},
        "correctness": correctness(rng),
        "scaling_measurement": scaling(rng),
        "dominance_grid_derived": dominance_grid(),
        "host_note": "scaling rows are Python/gmpy2 wall times on a shared 4-vCPU cloud VM; they establish growth shape, not a speed claim",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res["correctness"]))
    for r in res["dominance_grid_derived"]:
        if r["in_preprocessing_range"]:
            print(f"d={r['d_exp']} w={r['w_exp']}: direct N^{r['direct_exp']} vs AVW N^{r['avw_exp']}  -> AVW slower by D^{r['advantage_exp_over_D']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
