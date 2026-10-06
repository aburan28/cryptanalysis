"""G2 items (1)-(7a): Tr(b), Ord_b, Ord_sqrt(b), magic number m, GHS genus, gGHS minimum
over realizable decompositions, halving criterion vs #E = 4N, for all 263 curves.

Primary computation: own pure-Python F_2 linear algebra (f2lin.py).
Second implementation: Sage GF(2) matrices of the squaring map (Frobenius matrix M),
Ord via "smallest divisor d of x^131+1 with d(M) v = 0", ranks via Sage .rank().
Curves come from ground_truth/ecc2k.py load().  Nothing from weil-descent-ghs/*.py is used;
its JSON outputs are only read for the comparison at the end.

Run:  export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp
      timeout 2400 sage -python ghs_all_curves.py
"""
import sys, json, time, random, hashlib
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
OUT = "/Volumes/SSD990/ecdlp-hardness-work/gaps/G2-verify-weil-descent-ghs"
sys.path.insert(0, OUT)
import ecc2k
import f2lin as F
from sage.all import GF, PolynomialRing, matrix, vector, ZZ, prod
from itertools import combinations

T0 = time.time()
K, curves = ecc2k.load()
LABELS = ecc2k.LABELS
n = 131
X131 = (1 << 131) | 1                         # x^131 + 1
XP1 = 0b11                                    # x + 1
PHI, r = F.pdivmod(X131, XP1)                 # Phi_131 = (x^131+1)/(x+1)
assert r == 0 and F.pdeg(PHI) == 130

# ---------------------------------------------------------------- Sage second implementation
R = PolynomialRing(GF(2), "x"); x = R.gen()
fac = (x**131 + 1).factor()
fac_list = [(g, e) for g, e in fac]
assert all(e == 1 for _, e in fac_list)
divisors = sorted({prod(S, R(1)) for k in range(len(fac_list) + 1)
                   for S in combinations([g for g, _ in fac_list], k)}, key=lambda d: d.degree())
# Frobenius (squaring) matrix on the polynomial basis: column j = vec(z^(2j))
def vec(u_int):
    return vector(GF(2), [(u_int >> i) & 1 for i in range(n)])
M = matrix(GF(2), n, n)
for j in range(n):
    col = F.fsqr(1 << j)
    for i in range(n):
        if (col >> i) & 1:
            M[i, j] = 1
assert M ** 131 == matrix.identity(GF(2), n), "sigma^131 != id"
dM = {d: d(M) for d in divisors}


def sage_ord(u_int):
    v = vec(u_int)
    for d in divisors:                       # sorted by degree; Ord is the unique minimal one
        if dM[d] * v == 0:
            return d
    raise AssertionError


def sage_m(sqrt_b_int):
    rows = []
    c = sqrt_b_int
    for _ in range(n):
        rows.append([1] + [(c >> i) & 1 for i in range(n)])
        c = F.fsqr(c)
    return matrix(GF(2), rows).rank()


def poly_to_int(P):
    return sum(int(cf) << i for i, cf in enumerate(P.list()))


def ord_type(u_int):
    """class of Ord_u among divisors of x^131+1, from the trace (used for realizability)"""
    if u_int == 0:
        return "1"
    if u_int == 1:
        return "x+1"
    return "Phi131" if F.ftrace(u_int) == 0 else "x^131+1"


TYPE_POLY = {"x+1": XP1, "Phi131": PHI, "x^131+1": X131}

rng = random.Random(20260924)
per = {}
for lab in LABELS:
    E = curves[lab]
    a1, a2, a3, a4, a6 = E.a_invariants()
    assert (a1, a3, a4) == (1, 0, 0)
    a2i, b = int(a2.to_integer()), int(a6.to_integer())
    assert str(b) == ecc2k.RECORDS[lab]["b_int"] and a2i == int(ecc2k.RECORDS[lab]["a2"])
    # (1) trace
    tr_b = F.ftrace(b)
    assert tr_b == int(a6.trace())                     # Sage cross-check
    # (2),(3) Ord via own Krylov
    sb = F.fsqrt(b)
    assert sb == int(a6.sqrt().to_integer())
    ob, osb = F.ord_poly(b), F.ord_poly(sb)
    assert F.apply_poly_sigma(ob, b) == 0 and F.apply_poly_sigma(osb, sb) == 0
    # Sage second implementation
    ob_s, osb_s = sage_ord(b), sage_ord(sb)
    assert poly_to_int(ob_s) == ob and poly_to_int(osb_s) == osb, lab
    # (4) magic number
    m = F.magic_number(sb)
    m_s = sage_m(sb)
    assert m == m_s
    krylov_dim = F.rank_f2(F.conjugates(sb))
    assert krylov_dim == F.pdeg(osb)
    # MT Remark 2 consistency: m = deg Ord + [x+1 does not divide Ord]
    assert m == F.pdeg(osb) + (0 if F.pmod(osb, XP1) == 0 else 1)
    # (5) GHS genus (MT rule) and Hess Thm 5 with gamma1 = 1, gamma2 = sqrt b
    g_rule = F.ghs_genus_rule(m, osb)
    g_hess, *_ = F.hess_genus(XP1, osb, trace_a=F.ftrace(a2i))
    assert g_rule == g_hess, lab
    # (6) realizable gGHS decompositions sqrt(b) = g1*g2  (Tr(a2) = 0)
    real = {}
    def note(g1):
        g2 = F.fmul(sb, F.finv(g1))
        assert F.fmul(g1, g2) == sb
        ty = (ord_type(g1), ord_type(g2))
        if ty not in real:
            o1, o2 = F.ord_poly(g1), F.ord_poly(g2)       # confirm the type by Krylov
            assert (o1, o2) == (TYPE_POLY[ty[0]], TYPE_POLY[ty[1]])
            real[ty] = (g1, g2, F.hess_genus(o1, o2)[0])
    note(1); note(sb)
    for _ in range(64):
        g1 = rng.getrandbits(n)
        if g1:
            note(g1)
    # the types that are NOT realizable, by the trace argument
    tsb = ord_type(sb)
    impossible = []
    for t1 in TYPE_POLY:
        for t2 in TYPE_POLY:
            if (t1, t2) in real:
                continue
            # a type pair with an x+1 entry fixes that gamma = 1, hence the other = sqrt b
            if "x+1" in (t1, t2):
                other = t2 if t1 == "x+1" else t1
                if (t1 == "x+1" and t2 == "x+1"):
                    ok_impossible = (sb != 1)
                else:
                    ok_impossible = (other != tsb)
                assert ok_impossible, (lab, t1, t2)
                impossible.append([t1, t2])
            else:
                raise AssertionError(f"{lab}: pair {(t1, t2)} not sampled but not excluded")
    gmin = min(v[2] for v in real.values())
    min_pairs = sorted([list(k) for k, v in real.items() if v[2] == gmin])
    # (7a) halving criterion: for Tr(a2)=0, 8 | #E iff Tr(b) = 0 ; ground-truth #E = 4N
    card = int(ecc2k.RECORDS[lab]["order_pari"])
    assert card == ecc2k.CARD
    halving_ok = ((card % 8 == 0) == (tr_b == 0)) and F.ftrace(a2i) == 0
    per[lab] = {
        "b_int": str(b), "a2": a2i, "trace_b": tr_b, "trace_sqrt_b": F.ftrace(sb),
        "Ord_b": F.pstr(ob), "deg_Ord_b": F.pdeg(ob),
        "Ord_sqrt_b": F.pstr(osb), "deg_Ord_sqrt_b": F.pdeg(osb),
        "krylov_dim_sqrt_b": krylov_dim, "magic_number": m,
        "ghs_genus": str(g_rule), "ghs_genus_log2_exact_power": (g_rule & (g_rule - 1)) == 0 and g_rule.bit_length() - 1,
        "ghs_genus_formula": "2^(m-1)" if F.pmod(osb, XP1) == 0 else "2^(m-1)-1",
        "gghs_realizable_types": {f"{k[0]},{k[1]}": str(v[2]) for k, v in sorted(real.items())},
        "gghs_nonrealizable_types": impossible,
        "gghs_min_genus": str(gmin), "gghs_min_pairs": min_pairs,
        "gghs_min_witness": {"gamma1_int": str(real[tuple(min_pairs[0])][0]),
                              "gamma2_int": str(real[tuple(min_pairs[0])][1])},
        "sage_checks": {"trace": True, "sqrt": True, "Ord_b": True, "Ord_sqrt_b": True, "m_rank": True},
        "card_ground_truth": str(card), "halving_criterion_consistent": halving_ok,
    }

# ---------------------------------------------------------------- comparisons
wd = "/Volumes/SSD990/ecdlp-hardness-work/weil-descent-ghs"
pc = json.load(open(f"{wd}/per_curve.json"))
raw = json.load(open(f"{wd}/raw_magic_numbers.json"))["curves"]


def norm_poly(s):
    return s.replace(" ", "")


mism = []
for lab in LABELS:
    me, th, rw = per[lab], pc[lab], raw[lab]
    checks = {
        "magic_number": (me["magic_number"], th["magic_number"]),
        "trace_b": (me["trace_b"], th["trace_b"]),
        "Ord_b": (norm_poly(me["Ord_b"]), norm_poly(th["Ord_b"])),
        "deg_Ord_b": (me["deg_Ord_b"], th["deg_Ord_b"]),
        "dim_span_conjugates_sqrt_b": (me["krylov_dim_sqrt_b"], th["dim_span_conjugates_sqrt_b"]),
        "b_is_normal_element": (me["deg_Ord_b"] == 131, th["b_is_normal_element"]),
        "ghs_genus": (me["ghs_genus"], th["ghs_genus"]),
        "ghs_genus_formula": (me["ghs_genus_formula"], th["ghs_genus_formula"]),
        "genus_lower_bound(gGHS min)": (me["gghs_min_genus"], th["genus_lower_bound"]),
        "raw.b_int": (me["b_int"], rw["b_int"]),
        "raw.trace_sqrt_b": (me["trace_sqrt_b"], rw["trace_sqrt_b"]),
        "raw.b_in_F2": (int(me["b_int"]) in (0, 1), rw["b_in_F2"]),
        "raw.x_plus_1_divides_Ord_b": (me["ghs_genus_formula"] == "2^(m-1)", rw["x_plus_1_divides_Ord_b"]),
        "raw.magic_number_rank_sage": (me["magic_number"], rw["magic_number_rank_sage"]),
        "raw.magic_number_rank_bitmask": (me["magic_number"], rw["magic_number_rank_bitmask"]),
        "raw.magic_number_menezes_teske_formula": (me["magic_number"], rw["magic_number_menezes_teske_formula"]),
        "raw.ghs_genus": (me["ghs_genus"], rw["ghs_genus"]),
        "raw.gghs_min_genus": (me["gghs_min_genus"], rw["gghs_min_genus_over_decompositions"]),
    }
    for k, (a, bb) in checks.items():
        if a != bb:
            mism.append({"label": lab, "field": k, "ours": a, "theirs": bb})
    # min-pair lists: report differences (realizability)
    theirs_pairs = sorted([list(p) for p in rw["gghs_min_pairs"]])
    if theirs_pairs != me["gghs_min_pairs"]:
        me["min_pairs_vs_sweep"] = {"ours_realizable": me["gghs_min_pairs"], "sweep_listed": theirs_pairs}

from collections import Counter
summary = {
    "curves": len(per),
    "counts": {
        "magic_number": dict(Counter(str(v["magic_number"]) for v in per.values())),
        "trace_b": dict(Counter(str(v["trace_b"]) for v in per.values())),
        "Ord_b": dict(Counter(v["Ord_b"] for v in per.values())),
        "Ord_sqrt_b": dict(Counter(v["Ord_sqrt_b"] for v in per.values())),
        "ghs_genus": dict(Counter(v["ghs_genus"] for v in per.values())),
        "ghs_genus_formula": dict(Counter(v["ghs_genus_formula"] for v in per.values())),
        "gghs_min_genus": dict(Counter(v["gghs_min_genus"] for v in per.values())),
        "gghs_min_pairs": dict(Counter(json.dumps(v["gghs_min_pairs"]) for v in per.values())),
        "halving_criterion_consistent": dict(Counter(str(v["halving_criterion_consistent"]) for v in per.values())),
    },
    "x131p1_factorization_sage": str(fac),
    "divisors_of_x131p1_degrees": [int(d.degree()) for d in divisors],
    "mismatches_vs_sweep_numeric_fields": mism,
    "min_pairs_differences": {lab: per[lab]["min_pairs_vs_sweep"] for lab in LABELS if "min_pairs_vs_sweep" in per[lab]},
    "elapsed_s": round(time.time() - T0, 1),
}
json.dump({"summary": summary, "curves": per}, open(f"{OUT}/per_curve_G2.json", "w"), indent=1)
s = dict(summary)
s["min_pairs_differences"] = f"{len(summary['min_pairs_differences'])} curves; e.g. " + json.dumps(
    next(iter(summary["min_pairs_differences"].items()), None))
print(json.dumps(s, indent=1))
