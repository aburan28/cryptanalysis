# Kuhn-Struik totals when instances on different B1 curves have unrelated base points:
# each instance needs log_G(P_j) and log_G(Q_j) w.r.t. one common E0 base G -> 2L DLPs.
import math, json, sys
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
ell = ecc2k.N / 262.0
rho1 = math.sqrt(math.pi * ell / 2)
def ks(L):
    s = 0.0; c = 1.0
    for i in range(L):
        s += c; c *= (2 * i + 1) / (2 * i + 2)
    return rho1 * s
out = {}
for L in (1, 263):
    out[f"L{L}_shared_base"] = dict(total_log2=math.log2(ks(L)), per_instance_log2=math.log2(ks(L) / L))
    out[f"L{L}_independent_bases"] = dict(total_log2=math.log2(ks(2 * L)), per_instance_log2=math.log2(ks(2 * L) / L))
print(json.dumps(out, indent=1))
json.dump(out, open("ks_bases.json", "w"), indent=1)
