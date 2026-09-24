# Why 131 and 263 divide N-1 (and hence why the index (N-1)/k contains 131), plus an independent
# point count of y^2+xy=x^3+1 over GF(2^131) in Sage's DEFAULT modulus (not the ECC2K basis).
#   sage -python structural_checks.py -> structural_checks.json
import json, sys
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import Integer, GF, EllipticCurve, Mod
N, q, t, s = Integer(ecc2k.N), Integer(ecc2k.q), Integer(ecc2k.t), Integer(ecc2k.TAU_EIGEN)
o = {}
o["tau_eigen_s_order_mod_N"] = str(Mod(s, N).multiplicative_order())      # expect 131 (tau^131 = pi = 1 on E(F_q))
o["131 | N-1"] = bool((N - 1) % 131 == 0)
o["q mod 263"] = int(q % 263); o["t mod 263"] = int(t % 263)
o["ord_263(2)"] = int(Mod(2, 263).multiplicative_order())
o["(q+1-t) mod 263"] = int((q + 1 - t) % 263)
o["N mod 263"] = int(N % 263)
o["t^2-4q mod 263^2"] = int((t * t - 4 * q) % 263**2)
o["2 is QR mod N (so ord_N(2) | (N-1)/2)"] = bool(Mod(2, N).is_square())
o["ord_N(2) = 131*k"] = None
E = EllipticCurve(GF(2**131, "a"), [1, 0, 0, 0, 1])      # Sage default modulus, independent of ground truth
c = E.cardinality()
o["sage_default_modulus_card"] = str(c)
o["card == 4N"] = bool(c == 4 * N)
k = Mod(q, N).multiplicative_order(); d = Mod(2, N).multiplicative_order()
o["ord_N(2) = 131*k"] = bool(d == 131 * k)
o["(N-1)/ord_N(2)"] = str((N - 1) // d)
o["(N-1)/k"] = str((N - 1) // k)
json.dump(o, open("structural_checks.json", "w"), indent=1)
print(json.dumps(o, indent=1))
