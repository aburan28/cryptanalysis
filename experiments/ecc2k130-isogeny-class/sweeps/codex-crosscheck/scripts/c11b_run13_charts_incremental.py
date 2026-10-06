# Incremental/sharded version of c11: per-chart check of Codex run-13 floor-solver-results.json.
# argv: shard n_shards. Appends JSON lines to raw/c11b_shard{s}of{n}.jsonl
import json, itertools, time, sys
from pathlib import Path
from sage.all import GF, PolynomialRing, EllipticCurve, Integer, set_random_seed
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
GT = json.loads(Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json").read_text())
gt = {c["label"]: c for c in GT["curves"]}
R = PolynomialRing(GF(2), "z"); zz = R.gen()
K = GF(2**131, name="z", modulus=zz**131 + zz**13 + zz**2 + zz + 1)
N = Integer(GT["meta"]["N"])
si, ns = int(sys.argv[1]), int(sys.argv[2])
set_random_seed(500 + si)
d = json.loads((W / "codex_inputs/curve-comparison/run-13-full-floor-solver/floor-solver-results.json").read_text())
outf = W / "raw" / f"c11b_shard{si}of{ns}.jsonl"
done = set()
if outf.exists():
    for line in outf.read_text().splitlines():
        if line.strip(): done.add(json.loads(line)["key"])
Ecache = {}
def curve(lab):
    if lab not in Ecache:
        E = EllipticCurve(K, [1, 0, 0, 0, K.from_integer(int(gt[lab]["b_int"]))])
        while True:
            T = N * E.random_point()
            if not (2*T).is_zero(): break
        Ecache[lab] = (E, [E(0), T, 2*T, 3*T])
    return Ecache[lab]
jobs = [(panel, r) for panel, rows in d["panels"].items() for r in rows]
t0 = time.time()
for idx, (panel, r) in enumerate(jobs):
    key = f"{panel}:{r['curve_id']}"
    if idx % ns != si or key in done: continue
    lab = r["curve_id"]; ref = lab[0] + "000"
    xs = [K.from_integer(int(x)) for x in r["pulled_x_coordinates"]]
    res = {"key": key, "codex_x_count": r["factor_base_x_count"], "codex_targets": r["distinct_reachable_targets"], "n_pulled_x": len(xs)}
    for where, cl in [("ref", ref), ("chart", lab)]:
        E, Tm = curve(cl)
        lifts = [E.lift_x(x, all=True) for x in xs]
        res[f"all_x_lift_on_{where}"] = all(bool(L) for L in lifts)
        if res[f"all_x_lift_on_{where}"]:
            pts = [L[0] for L in lifts]
            tags = [Tm.index(N*P) for P in pts]
            filt = set(); unf = set()
            for i, j, l in itertools.combinations(range(len(pts)), 3):
                for a, b, c in itertools.product((1, -1), repeat=3):
                    S = a*pts[i] + b*pts[j] + c*pts[l]
                    if S.is_zero(): continue
                    unf.add((S[0], S[1]))
                    if (a*tags[i] + b*tags[j] + c*tags[l]) % 4 == 0: filt.add((S[0], S[1]))
            res[f"targets_subgroup_{where}"] = len(filt); res[f"targets_unfiltered_{where}"] = len(unf)
            res[f"tags_{where}"] = sorted(tags)
            break          # x's valid on the reference curve: no need to test the chart
    with open(outf, "a") as fh:
        fh.write(json.dumps(res) + "\n")
    print(key, f"{time.time()-t0:.0f}s", flush=True)
print("done", time.time() - t0, flush=True)
