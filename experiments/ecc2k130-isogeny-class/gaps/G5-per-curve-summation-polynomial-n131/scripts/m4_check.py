"""Q5: m = 4 (S5) on the real n = 131 curves, polynomial basis V_k, k = 3 and 4 (12 and 16
variables): does E0 differ from the class/dense/sparse curves in msolve F4 behaviour where its
degree-graded profile is (k = 3) or is not (k = 4) different?  S5 and its descent come from the
repo's reference implementation (pdp-scaling/sumpoly.py + descend.py); solutions are checked by
brute force (2^(4k) assignments).
Usage: sage -python m4_check.py LABEL K [NRANDOM [CAP]]  -> raw/m4/m4_<label>_k<K>.json
(k = 4 hit the 600 s msolve cap on E0's first random target under machine load ~40; recorded
 in logs/m4.log and not pursued.)"""
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "ref"))
import descend as REF  # noqa: E402
import g5lib as L  # noqa: E402
import gf2n as RG  # noqa: E402
import sumpoly as RS  # noqa: E402

CTRL = json.loads((ROOT / "controls.json").read_text())
OUT = ROOT / "raw" / "m4"
OUT.mkdir(parents=True, exist_ok=True)
lab, k = sys.argv[1], int(sys.argv[2])
NRAND = int(sys.argv[3]) if len(sys.argv) > 3 else 2
CAP = int(sys.argv[4]) if len(sys.argv) > 4 else 600
m = 4
nv = m * k
if lab in L.ecc2k.RECORDS:
    C = L.CurveCtx(lab, L.dec(L.ecc2k.RECORDS[lab]["b_int"]), order=L.ecc2k.CARD)
else:
    c = next(c for c in CTRL["curves"] if c["label"] == lab)
    C = L.CurveCtx(lab, L.dec(c["b_int"]), order=int(c["order"]))
S5 = RS.load(5)
F = RG.GF2n(131, L.ecc2k.MODULUS_INT)
Er = RG.Curve(F, L.enc(C.b))
basis = L.poly_basis(k)
dom = L.factor_domain(C, basis)
rows = []
targets = []
for i in range(NRAND):
    targets.append(("random", i, C.random_odd_target(random.Random(L.seed_int("G5", lab, "rand", i))), None))
pt = L.planted_target(C, dom, m, random.Random(L.seed_int("G5m4", lab, k, "planted", 0)))
if pt is not None:
    targets.append(("planted", 0, pt[0], pt[1]))
for tk, ti, R, tri in targets:
    t0 = time.process_time()
    anf = {mk: v for mk, v in REF.descend(S5, F, Er, m, k, L.enc(R[0])).items() if v}
    t_desc = time.process_time() - t0
    sols = L.solutions_bruteforce(anf, nv)
    gens, nd = L.build_generators(anf, nv)
    ms, gb = L.run_msolve(gens, nv, CAP, f"m4{lab}{k}{tk}{ti}")
    if gb is not None:
        cnt, ok = L.gb_solution_count(gb, nv, sols[:50])
        ms["solution_count"] = cnt
        ms["agrees_with_bruteforce"] = cnt == len(sols) and ok
    row = {"label": lab, "m": m, "k": k, "target_kind": tk, "target_idx": ti, "target_x": str(L.enc(R[0])),
           "planted_masks": tri, "anf_monomials": len(anf), "anf_degree": L.anf_degree(anf),
           "desc_rank": L.coeff_rank(anf), "descent_cpu": t_desc, "bf_solutions": len(sols), "msolve": ms}
    if tri is not None:
        planted = sum(mk << (i * k) for i, mk in enumerate(tri))
        row["planted_in_solutions"] = planted in sols
    rows.append(row)
    print(json.dumps({x: row[x] for x in ("label", "k", "target_kind", "desc_rank", "bf_solutions")}),
          json.dumps({x: ms.get(x) for x in ("status", "max_degree", "degree_sequence", "msolve_cpu_reported",
                                             "max_matrix", "agrees_with_bruteforce")}), flush=True)
(OUT / f"m4_{lab}_k{k}.json").write_text(json.dumps(rows, indent=1))
