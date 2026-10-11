"""The exact selected-resieve correspondence, as a checkable lemma.

Lemma (selected resieve = selected thin product).
Fix a factor base of primes p <= y with weights w_p, a sieve interval of N
positions and J sieve lines, line j having root set R_p^(j) subset Z/p for
each p.  Let the *residue-state* index set be

    S = {(p, a) : p <= y, 0 <= a < p},      D = |S| = sum_{p<=y} p,

and define X in {0,1}^{N x D}, Y in Z^{D x J} by

    X[x, (p,a)] = [x = a mod p],      Y[(p,a), j] = w_p * [a in R_p^(j)].

Then for every position x and line j

    (XY)[x, j] = sum_{p<=y} w_p * #{a in R_p^(j) : x = a mod p}
              = the log-sieve score of position x on line j,

so recomputing the sieve score on a selected set W of (position, line) pairs
("resieving the survivors") is exactly the selected-entries problem for the
product XY with inner dimension D = sum_{p<=y} p = y^(2+o(1)).

Corollary (rank of the two-position kernel).
K[u, v] = sum_p w_p [u = v mod p] = (X diag(w) X^T)[u, v] depends on u - v
only, with Fourier support {1} u {zeta_p^a : 1 <= a < p, p <= y}; these
frequencies are pairwise distinct (a/p in lowest terms determines p), so when
N >= 1 + sum_p (p - 1) and all w_p > 0 the Vandermonde factorisation gives

    rank_C K = 1 + sum_{p<=y} (p - 1) = Theta(D).

Fourier expansion is therefore a basis change, not a compression.

What this module does.
  * Checks the identity (XY)[x,j] = sieve score exactly on random small
    instances (integers, no floating point).
  * Checks the rank corollary exactly (fraction-free elimination) for several
    prime sets and N both above and below the threshold.
  * Tabulates the inner-dimension screen: the largest factor-base bound y for
    which D = sum_{p<=y} p fits under the theorem's ceiling N^(1/18).

Everything printed is either `checked` (exhaustive/exact on the stated
instances) or `derived` (follows from the lemma and the stated premise).
"""

from __future__ import annotations

import json
import math
import os
import random
from fractions import Fraction

from avw_model import MAX_D_EXP

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "selected_resieve.json")


def primes_upto(y: int) -> list[int]:
    s = bytearray([1]) * (y + 1)
    s[0:2] = b"\x00\x00"
    for i in range(2, int(y**0.5) + 1):
        if s[i]:
            s[i * i :: i] = bytearray(len(s[i * i :: i]))
    return [i for i in range(y + 1) if s[i]]


def residue_states(primes: list[int]) -> list[tuple[int, int]]:
    return [(p, a) for p in primes for a in range(p)]


def build_X(n: int, primes: list[int]) -> list[list[int]]:
    states = residue_states(primes)
    return [[1 if x % p == a else 0 for (p, a) in states] for x in range(n)]


def build_Y(primes, root_sets, weights) -> list[list[int]]:
    states = residue_states(primes)
    lines = len(root_sets)
    return [[weights[p] if a in root_sets[j][p] else 0 for j in range(lines)] for (p, a) in states]


def sieve_scores(n, primes, root_sets, weights) -> list[list[int]]:
    """Direct log-sieve: for each line, each prime, each root, stride through."""
    lines = len(root_sets)
    score = [[0] * lines for _ in range(n)]
    for j in range(lines):
        for p in primes:
            for r in root_sets[j][p]:
                for x in range(r % p, n, p):
                    score[x][j] += weights[p]
    return score


def matmul(A, B):
    return [[sum(a * b for a, b in zip(row, col)) for col in zip(*B)] for row in A]


def exact_rank(M) -> int:
    """Rank over Q by fraction-free Gaussian elimination."""
    rows = [[Fraction(v) for v in r] for r in M]
    rank = 0
    ncols = len(rows[0]) if rows else 0
    for c in range(ncols):
        piv = next((i for i in range(rank, len(rows)) if rows[i][c] != 0), None)
        if piv is None:
            continue
        rows[rank], rows[piv] = rows[piv], rows[rank]
        pv = rows[rank][c]
        for i in range(len(rows)):
            if i != rank and rows[i][c] != 0:
                f = rows[i][c] / pv
                rows[i] = [a - f * b for a, b in zip(rows[i], rows[rank])]
        rank += 1
    return rank


def check_identity(rng: random.Random, trials: int = 40) -> dict:
    worst = None
    for t in range(trials):
        y = rng.choice([5, 7, 11, 13])
        primes = primes_upto(y)
        n = rng.randint(1, 60)
        lines = rng.randint(1, 4)
        weights = {p: rng.randint(1, 50) for p in primes}
        root_sets = [
            {p: set(rng.sample(range(p), rng.randint(0, min(2, p)))) for p in primes} for _ in range(lines)
        ]
        X = build_X(n, primes)
        Y = build_Y(primes, root_sets, weights)
        if matmul(X, Y) != sieve_scores(n, primes, root_sets, weights):
            raise AssertionError(f"identity failed: y={y} n={n} lines={lines}")
        worst = max(worst or 0, n * sum(primes))
    return {"trials": trials, "status": "checked", "largest_N_times_D": worst}


def check_rank(rng: random.Random) -> list[dict]:
    rows = []
    for primes in ([2, 3], [2, 3, 5], [3, 5, 7], [2, 3, 5, 7], [2, 3, 5, 7, 11]):
        D = sum(primes)
        predicted = 1 + sum(p - 1 for p in primes)
        for n in (predicted - 3, predicted, predicted + 6):
            if n < 1:
                continue
            weights = {p: rng.randint(1, 9) for p in primes}
            X = build_X(n, primes)
            K = [[sum(weights[p] * (1 if u % p == v % p else 0) for p in primes) for v in range(n)] for u in range(n)]
            # K must equal X diag(w) X^T exactly.
            XW = [[X[u][k] * weights[residue_states(primes)[k][0]] for k in range(D)] for u in range(n)]
            assert matmul(XW, [list(c) for c in zip(*X)]) == K
            r = exact_rank(K)
            expect = predicted if n >= predicted else n
            rows.append(
                {
                    "primes": primes,
                    "D": D,
                    "N": n,
                    "rank": r,
                    "predicted_1_plus_sum_p_minus_1": predicted,
                    "status": "checked" if r == expect else "MISMATCH",
                }
            )
            if r != expect:
                raise AssertionError(rows[-1])
    return rows


def frequencies_distinct(primes) -> bool:
    freqs = [Fraction(0)] + [Fraction(a, p) for p in primes for a in range(1, p)]
    return len(set(freqs)) == len(freqs) == 1 + sum(p - 1 for p in primes)


def inner_dimension_screen() -> list[dict]:
    """Largest y with sum_{p<=y} p <= N^(1/18) for sieve sizes N = 2^k."""
    out = []
    primes = primes_upto(200_000)
    for k in (32, 48, 64, 96, 128, 192, 256, 384, 512):
        ceiling = 2.0 ** (k * MAX_D_EXP)
        D = 0
        y = None
        for p in primes:
            if D + p > ceiling:
                break
            D += p
            y = p
        else:
            raise RuntimeError("prime table too short for this ceiling")
        out.append({"log2_N": k, "D_ceiling_N^(1/18)": ceiling, "max_y": y, "D_at_max_y": D, "status": "checked"})
    return out


def main() -> None:
    rng = random.Random(20261006)
    result = {
        "lemma": "selected resieve on W == selected entries of XY, inner dimension D = sum_{p<=y} p",
        "identity_check": check_identity(rng),
        "rank_check": check_rank(rng),
        "frequencies_distinct_checked_for": [
            {"primes": ps, "distinct": frequencies_distinct(ps)} for ps in ([2, 3, 5], [2, 3, 5, 7, 11, 13])
        ],
        "inner_dimension_screen": inner_dimension_screen(),
        "derived": [
            "D = sum_{p<=y} p = y^2/(2 ln y) (1+o(1)), so the theorem's D <= N^(1/18) ceiling bounds the factor base by y <= N^(1/36+o(1)).",
            "rank_C K = Theta(D): any exact linear compression of the residue-state representation needs Theta(D) coordinates.",
        ],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(result, fh, indent=1)
    print(json.dumps(result["identity_check"]))
    for r in result["rank_check"]:
        print(f"primes={r['primes']} D={r['D']} N={r['N']} rank={r['rank']} predicted={r['predicted_1_plus_sum_p_minus_1']} {r['status']}")
    for r in result["inner_dimension_screen"]:
        print(f"N=2^{r['log2_N']}: D ceiling {r['D_ceiling_N^(1/18)']:.1f} -> max factor-base bound y={r['max_y']} (D={r['D_at_max_y']})")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
