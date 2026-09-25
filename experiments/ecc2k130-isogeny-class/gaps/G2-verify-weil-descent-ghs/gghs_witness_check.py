"""G2 item (6): factor x^131+1 over F_2 with own code, tabulate the Hess/MT genus for every
Ord-type pair, and re-check the explicit gGHS decompositions stored by the weil-descent-ghs
sweep (per_curve.json gghs_witness for all 262 floor curves, raw_magic_numbers.json, and
E0's nontrivial decomposition in verify_independent.json) with own arithmetic.

Plain python3:  timeout 2400 python3 gghs_witness_check.py
"""
import sys, json, time, math
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
OUT = "/Volumes/SSD990/ecdlp-hardness-work/gaps/G2-verify-weil-descent-ghs"
sys.path.insert(0, OUT)
import ecc2k                     # constants/records only (no Sage needed)
import f2lin as F

T0 = time.time()
res = {}
X131 = (1 << 131) | 1
XP1 = 0b11
PHI, r = F.pdivmod(X131, XP1)
assert r == 0
# ord_131(2)
o = next(k for k in range(1, 200) if pow(2, k, 131) == 1)
res["ord_131(2)"] = o
res["Phi131_is_sum_x^i_i<=130"] = PHI == (1 << 131) - 1 and F.pdeg(PHI) == 130
res["Phi131_irreducible_rabin"] = F.is_irreducible_f2(PHI)
res["x+1_times_Phi131_eq_x131+1"] = F.clmul(XP1, PHI) == X131
res["gcd(x^131+1, x^130)"] = F.pstr(F.pgcd(X131, 1 << 130))
res["factorization"] = "(x + 1) * Phi_131, Phi_131 = sum_{i=0}^{130} x^i irreducible (Rabin test; ord_131(2) = %d)" % o

# genus table over all Ord-type pairs (Tr(a) = 0 and Tr(a) = 1)
types = {"x+1": XP1, "Phi131": PHI, "x^131+1": X131}
tab = {}
for ta in (0, 1):
    for n1, p1 in types.items():
        for n2, p2 in types.items():
            g, t, s1, s2 = F.hess_genus(p1, p2, trace_a=ta)
            tab[f"Tr(a)={ta}:{n1},{n2}"] = {"genus": str(g), "t": t, "s1": s1, "s2": s2,
                                           "log2_genus": round(math.log2(g), 6)}
res["genus_table"] = tab
g_min_excl = min(int(v["genus"]) for k, v in tab.items() if k.startswith("Tr(a)=0") and k != "Tr(a)=0:x+1,x+1")
res["min_genus_Tr(a)=0_excluding_(x+1,x+1)"] = str(g_min_excl)
res["min_genus_excl_equals_2^130-1"] = g_min_excl == 2 ** 130 - 1
# (x+1, x+1) needs gamma1, gamma2 in F_2^* = {1}, so sqrt(b) = 1, b = 1: only E0.
res["argument"] = ("Every nonzero gamma in F_q has Ord_gamma | x^131+1 = (x+1)Phi_131, so Ord_gamma is x+1 "
                   "(gamma = 1), Phi_131 (Tr gamma = 0, gamma != 0) or x^131+1 (Tr gamma = 1, gamma != 1). "
                   "Over the 9 type pairs with Tr(a2) = 0 the Hess genus is 1 only for (x+1, x+1), which "
                   "forces gamma1 = gamma2 = 1 and sqrt(b) = 1, i.e. b = 1 (E0). All other pairs give genus "
                   ">= 2^130 - 1. For the 262 floor curves b != 1, so every decomposition sqrt(b) = g1*g2 "
                   "has genus >= 2^130 - 1, attained only by (Phi131, Phi131).")

# stored witnesses
wd = "/Volumes/SSD990/ecdlp-hardness-work/weil-descent-ghs"
pc = json.load(open(f"{wd}/per_curve.json"))
raw = json.load(open(f"{wd}/raw_magic_numbers.json"))["curves"]
vi = json.load(open(f"{wd}/verify_independent.json"))["summary"]["E0_nontrivial_gghs_decomposition"]


def check_witness(lab, w):
    b = int(ecc2k.RECORDS[lab]["b_int"])
    sb = F.fsqrt(b)
    g1, g2 = int(w["gamma1_int"]), int(w["gamma2_int"])
    prod = F.fmul(g1, g2)
    o1, o2 = F.ord_poly(g1), F.ord_poly(g2)
    g, t, s1, s2 = F.hess_genus(o1, o2, trace_a=0)
    rec = {"g1*g2==sqrt(b)": prod == sb, "g1*g2==b": prod == b,
           "Ord_g1": F.pstr(o1) if F.pdeg(o1) < 2 else f"deg {F.pdeg(o1)}" + (" (Phi131)" if o1 == PHI else ""),
           "Ord_g2": F.pstr(o2) if F.pdeg(o2) < 2 else f"deg {F.pdeg(o2)}" + (" (Phi131)" if o2 == PHI else ""),
           "t": t, "s1": s1, "s2": s2, "genus_recomputed": str(g),
           "genus_stored": w["genus"], "genus_match": str(g) == w["genus"]}
    for k in ("Ord_gamma1_deg", "Ord_gamma2_deg", "t_lcm_deg"):
        if k in w:
            rec[k + "_match"] = {"Ord_gamma1_deg": s1, "Ord_gamma2_deg": s2, "t_lcm_deg": t}[k] == w[k]
    return rec


wit = {}
for lab in ecc2k.LABELS:
    w = pc[lab]["gghs_witness"]
    if w is None:
        continue
    rec = check_witness(lab, w)
    # also the raw file's witness must be the same data
    rec["raw_file_same_witness"] = raw[lab]["gghs_witness"] == w
    wit[lab] = rec
res["witnesses_checked"] = len(wit)
res["witness_all_ok"] = all(v["g1*g2==sqrt(b)"] and v["genus_match"] and v["raw_file_same_witness"]
                            and all(v.get(k, True) for k in ("Ord_gamma1_deg_match", "Ord_gamma2_deg_match", "t_lcm_deg_match"))
                            for v in wit.values())
res["witness_genus_values"] = sorted({v["genus_recomputed"] for v in wit.values()})
res["witness_failures"] = {k: v for k, v in wit.items() if not (v["g1*g2==sqrt(b)"] and v["genus_match"])}
res["E0_nontrivial_decomposition"] = check_witness("E0", vi)
res["E0_nontrivial_decomposition"]["genus_stored_equals_2^130-1"] = int(vi["genus"]) == 2 ** 130 - 1
res["witness_sample_A000"] = wit["A000"]
res["witness_sample_B130"] = wit["B130"]
res["elapsed_s"] = round(time.time() - T0, 1)
json.dump({"summary": res, "per_curve_witness": wit}, open(f"{OUT}/gghs_witness_check.json", "w"), indent=1)
out = dict(res); out.pop("genus_table")
print(json.dumps(out, indent=1))
print("genus_table (Tr(a)=0):", json.dumps({k: v["genus"] for k, v in tab.items() if k.startswith("Tr(a)=0")}, indent=1))
