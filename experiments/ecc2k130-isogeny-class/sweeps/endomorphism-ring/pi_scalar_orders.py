# pi = tau^131 = a + b*tau with f = |b| = 263*p. So pi == a (mod 263 O_K) and (mod p O_K):
# pi acts on E0[263] and E0[p] as the scalar a. The field of definition of E0[ell] is
# F_{q^k}, k = multiplicative order of a mod ell. Also: on a level-ell floor curve pi acts on E[ell]
# as a non-scalar Jordan block with eigenvalue a, so its rational ell-isogeny kernel lives over F_{q^k} too.
from sage.all import *
import json, sys
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
alg = json.load(open("/Volumes/SSD990/ecdlp-hardness-work/endomorphism-ring/algebra_output.json"))
a, b = [Integer(x) for x in alg["pi = tau^131 = a + b*tau, (a,b)"]]
t = Integer(ecc2k.t); p = Integer(ecc2k.p)
out = {}
for ell in [263, p]:
    assert b % ell == 0
    assert (2*a - t) % ell == 0          # a == t/2 mod ell
    k = Mod(a, ell).multiplicative_order()
    out[str(ell)] = {"a_mod_ell": str(a % ell), "ord_a_mod_ell (extension degree k with E0[ell] in E0(F_{q^k}))": str(k),
                     "log2_k": float(log(k, 2)), "factor_k": str(factor(k))}
    # kernel-polynomial size of an ell-isogeny over F_q
    out[str(ell)]["kernel_poly_degree_(ell-1)/2"] = str((ell - 1)//2)
print(json.dumps(out, indent=1))
json.dump(out, open("/Volumes/SSD990/ecdlp-hardness-work/endomorphism-ring/pi_scalar_orders.json", "w"), indent=1)
