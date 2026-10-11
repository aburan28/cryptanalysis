"""Self-tests of g5lib: summation polynomials on real points, descent vs the repo's
independent tensor-contraction descent (experiments/pdp-scaling/descend.py), brute-force
solution counting vs planted solutions, msolve GB vs brute force.  Writes selftest.json."""
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "ref"))
import g5lib as L  # noqa: E402

out = {}
rng = random.Random(777)
C0 = L.CurveCtx("E0", L.dec(1), order=L.ecc2k.CARD)
recA = L.ecc2k.RECORDS["A000"]
CA = L.CurveCtx("A000", L.dec(recA["b_int"]), order=L.ecc2k.CARD)

# 1. S_{m+1} vanishes on x-coordinates of real point sums
chk = {}
for C in (C0, CA):
    for m in (2, 3):
        good = 0
        for _ in range(20):
            pts = [C.E.random_point() for _ in range(m)]
            T = pts[0]
            for P in pts[1:]:
                T = T + P
            if T.is_zero() or any(P.is_zero() for P in pts):
                continue
            assert L.S_field(m, [P[0] for P in pts], T[0], C.b) == 0
            good += 1
        # and does not vanish for a random r
        r = L.dec(rng.getrandbits(131))
        assert L.S_field(m, [pts[i][0] for i in range(m)], r, C.b) != 0
        chk[f"{C.label}_m{m}"] = good
out["sumpoly_on_points"] = chk
print("sumpoly ok", chk, flush=True)

# 2. descent vs the repo's reference implementation (polynomial basis only)
import descend as REF  # noqa: E402
import gf2n as RG  # noqa: E402
import sumpoly as RS  # noqa: E402

F = RG.GF2n(131, L.ecc2k.MODULUS_INT)
Sref = RS.load(4)
cmp = {}
for C in (C0, CA):
    Er = RG.Curve(F, L.enc(C.b))
    for m in (2, 3):
        for k in (3, 4, 5):
            r = L.dec(rng.getrandbits(131))
            t0 = time.time()
            mine = L.descended_anf(m, L.poly_basis(k), C.b, r)
            t1 = time.time()
            ref = REF.descend(Sref, F, Er, m, k, L.enc(r))
            t2 = time.time()
            same = mine == {mk: v for mk, v in ref.items() if v}
            cmp[f"{C.label}_m{m}_k{k}"] = {"equal": same, "monomials": len(mine),
                                            "t_mine": round(t1 - t0, 3), "t_ref": round(t2 - t1, 3)}
            assert same, (C.label, m, k)
out["descent_vs_reference"] = cmp
print("descent ok", flush=True)

# 3. planted instances: brute-force solution set contains the planted assignment(s);
#    msolve GB count equals brute force count
pl = {}
for C in (C0, CA):
    for m, k in ((2, 5), (3, 4)):
        basis = L.poly_basis(k)
        dom = L.factor_domain(C, basis)
        T, tri = L.planted_target(C, dom, m, rng)
        anf = L.descended_anf(m, basis, C.b, T[0])
        nv = m * k
        sols = L.solutions_bruteforce(anf, nv)
        planted = sum(mk << (i * k) for i, mk in enumerate(tri))
        assert planted in sols
        assert all(L.eval_anf(anf, a) == 0 for a in sols)
        gens, nd = L.build_generators(anf, nv)
        rec, gb = L.run_msolve(gens, nv, 120, f"selftest{C.label}{m}{k}")
        cnt, ok = L.gb_solution_count(gb, nv, sols)
        cls = L.classify_solutions(C, basis, m, sols, T)
        pl[f"{C.label}_m{m}_k{k}"] = {"bruteforce_solutions": len(sols), "msolve_count": cnt,
                                       "gb_vanishes_on_solutions": ok, "msolve_max_deg": rec.get("max_degree"),
                                       "classify": cls}
        assert cnt == len(sols) and ok
        # random (unsat) target
        R = C.random_odd_target(rng)
        anf = L.descended_anf(m, basis, C.b, R[0])
        sols = L.solutions_bruteforce(anf, nv)
        gens, nd = L.build_generators(anf, nv)
        rec, gb = L.run_msolve(gens, nv, 120, f"selftestR{C.label}{m}{k}")
        cnt, ok = L.gb_solution_count(gb, nv, sols)
        assert cnt == len(sols)
        pl[f"{C.label}_m{m}_k{k}_random"] = {"bruteforce_solutions": len(sols), "msolve_count": cnt,
                                              "msolve_max_deg": rec.get("max_degree")}
out["planted"] = pl
print(json.dumps(pl, indent=1), flush=True)
(HERE.parent / "selftest.json").write_text(json.dumps(out, indent=1))
print("ALL SELFTESTS PASSED")
