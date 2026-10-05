# Find which curve the run-13 pulled_x_coordinates live on (test every one of the 263 curves for a few charts).
import json
from pathlib import Path
from sage.all import GF, PolynomialRing, EllipticCurve
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
GT = json.loads(Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json").read_text())
R = PolynomialRing(GF(2), "z"); zz = R.gen()
K = GF(2**131, name="z", modulus=zz**131 + zz**13 + zz**2 + zz + 1)
d = json.loads((W / "codex_inputs/curve-comparison/run-13-full-floor-solver/floor-solver-results.json").read_text())
curves = {c["label"]: EllipticCurve(K, [1, 0, 0, 0, K.from_integer(int(c["b_int"]))]) for c in GT["curves"]}
for panel in ["common_conjugate", "chart_specific"]:
    for r in d["panels"][panel][:3] + d["panels"][panel][131:133]:
        xs = [K.from_integer(int(x)) for x in r["pulled_x_coordinates"]]
        hits = [lab for lab, E in curves.items() if all(E.lift_x(x, all=True) for x in xs)]
        print(panel, r["curve_id"], "x's liftable on:", hits, flush=True)
