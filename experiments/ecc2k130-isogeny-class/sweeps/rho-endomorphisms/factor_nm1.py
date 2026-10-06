# Factor N-1 and N+1 (PARI), record orders of small structural elements.
import sys, json, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import pari, factor, Integer, is_prime, log, RR
N = Integer(ecc2k.N)
t0 = time.time()
F = factor(N - 1, proof=True)
t1 = time.time()
out = {"N": str(N), "N_minus_1_factorization": [[str(pp), int(e)] for pp, e in F],
       "all_factors_proved_prime": all(Integer(pp).is_prime(proof=True) for pp, _ in F),
       "factor_seconds": round(t1 - t0, 2)}
print(F, "time", t1 - t0)
# number of eigenvalues of order < 2^20
divs = [d for d in (N - 1).divisors() if d < 2**20] if len(F) < 40 else None
from sage.all import euler_phi
out["small_divisors_lt_2^20"] = [int(d) for d in divs]
out["num_elements_order_lt_2^20"] = int(sum(euler_phi(d) for d in divs))
print("divisors < 2^20:", divs, "count elements:", out["num_elements_order_lt_2^20"])
json.dump(out, open("factor_nm1.json", "w"), indent=1)
