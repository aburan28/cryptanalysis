# Cost bounds used in report.md (plain python3; mpmath-free, uses math.log2 on exact ints).
#   python3 cost_bounds.py  -> cost_bounds.json
import json, math, sys
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
N, q, t = ecc2k.N, ecc2k.q, ecc2k.t
ED = json.load(open("/Volumes/SSD990/ecdlp-hardness-work/pairing-transfer/embedding_degrees.json"))
k = int(ED["N"]["embedding_degree_k_ord_n_q"]); d2 = int(ED["N"]["ord_n_2"])
r = int(ED["twist_factors"]["19678316408850118605767852657510239"]["n"])
assert d2 == 131 * k
lg = math.log2
out = {
 "log2_N": lg(N),
 "rho_E0_neg_tau_log2_iters": 0.5 * lg(math.pi * N / (4 * 131)),
 "rho_neg_only_log2_iters": 0.5 * lg(math.pi * N / 4),
 "k": str(k), "log2_k": lg(k),
 "target_field_F_(q^k)_log2_of_bitlength_131k": lg(131 * k),
 "minimal_field_F_(2^ord_N(2))_log2_of_bitlength": lg(d2),
 "note_lower_bound": "one element of F_(q^k) needs 131*k bits; any Frey-Rueck/MOV transfer must at least write the pairing value, so its cost is >= 131*k bit operations",
 "lower_bound_minus_rho_E0_bits": lg(131 * k) - 0.5 * lg(math.pi * N / (4 * 131)),
 "twist_r_log2": lg(r),
 "rho_on_twist_prime_r_neg_only_log2_iters (out of scope: twist attacks on x-only implementations)": 0.5 * lg(math.pi * r / 4),
}
json.dump(out, open("/Volumes/SSD990/ecdlp-hardness-work/pairing-transfer/cost_bounds.json", "w"), indent=1)
print(json.dumps(out, indent=1))
