# Generic-attack baselines per curve class (recomputed, not read).
from mpmath import mp, mpf, sqrt, pi, log
import json
mp.dps = 50
N = mpf(680564733841876926932320129493409985129)
r = {}
r["log2_N"] = float(log(N, 2))
r["E0_rho_neg_tau_log2"] = float(log(sqrt(pi*N/(4*131)), 2))   # classes of size 2*131
r["E0_rho_neg_only_log2"] = float(log(sqrt(pi*N/4), 2))
r["floor_rho_neg_only_log2"] = float(log(sqrt(pi*N/4), 2))       # floor curves: no F_2 model, no tau
r["floor_rho_plain_log2"] = float(log(sqrt(pi*N/2), 2))
r["note"] = "floor curves: effective ECDLP cost = min(own rho 2^64.33, transfer via an F_q-rational degree-263 isogeny to E0 (poly time, gcd(263,N)=1) + E0 rho 2^60.81)"
print(json.dumps(r, indent=1))
json.dump(r, open("../raw/c05_rho_baselines.json", "w"), indent=1)
