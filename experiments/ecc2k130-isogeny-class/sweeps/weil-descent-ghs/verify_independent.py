"""Sage-free re-derivation of the per-curve Weil-descent data, from ground_truth.json only.
Pure-Python GF(2^131) (modulus z^131+z^13+z^2+z+1, ints as bitmasks), pure-Python F2 ranks.
For every one of the 263 curves: sqrt(b) = b^(2^130); m = rank{(1, sqrt(b)^(2^i))}; d = rank{sqrt(b)^(2^i)};
Tr(b) = sum of conjugates; checks the gGHS witnesses in per_curve.json (g1*g2 = sqrt(b), both
trace 0, neither in F2 => Ord = Phi_131 => genus 2^130 - 1), and finds a non-trivial gGHS
decomposition for E0 (1 = g1 * g1^-1 with Tr g1 = Tr g1^-1 = 0).
Run: python3 verify_independent.py
"""
import json, random, sys, time
D = "/Volumes/SSD990/ecdlp-hardness-work/"
gt = json.load(open(D + "ground_truth/ground_truth.json"))
pc = json.load(open(D + "weil-descent-ghs/per_curve.json"))
n = 131
MOD = (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1
assert int(gt["meta"]["modulus_int"]) == MOD


def mul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        b >>= 1
        a <<= 1
        if a >> n:
            a ^= MOD
    return r


def sq(a):
    return mul(a, a)


def inv(a):
    # a^(2^131 - 2)
    r, e, base = 1, (1 << n) - 2, a
    while e:
        if e & 1:
            r = mul(r, base)
        base = sq(base)
        e >>= 1
    return r


def conj(a):
    out = [a]
    for _ in range(n - 1):
        out.append(sq(out[-1]))
    assert sq(out[-1]) == a
    return out


def trace(a):
    t = 0
    for c in conj(a):
        t ^= c
    assert t in (0, 1)
    return t


def rank(rows):
    piv, r = {}, 0
    for v in rows:
        while v:
            h = v.bit_length() - 1
            if h in piv:
                v ^= piv[h]
            else:
                piv[h] = v; r += 1; break
    return r


t0 = time.time()
res = {}
for c in gt["curves"]:
    lab = c["label"]
    b = int(c["b_int"])
    assert int(c["a2"]) == 0
    assert mul(b, int(c["j_int"])) == 1          # b = 1/j
    cb = conj(b)
    v = cb[-1]                                   # b^(2^130) = sqrt(b)
    assert sq(v) == b
    cv = conj(v)
    m = rank([(1 << n) | u for u in cv])
    d = rank(cv)
    tb = 0
    for u in cb:
        tb ^= u
    g = 2 ** (m - 1) if d == m else 2 ** (m - 1) - 1      # (x+1)|Ord_b  <=>  d == m
    assert pc[lab]["magic_number"] == m, lab
    assert pc[lab]["dim_span_conjugates_sqrt_b"] == d, lab
    assert pc[lab]["trace_b"] == tb, lab
    assert int(pc[lab]["ghs_genus"]) == g, lab
    w = pc[lab]["gghs_witness"]
    wit_ok = None
    if w is not None:
        g1, g2 = int(w["gamma1_int"]), int(w["gamma2_int"])
        assert mul(g1, g2) == v
        assert g1 not in (0, 1) and g2 not in (0, 1)
        assert trace(g1) == 0 and trace(g2) == 0
        # Ord = Phi_131 for trace-0 elements outside F2 (x^131+1 = (x+1)Phi_131, Phi_131 irreducible)
        assert rank(conj(g1)) == 130 and rank(conj(g2)) == 130
        gg = 2 ** 130 - 2 ** 0 - 2 ** 0 + 1
        assert int(w["genus"]) == gg
        wit_ok = True
    res[lab] = {"m": m, "d": d, "Tr_b": tb, "ghs_genus_log2_is_130": g == 2 ** 130, "witness_ok": wit_ok}

# E0: non-trivial gGHS decomposition 1 = g1 * g1^{-1}
rng = random.Random(7)
e0w = None
for _ in range(200):
    g1 = rng.getrandbits(n)
    if g1 in (0, 1):
        continue
    g2 = inv(g1)
    assert mul(g1, g2) == 1
    if trace(g1) == 0 and trace(g2) == 0:
        assert rank(conj(g1)) == 130 and rank(conj(g2)) == 130
        e0w = {"gamma1_int": str(g1), "gamma2_int": str(g2), "Ord_types": ["Phi131", "Phi131"],
               "genus": str(2 ** 130 - 1)}
        break
assert e0w is not None
from collections import Counter
summary = {"curves_checked": len(res),
           "m_counts": dict(Counter(str(r["m"]) for r in res.values())),
           "d_counts": dict(Counter(str(r["d"]) for r in res.values())),
           "trace_b_counts": dict(Counter(str(r["Tr_b"]) for r in res.values())),
           "ghs_genus_2^130_count": sum(r["ghs_genus_log2_is_130"] for r in res.values()),
           "gghs_witnesses_verified": sum(1 for r in res.values() if r["witness_ok"]),
           "E0_nontrivial_gghs_decomposition": e0w,
           "elapsed_s": round(time.time() - t0, 1)}
json.dump({"summary": summary, "curves": res}, open(D + "weil-descent-ghs/verify_independent.json", "w"), indent=1)
print(json.dumps(summary, indent=1))
