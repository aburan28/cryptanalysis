# Per-chart check of Codex run-13 floor-solver-results.json (both panels, all 262 floor charts):
#  - are the pulled_x_coordinates valid x-coordinates (rational y-lift) on the orbit reference curve (A000/B000)
#    and/or on the chart curve itself?
#  - recompute distinct_reachable_targets = # distinct nonzero P1+P2+P3 (three distinct x, all signs) in the
#    order-N subgroup, on whichever curve the x's live; also the unfiltered count for comparison.
import json, itertools, time
from pathlib import Path
from sage.all import GF, PolynomialRing, EllipticCurve, Integer, set_random_seed
set_random_seed(5)
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
GT = json.loads(Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json").read_text())
gt = {c["label"]: c for c in GT["curves"]}
R = PolynomialRing(GF(2), "z"); zz = R.gen()
K = GF(2**131, name="z", modulus=zz**131 + zz**13 + zz**2 + zz + 1)
N = Integer(GT["meta"]["N"])
d = json.loads((W / "codex_inputs/curve-comparison/run-13-full-floor-solver/floor-solver-results.json").read_text())
Ecache = {}
def curve(lab):
    if lab not in Ecache:
        E = EllipticCurve(K, [1, 0, 0, 0, K.from_integer(int(gt[lab]["b_int"]))])
        while True:
            T = N * E.random_point()
            if not (2*T).is_zero(): break
        Ecache[lab] = (E, [E(0), T, 2*T, 3*T])
    return Ecache[lab]
out = {}
t0 = time.time()
for panel, rows in d["panels"].items():
    for r in rows:
        lab = r["curve_id"]; ref = lab[0] + "000"
        xs = [K.from_integer(int(x)) for x in r["pulled_x_coordinates"]]
        res = {"codex_x_count": r["factor_base_x_count"], "codex_targets": r["distinct_reachable_targets"],
               "n_pulled_x": len(xs)}
        for where, cl in [("ref", ref), ("chart", lab)]:
            E, Tm = curve(cl)
            lifts = [E.lift_x(x, all=True) for x in xs]
            res[f"all_x_lift_on_{where}"] = all(bool(L) for L in lifts)
            if res[f"all_x_lift_on_{where}"]:
                pts = [L[0] for L in lifts]
                tags = [Tm.index(N*P) for P in pts]
                filt = set(); unf = set()
                for i, j, l in itertools.combinations(range(len(pts)), 3):
                    for si, sj, sl in itertools.product((1, -1), repeat=3):
                        S = si*pts[i] + sj*pts[j] + sl*pts[l]
                        if S.is_zero(): continue
                        unf.add((S[0], S[1]))
                        if (si*tags[i] + sj*tags[j] + sl*tags[l]) % 4 == 0:
                            filt.add((S[0], S[1]))
                res[f"targets_subgroup_{where}"] = len(filt); res[f"targets_unfiltered_{where}"] = len(unf)
                res[f"tags_{where}"] = sorted(tags)
        out[f"{panel}:{lab}"] = res
    print(panel, "done", time.time() - t0, flush=True)
(W / "raw" / "c11_run13_charts.json").write_text(json.dumps(out, indent=1))
# summary
summ = {}
for panel in d["panels"]:
    rows = {k: v for k, v in out.items() if k.startswith(panel + ":")}
    s = {"charts": len(rows)}
    for where in ["ref", "chart"]:
        s[f"x_valid_on_{where}"] = sum(v[f"all_x_lift_on_{where}"] for v in rows.values())
        s[f"targets_match_subgroup_{where}"] = sum(v.get(f"targets_subgroup_{where}") == v["codex_targets"] for v in rows.values())
        s[f"targets_match_unfiltered_{where}"] = sum(v.get(f"targets_unfiltered_{where}") == v["codex_targets"] for v in rows.values())
    s["x_count_match"] = sum(v["codex_x_count"] == v["n_pulled_x"] for v in rows.values())
    summ[panel] = s
print(json.dumps(summ, indent=1))
(W / "raw" / "c11_run13_charts_summary.json").write_text(json.dumps(summ, indent=1))
