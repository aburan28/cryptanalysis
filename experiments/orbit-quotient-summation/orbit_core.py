"""Core helpers for the exact orbit-quotient summation toy experiment."""
from __future__ import annotations
import math, statistics, sys
from collections import Counter
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pdp-scaling"))
from gf2n import Curve, GF2n, INF, Point  # noqa: E402


def scalar(E, k, P):
    R, Q = INF, P
    while k:
        if k & 1:
            R = E.add(R, Q)
        Q = E.add(Q, Q)
        k >>= 1
    return R


def frob(E, P, k=1):
    return P if P.inf else Point(E.F.frob(P.x, k), E.F.frob(P.y, k))


def rank_f2(vs, n):
    piv = [0] * n
    rank = 0
    for v in vs:
        x = v
        while x:
            i = x.bit_length() - 1
            if piv[i]:
                x ^= piv[i]
            else:
                piv[i] = x
                rank += 1
                break
    return rank


def normal_conjugates(F, beta):
    out, x = [], beta
    for _ in range(F.n):
        out.append(x)
        x = F.sqr(x)
    if rank_f2(out, F.n) != F.n:
        raise ValueError("not a normal generator")
    return out


def quotient_basis(n, s):
    if (n - 1) % s:
        raise ValueError("s must divide n-1")
    mult = pow(2, s, n)
    unseen = set(range(1, n))
    cosets = []
    while unseen:
        x = min(unseen)
        orbit = []
        while x not in orbit:
            orbit.append(x)
            unseen.discard(x)
            x = x * mult % n
        cosets.append(orbit)
    if len(cosets) != s:
        raise ValueError("wrong cyclotomic coset count")
    return [1 | sum(1 << i for i in orbit) for orbit in cosets]


def payload_word(payload, basis):
    out = 0
    for i, b in enumerate(basis):
        if payload >> i & 1:
            out ^= b
    return out


def word_to_field(word, conjugates):
    out = 0
    for i, b in enumerate(conjugates):
        if word >> i & 1:
            out ^= b
    return out


def koblitz_order(n):
    a, b = 2, -1
    if n == 1:
        t = b
    else:
        for _ in range(2, n + 1):
            a, b = b, -b - 2 * a
        t = b
    return (1 << n) + 1 - t


def factor_reps(n, s, beta):
    F = GF2n(n)
    E = Curve(F, 1)
    conjugates = normal_conjugates(F, beta)
    basis = quotient_basis(n, s)
    r = koblitz_order(n) // 4
    reps = {}
    for payload in range(1, 1 << s):
        x = word_to_field(payload_word(payload, basis), conjugates)
        P = E.lift_x(x)
        if P is not None and scalar(E, r, P).inf:
            reps[payload] = P
    return E, r, reps


def dlog_bsgs(E, G, Q, r):
    """Tiny-group correctness oracle, not a proposed attack stage."""
    m = math.isqrt(r) + 1
    table = {}
    P = INF
    for j in range(m):
        table.setdefault(P, j)
        P = E.add(P, G)
    step = E.neg(scalar(E, m, G))
    gamma = Q
    for i in range(m + 1):
        if gamma in table:
            x = i * m + table[gamma]
            if x < r and scalar(E, x, G) == Q:
                return x
        gamma = E.add(gamma, step)
    raise ValueError("dlog not found")


def model(n, s, beta):
    E, r, reps = factor_reps(n, s, beta)
    keys = sorted(reps)
    G = reps[keys[0]]
    lam = dlog_bsgs(E, G, frob(E, G), r)
    scalars = {k: dlog_bsgs(E, G, P, r) for k, P in reps.items()}
    H = sorted({sign * pow(lam, a, r) % r for a in range(n) for sign in (1, -1)})
    if len(H) != 2 * n:
        raise AssertionError("unexpected signed Frobenius orbit size")
    return dict(n=n, s=s, beta=beta, r=r, lam=lam, keys=keys, scalars=scalars, H=H)


def slot_sets(M, arity, mode, phases):
    r, lam = M["r"], M["lam"]
    out = []
    for i in range(arity):
        d = {}
        for key, base in M["scalars"].items():
            if mode == "orbit":
                d[key] = {h * base % r for h in M["H"]}
            else:
                x = pow(lam, phases[i], r) * base % r
                d[key] = {x, -x % r}
        out.append(d)
    return out


def pair_index(A, B, keys, r):
    out = {}
    for a in keys:
        for b in keys:
            counts = Counter((x + y) % r for x in A[a] for y in B[b])
            for total, count in counts.items():
                out.setdefault(total, []).append((a, b, count))
    return out


def planted_targets(M, arity, count, phases, seed):
    import random
    rng = random.Random(seed)
    r, lam, keys = M["r"], M["lam"], M["keys"]
    targets, witnesses, seen = [], [], set()
    while len(targets) < count:
        ks = [rng.choice(keys) for _ in range(arity)]
        signs = [-1 if rng.randrange(2) else 1 for _ in range(arity)]
        t = sum(signs[i] * pow(lam, phases[i], r) * M["scalars"][ks[i]]
                for i in range(arity)) % r
        if not t:
            continue
        canon = min(h * t % r for h in M["H"])
        if canon in seen:
            continue
        seen.add(canon)
        targets.append(t)
        witnesses.append(dict(keys=ks, signs=signs))
    return targets, witnesses


def summarize(domain, witnesses):
    vals = list(witnesses.values())
    return dict(
        domain_key_tuples=domain,
        positive_key_tuples=len(vals),
        density=len(vals) / domain,
        witness_median=statistics.median(vals) if vals else 0,
        witness_mean=statistics.mean(vals) if vals else 0,
        witness_min=min(vals) if vals else 0,
        witness_max=max(vals) if vals else 0,
        single_witness_tuples=sum(v == 1 for v in vals),
    )


def m3_truths(M, targets, mode, phases=(0, 1, 2)):
    s, r, keys = M["s"], M["r"], M["keys"]
    sets = slot_sets(M, 3, mode, phases)
    pairs = pair_index(sets[0], sets[1], keys, r)
    truths = [bytearray(1 << (3 * s)) for _ in targets]
    stats = []
    for ti, target in enumerate(targets):
        W = {}
        for c in keys:
            for z in sets[2][c]:
                for a, b, count in pairs.get((target - z) % r, ()):
                    triple = (a, b, c)
                    W[triple] = W.get(triple, 0) + count
        for a, b, c in W:
            truths[ti][a | (b << s) | (c << (2 * s))] = 1
        stats.append(summarize(len(keys) ** 3, W))
    return truths, stats


def m4_stats(M, targets, mode, phases=(0, 1, 2, 3)):
    r, keys = M["r"], M["keys"]
    sets = slot_sets(M, 4, mode, phases)
    left = pair_index(sets[0], sets[1], keys, r)
    right = pair_index(sets[2], sets[3], keys, r)
    out = []
    for target in targets:
        W = {}
        for total, L in left.items():
            R = right.get((target - total) % r)
            if not R:
                continue
            for a, b, w1 in L:
                for c, d, w2 in R:
                    quad = (a, b, c, d)
                    W[quad] = W.get(quad, 0) + w1 * w2
        out.append(summarize(len(keys) ** 4, W))
    return out


def mobius_anf(truth, variables):
    a = bytearray(truth)
    for i in range(variables):
        bit = 1 << i
        for mask in range(1 << variables):
            if mask & bit:
                a[mask] ^= a[mask ^ bit]
    hist = Counter(mask.bit_count() for mask, v in enumerate(a) if v)
    return dict(degree=max(hist, default=-1), monomials=sum(hist.values()),
                degree_histogram=dict(sorted(hist.items())))


def monomial_masks(variables, degree):
    out = [0]
    for d in range(1, degree + 1):
        for pos in combinations(range(variables), d):
            mask = 0
            for i in pos:
                mask |= 1 << i
            out.append(mask)
    return out


def eval_row(x, columns):
    row, sub = 0, x
    while True:
        j = columns.get(sub)
        if j is not None:
            row |= 1 << j
        if sub == 0:
            return row
        sub = (sub - 1) & x


def degree_consistency(truths, keys, s, degree):
    """Exact interpolation on the valid-key domain K^3."""
    masks = monomial_masks(3 * s, degree)
    columns = {mask: i for i, mask in enumerate(masks)}
    pivots = {}
    inconsistent = 0
    for a in keys:
        for b in keys:
            for c in keys:
                x = a | (b << s) | (c << (2 * s))
                rhs = 0
                for i, truth in enumerate(truths):
                    if truth[x]:
                        rhs |= 1 << i
                coeff = eval_row(x, columns)
                while coeff:
                    p = coeff.bit_length() - 1
                    if p in pivots:
                        pc, pr = pivots[p]
                        coeff ^= pc
                        rhs ^= pr
                    else:
                        pivots[p] = (coeff, rhs)
                        break
                if not coeff:
                    inconsistent |= rhs
    return dict(
        degree=degree,
        monomials_at_most_degree=len(masks),
        evaluation_rank=len(pivots),
        domain_size=len(keys) ** 3,
        consistent=[not bool(inconsistent >> i & 1) for i in range(len(truths))],
    )


def poisson_prediction(n, r, arity):
    mu = (2 * n) ** arity / r
    return dict(mean_witnesses=mu, positive_probability=1 - math.exp(-mu))
