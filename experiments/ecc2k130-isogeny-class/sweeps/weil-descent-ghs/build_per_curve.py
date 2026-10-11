"""Assemble per_curve.json {label: {...}} from raw_magic_numbers.json (+ weil_restriction.json).
Run: python3 build_per_curve.py"""
import json, math, sys
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k

D = "/Volumes/SSD990/ecdlp-hardness-work/weil-descent-ghs/"
raw = json.load(open(D + "raw_magic_numbers.json"))
wr = json.load(open(D + "weil_restriction.json"))
assert wr["A(1)==N"] is True and wr["Pres_factor_degrees"] == [2, 260]
N = ecc2k.N
rho_E0 = math.log2(math.sqrt(math.pi * N / (4 * 131)))
rho_floor = math.log2(math.sqrt(math.pi * N / 4))
HESS_AS_LB = 2 ** 128 + 1
out = {}
for lab in ecc2k.LABELS:
    r = raw["curves"][lab]
    m = r["magic_number_rank_sage"]
    assert m == r["magic_number_rank_bitmask"] == r["magic_number_menezes_teske_formula"]
    g = int(r["ghs_genus"])
    gmin = int(r["gghs_min_genus_over_decompositions"])
    is_e0 = (lab == "E0")
    out[lab] = {
        "magic_number": m,
        "genus_lower_bound": str(gmin),
        "genus_lower_bound_log2": math.log2(gmin),
        "genus_lower_bound_meaning": ("min genus over GHS and all Hess-gGHS decompositions sqrt(b)=g1*g2 "
                                      "(Menezes-Teske 2006 eq.(5)); for E0 the genus-1 cover is E0/F_2 itself, "
                                      "whose Jacobian E0(F_2) has order 4 and cannot carry the order-N subgroup"),
        "ghs_genus": str(g),
        "ghs_genus_formula": "2^(m-1)" if r["x_plus_1_divides_Ord_b"] else "2^(m-1)-1",
        "ghs_genus_log2": math.log2(g),
        "trace_b": r["trace_b"],
        "Ord_b": "x^131+1" if r["deg_Ord_b"] == 131 else r["Ord_b"],
        "deg_Ord_b": r["deg_Ord_b"],
        "dim_span_conjugates_sqrt_b": r["dim_span_conjugates_sqrt_b"],
        "b_is_normal_element": (r["deg_Ord_b"] == 131),
        "descent_subfields": ["F_2"],
        "genus_lower_bound_any_cover_capturing_N": 130,
        "genus_lower_bound_hess_artin_schreier_nontrivial": str(HESS_AS_LB),
        "ghs_cover_carries_N_subgroup": (False if is_e0 else "not needed: genus 2^130"),
        "hardness_reduction_log2": 0.0,
        "rho_baseline_log2_iterations": round(rho_E0 if is_e0 else rho_floor, 2),
        "gghs_witness": r["gghs_witness"],
    }
json.dump(out, open(D + "per_curve.json", "w"), indent=1)
from collections import Counter
print(len(out), Counter((v["magic_number"], v["genus_lower_bound_log2"], v["ghs_genus_log2"], v["trace_b"]) for v in out.values()))
