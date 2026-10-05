# Compare Codex's Phi_263(1,Y) mod 2 exponent list (run-04 phi263-specialization.json) and its H_D mod 2 exponents
# (inventory.json) against (Y+1)^2 * H_D(Y) mod 2 computed from the ground-truth H_D hex file, plus a fresh
# PARI polmodular(263, 0, Mod(1,2)) evaluation. Also orbit minpoly exponent lists (A, B) vs our factorization.
import json, hashlib
from pathlib import Path
from sage.all import GF, PolynomialRing, pari, ZZ
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
hexlines = Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/class_polynomial_D-484183.hex").read_text().split()
coeffs = [int(h, 16) for h in hexlines]
R = PolynomialRing(GF(2), "Y"); Y = R.gen()
H2 = R([c % 2 for c in coeffs])
ph = json.loads((W / "codex_inputs/curve-comparison/run-04-isogeny/phi263-specialization.json").read_text())
inv = json.loads((W / "codex_inputs/public-cm-inventory/inventory.json").read_text())
res = {}
res["H_D_degree"] = int(H2.degree())
res["H_D_mod2_exponents_match_codex"] = [k for k, c in enumerate(H2.list()) if c] == inv["mod_2_polynomial_nonzero_exponents"]
res["hex_sha256_matches_codex"] = hashlib.sha256(("\n".join(format(c, "x") for c in coeffs) + "\n").encode()).hexdigest() == inv["integer_polynomial_coefficients_sha256"]
F = (Y + 1)**2 * H2
res["(Y+1)^2*H_D exponents == codex Phi_263(1,Y) exponents"] = [k for k, c in enumerate(F.list()) if c] == ph["nonzero_exponents"]
phi_pari = pari("polmodular(263, 0, Mod(1,2))")
Pp = R([int(pari.lift(pari.polcoef(phi_pari, k))) % 2 for k in range(int(pari.poldegree(phi_pari)) + 1)])
res["fresh PARI Phi_263(1,Y) mod 2 exponents == codex"] = [k for k, c in enumerate(Pp.list()) if c] == ph["nonzero_exponents"]
res["codex_phi_source_sha256"] = ph["source_sha256"]
fac = H2.factor()
exps = sorted([[k for k, c in enumerate(g.list()) if c] for g, _ in fac])
cod = sorted([m["j_minpoly_nonzero_exponents"] for m in inv["models"]])
res["orbit minpolys (as a set) == codex j_minpoly lists"] = exps == cod
res["factor degrees"] = sorted(int(g.degree()) for g, _ in fac)
print(json.dumps(res, indent=1))
(W / "raw" / "c09_phi263_and_hd.json").write_text(json.dumps(res, indent=1))
