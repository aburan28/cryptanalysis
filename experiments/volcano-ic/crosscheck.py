"""Independent cross-check of the tier-A census, written without Sage or ic.sage.

    python3 crosscheck.py        (or: sage -python crosscheck.py)

F_2^19 arithmetic uses log/antilog tables over the modulus in run.sage. The
script recomputes the isogeny class, then every curve's factor base, Z/4 tags,
eligible pairs and exact yield, and compares them with results/census-*.jsonl.
Two further checks use the same arithmetic:

- subspaces: E0 and two descendants, each over 456 random factor-base
  subspaces g*V, to separate the curve from the draw of V;
- s3: every solution of S3(x1, x2, xR) = 0 in V x V for random E0 targets,
  sorted into genuine, twist and x = 0 (2-torsion) solutions.

Writes results/crosscheck.json.
"""
import glob
import json
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
M, K = 19, 10
Q = 1 << M
Q1 = Q - 1                  # 2^19 - 1 is prime, so z generates F_2^19*
MODULUS = sum(1 << e for e in (19, 18, 16, 11, 8, 6, 4, 1, 0))    # MODULUS in run.sage
ORDER = 523492
P_SUB = ORDER // 4
CLASSES = (P_SUB - 1) // 2
TRACE = Q + 1 - ORDER       # 797

EXP = np.zeros(Q1, dtype=np.int64)
_a = 1
for _i in range(Q1):
    EXP[_i] = _a
    _a <<= 1
    if _a >> M:
        _a ^= MODULUS
LOG = np.zeros(Q, dtype=np.int64)
LOG[EXP] = np.arange(Q1)


def mul(a, b):
    return np.where((a == 0) | (b == 0), 0, EXP[(LOG[a] + LOG[b]) % Q1])


def div(a, b):
    # Callers never divide by zero; a zero numerator gives zero.
    return np.where(a == 0, 0, EXP[(LOG[a] - LOG[b]) % Q1])


def sq(a):
    return np.where(a == 0, 0, EXP[(2 * LOG[a]) % Q1])


def sqrt(a):
    return np.where(a == 0, 0, EXP[(LOG[a] * ((Q1 + 1) // 2)) % Q1])


def _traceMask():
    t = EXP[:M].copy()                      # z^0 ... z^(M-1)
    acc = t.copy()
    for _ in range(M - 1):
        t = sq(t)
        acc ^= t
    assert set(acc.tolist()) <= {0, 1}
    return sum(int(v) << i for i, v in enumerate(acc))


TMASK = _traceMask()
PARITY = np.array([bin(i).count('1') & 1 for i in range(1 << 16)], dtype=np.int64)


def tr(a):
    a = a & TMASK
    return PARITY[a & 0xFFFF] ^ PARITY[a >> 16]


def halfTrace(c):
    # M is odd: H(c) = sum c^(4^i) solves w^2 + w = c whenever Tr(c) = 0.
    acc, s = c.copy(), c.copy()
    for _ in range((M - 1) // 2):
        s = sq(sq(s))
        acc ^= s
    return acc


def parsePoly(text):
    """'z^17 + z^15 + ... + 1' (Sage or PARI) -> integer bit vector."""
    out = 0
    for term in text.replace(' ', '').split('+'):
        if term == '1':
            out ^= 1
        elif term == 'z':
            out ^= 2
        else:
            out ^= 1 << int(re.fullmatch(r'z\^(\d+)', term).group(1))
    return out


def isogenyClass():
    """Every b with #E_b = ORDER, for E_b: y^2 + xy = x^3 + b.

    #E_b = Q + 1 + S(b) with S(b) = sum_{x != 0} (-1)^Tr(x + b/x^2). Writing
    x = z^i, b = z^k and j = 2i (2 is invertible mod Q1) makes S a cyclic
    convolution of length Q1, so one FFT gives S for every b."""
    chi = 1.0 - 2.0 * tr(EXP)
    f = chi[(np.arange(Q1) * ((Q1 + 1) // 2)) % Q1]      # (-1)^Tr(z^(j/2))
    S = np.rint(np.fft.ifft(np.fft.fft(f) * np.fft.fft(chi)).real).astype(np.int64)
    return {int(b) for b in EXP[np.nonzero(S == -TRACE)[0]]}


def census(b, V):
    """Factor base {one point per x in V, x != 0}, its Z/4 tags, and the exact yield."""
    bb = np.full_like(V, b)
    c = V ^ div(bb, sq(V))
    on = tr(c) == 0
    x = V[on]
    y = mul(x, halfTrace(c[on]))
    # a = 0: P lies in 2E iff Tr(x) = 0. For such P = (u, v) the halves have
    # x^2 = v + u(l + 1) with l^2 + l = u, and they lie in 2E (P in 4E, tag 0)
    # iff that has trace 0.
    odd = tr(x) == 1
    tag0 = ~odd & (tr(y ^ mul(x, halfTrace(x) ^ 1)) == 0)
    tag2 = ~odd & ~tag0
    # Give every odd point the tag of T4 = (b^(1/4), y4): P and T4 differ in
    # tag by 2 exactly when P + T4 has tag 0, and then -P has T4's tag.
    x4 = int(sqrt(sqrt(np.array([b])))[0])
    y4 = int(mul(np.array([x4]), halfTrace(np.array([x4 ^ int(sq(np.array([x4]))[0])])))[0])
    xo, yo = x[odd], y[odd]
    lam = div(yo ^ y4, xo ^ x4)
    x3 = sq(lam) ^ lam ^ xo ^ x4
    y3 = mul(lam, xo ^ x3) ^ x3 ^ yo
    flip = (tr(x3) == 0) & (tr(y3 ^ mul(x3, halfTrace(x3) ^ 1)) == 0)
    flip = np.where(xo == x4, yo != y4, flip)       # P = +-T4: the chord formula degenerates
    yo = np.where(flip, yo ^ xo, yo)

    def pairX(xa, ya, withSum):
        i, j = np.triu_indices(len(xa), 1)
        x1, y1, x2, y2 = xa[i], ya[i], xa[j], ya[j]
        lm = div(y1 ^ y2 ^ x2, x1 ^ x2)              # P1 - P2
        out = [sq(lm) ^ lm ^ x1 ^ x2]
        if withSum:
            lp = div(y1 ^ y2, x1 ^ x2)               # P1 + P2
            out.append(sq(lp) ^ lp ^ x1 ^ x2)
        return out

    targets = []
    for mask in (tag0, tag2):
        xa, ya = x[mask], y[mask]
        targets += pairX(xa, ya, True)
        targets.append(sq(xa) ^ div(np.full_like(xa, b), sq(xa)))       # 2P
    targets += pairX(xo, yo, False)
    allX = np.concatenate(targets)
    n0, n2, nOdd = int(tag0.sum()), int(tag2.sum()), int(odd.sum())
    assert len(allX) == n0 * n0 + n2 * n2 + nOdd * (nOdd - 1) // 2
    return {'fb_size': int(on.sum()), 'tags': [n0, n2, nOdd], 'eligible': int(len(allX)),
            'distinct_targets': int(len(np.unique(allX)))}


def loadCensus():
    out = {}
    for path in sorted(glob.glob(os.path.join(HERE, 'results', 'census-*.jsonl'))):
        for line in open(path):
            if line.strip():
                r = json.loads(line)
                out[parsePoly(r['b'])] = r
    return out


def checkCensus(records, V):
    listed = {parsePoly(m.group(1)) for m in re.finditer(r'\[([^\[\],]+),\s*0\]',
                                                          open(os.path.join(HERE, 'data', 'isoclass19.txt')).read())}
    found = isogenyClass()
    mismatches, results = [], {}
    for b, rec in sorted(records.items()):
        mine = census(b, V)
        t = rec['tag_counts']
        theirs = {'fb_size': rec['fb_size'], 'tags': [t[0], t[2], t[1] + t[3]],
                  'eligible': rec['eligible_signed_pairs'], 'distinct_targets': rec['distinct_targets']}
        if mine != theirs:
            mismatches.append({'curve': rec['curve'], 'crosscheck': mine, 'census': theirs})
        results[rec['curve']] = mine
    return {'isogeny_class_size': len(found), 'matches_isoclass19': found == listed,
            'census_records_matching_class': set(records) == found,
            'curves_compared': len(records), 'exact_matches': len(records) - len(mismatches),
            'fields_compared': ['fb_size', 'tag counts (n0, n2, n_odd)', 'eligible_signed_pairs', 'distinct_targets'],
            'mismatches': mismatches}, results


def inTraceZero(W):
    return bool((tr(W) == 0).all())


def attempts(r):
    return (r['fb_size'] + 10) / (r['distinct_targets'] / CLASSES)


def subspaces(records, V, draws=456, seed=7):
    """Each curve over random subspaces g*V: how much of its |F| is the draw of V?

    A draw with g*V inside the trace-zero hyperplane (probability 2^-10) makes
    every factor-base point halvable; see traceZero(). Such draws are counted
    and left out of the summary statistics."""
    rng = np.random.default_rng(seed)
    desc = [r for r in records.values() if r['curve'] != 'E0']
    picks = {'E0': 1,
             'lowest_yield': parsePoly(min(desc, key=lambda r: r['exact_decomp_prob'])['b']),
             'median_fb_size': parsePoly(sorted(desc, key=lambda r: (r['fb_size'], r['curve']))[len(desc) // 2]['b'])}
    out = {}
    for label, b in picks.items():
        rec = records[b]
        fb, att, tz = [], [], []
        for g in rng.integers(2, Q, size=draws):
            W = mul(np.full_like(V, g), V)
            if inTraceZero(W):
                tz.append(attempts(census(b, W)))
                continue
            r = census(b, W)
            fb.append(r['fb_size'])
            att.append(attempts(r))
        fb, att = np.array(fb), np.array(att)
        out[label] = {'curve': rec['curve'], 'draws': draws, 'trace_zero_draws_attempts': tz,
                      'fb_size_mean': float(fb.mean()), 'fb_size_sd': float(fb.std(ddof=1)),
                      'attempts_mean': float(att.mean()), 'attempts_sd': float(att.std(ddof=1)),
                      'fb_size_on_V': rec['fb_size'],
                      'fb_size_on_V_percentile': float(100 * np.mean(fb < rec['fb_size']))}
    fbV = np.array([r['fb_size'] for r in desc])
    attV = np.array([r['expected_attempts_per_dlp'] for r in desc])
    out['descendants_on_V'] = {'curves': len(desc), 'fb_size_mean': float(fbV.mean()), 'fb_size_sd': float(fbV.std(ddof=1)),
                               'attempts_mean': float(attV.mean()), 'attempts_sd': float(attV.std(ddof=1))}
    return out


def traceZero(records, V):
    """Every curve on W = g*V with W inside ker Tr, for the smallest such g.

    With a = 0, a point lies in 2E iff Tr(x) = 0, so on W every factor-base
    point has an even Z/4 tag. Odd pairs, which give one prime-subgroup
    combination instead of two, disappear, and eligible = n0^2 + n2^2."""
    G = np.arange(Q, dtype=np.int64)
    ok = np.ones(Q, dtype=bool)
    for i in range(K):
        ok &= tr(mul(G, np.full_like(G, 1 << i))) == 0
    g = int(np.nonzero(ok[2:])[0][0]) + 2
    W = mul(np.full_like(V, g), V)
    assert inTraceZero(W)
    perCurve, oddTags = {}, 0
    for b, rec in records.items():
        r = census(b, W)
        oddTags += r['tags'][2]
        perCurve[rec['curve']] = {'fb_size': r['fb_size'], 'exact_decomp_prob': r['distinct_targets'] / CLASSES,
                                  'expected_attempts_per_dlp': attempts(r)}
    att = np.array([v['expected_attempts_per_dlp'] for v in perCurve.values()])
    attV = np.array([r['expected_attempts_per_dlp'] for r in records.values()])
    return {'g': ' + '.join(f'z^{i}' if i > 1 else ('z' if i else '1')
                            for i in reversed(range(M)) if g >> i & 1),
            'solutions_g': int(ok[1:].sum()), 'odd_tags_total': oddTags,
            'attempts_mean': float(att.mean()), 'attempts_range': [float(att.min()), float(att.max())],
            'attempts_mean_on_V': float(attV.mean()), 'e0_attempts': perCurve['E0']['expected_attempts_per_dlp'],
            'per_curve': perCurve}


def randomSubgroupX(b, n, rng):
    """x-coordinates of uniform points of 4E = the order-p subgroup (x-only doubling)."""
    x = rng.integers(1, Q, size=4 * n)
    x = x[tr(x ^ div(np.full_like(x, b), sq(x))) == 0][:n]
    double = lambda u: sq(u) ^ div(np.full_like(u, b), sq(u))
    return double(double(x))


def s3Solutions(b, exactProb, targets=20000, seed=11):
    """All (x1, x2) in V x V with S3(x1, x2, xR) = 0, from S3 as a quadratic in x2:
    (x1 + xR)^2 x2^2 + x1 xR x2 + (x1 xR)^2 + b = 0."""
    rng = np.random.default_rng(seed)
    V = np.arange(1 << K, dtype=np.int64)            # includes x1 = 0
    onCurve = lambda x: (x != 0) & (tr(x ^ div(np.full_like(x, b), sq(x))) == 0)
    counts = {'genuine': 0, 'x_is_zero': 0, 'twist': 0}
    solvable = 0
    for xr in randomSubgroupX(b, targets, rng).tolist():
        xrv = np.full_like(V, xr)
        A, B = sq(V ^ xrv), mul(V, xrv)
        C = sq(mul(V, xrv)) ^ b
        x1s, x2s = [], []
        quad = (A != 0) & (B != 0)
        d = div(mul(A[quad], C[quad]), sq(B[quad]))
        ok = tr(d) == 0
        scale = div(B[quad][ok], A[quad][ok])
        r0 = mul(scale, halfTrace(d[ok]))
        for r in (r0, r0 ^ scale):
            x1s.append(V[quad][ok]), x2s.append(r)
        lin = (A == 0) & (B != 0)                     # x1 = xR
        x1s.append(V[lin]), x2s.append(div(C[lin], B[lin]))
        dbl = (A != 0) & (B == 0)                     # x1 = 0: x2 = sqrt(b) / xR
        x1s.append(V[dbl]), x2s.append(sqrt(div(C[dbl], A[dbl])))
        x1, x2 = np.concatenate(x1s), np.concatenate(x2s)
        keep = x2 < (1 << K)
        x1, x2 = x1[keep], x2[keep]
        zero = (x1 == 0) | (x2 == 0)
        good = ~zero & onCurve(x1) & onCurve(x2)
        counts['x_is_zero'] += int(zero.sum())
        counts['genuine'] += int(good.sum())
        counts['twist'] += int((~zero & ~good).sum())
        solvable += bool(good.any())
    share = solvable / targets
    return {'curve': 'E0', 'targets': targets, 'solutions': counts,
            'solvable_share': share, 'solvable_share_se': float(np.sqrt(share * (1 - share) / targets)),
            'exact_decomp_prob': exactProb,
            'x_is_zero_per_system': counts['x_is_zero'] / targets,
            'x_is_zero_per_system_theory': 2 * ((1 << K) - 1) / Q1}


def main():
    V = np.arange(1, 1 << K, dtype=np.int64)         # x in span{1, ..., z^9}, x != 0
    records = loadCensus()
    out = {'modulus': 'Z^19 + Z^18 + Z^16 + Z^11 + Z^8 + Z^6 + Z^4 + Z + 1'}
    out['census'], _ = checkCensus(records, V)
    out['subspaces'] = subspaces(records, V)
    out['trace_zero'] = traceZero(records, V)
    out['s3'] = s3Solutions(1, records[1]['exact_decomp_prob'])
    with open(os.path.join(HERE, 'results', 'crosscheck.json'), 'w') as fh:
        json.dump(out, fh, indent=2)
    brief = dict(out, trace_zero={k: v for k, v in out['trace_zero'].items() if k != 'per_curve'})
    print(json.dumps(brief, indent=2))


if __name__ == '__main__':
    main()
