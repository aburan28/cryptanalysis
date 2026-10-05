# Recompute Codex run-01 per-curve exact relation-coverage numbers (comparison.csv) for the
# polynomial-subspace profiles (k=4 and k=5) on all 263 curves, from scratch:
#   factor_base_x_count, factor_base_signed_point_count, all_signed_triples, eligible_signed_triples,
#   infinity_triples, prime_subgroup_distinct_targets, plus the four-torsion tag split (n0, n2, n_odd).
# Definition (run-01 REPORT): x ranges over nonzero elements of span{1, z, ..., z^(k-1)} with a rational y-lift;
# both signs kept; decompositions use three distinct x; all 8 sign choices; image filtered to the order-N subgroup
# via four-torsion components; infinity excluded from the target count.
import json, itertools, time, sys
from pathlib import Path
from sage.all import GF, PolynomialRing, EllipticCurve, Integer, set_random_seed
set_random_seed(99)
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
GT = json.loads(Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json").read_text())
R = PolynomialRing(GF(2), "z"); zz = R.gen()
K = GF(2**131, name="z", modulus=zz**131 + zz**13 + zz**2 + zz + 1)
z = K.gen()
N = Integer(GT["meta"]["N"])
ks = [int(a) for a in sys.argv[1:]] or [4, 5]
out = {}
t0 = time.time()
for c in GT["curves"]:
    lab = c["label"]
    b = K.from_integer(int(c["b_int"]))
    E = EllipticCurve(K, [1, int(c["a2"]), 0, 0, b])
    while True:                      # generator of E(F_q)[4] (cyclic of order 4)
        T = N * E.random_point()
        if not (2 * T).is_zero(): break
    Tm = [E(0), T, 2*T, 3*T]
    def tag(P):
        return Tm.index(N * P)
    rec = {}
    for k in ks:
        pts = []                     # one representative per rational x; -P implied
        for mask in range(1, 2**k):
            x = sum(z**i for i in range(k) if (mask >> i) & 1)
            L = E.lift_x(x, all=True)
            if L:
                pts.append(L[0])
        tags = [tag(P) for P in pts]
        n0 = sum(1 for g in tags if g == 0); n2 = sum(1 for g in tags if g == 2); nodd = len(tags) - n0 - n2
        allt = elig = inf = 0
        targets = set()
        for i, j, l in itertools.combinations(range(len(pts)), 3):
            for si, sj, sl in itertools.product((1, -1), repeat=3):
                allt += 1
                if (si*tags[i] + sj*tags[j] + sl*tags[l]) % 4:
                    continue
                elig += 1
                S = (pts[i] if si == 1 else -pts[i]) + (pts[j] if sj == 1 else -pts[j]) + (pts[l] if sl == 1 else -pts[l])
                if S.is_zero():
                    inf += 1
                else:
                    targets.add((S[0], S[1]))
        rec[str(k)] = {"factor_base_x_count": len(pts), "factor_base_signed_point_count": 2*len(pts),
                       "all_signed_triples": allt, "eligible_signed_triples": elig, "infinity_triples": inf,
                       "prime_subgroup_distinct_targets": len(targets), "tag_split_n0_n2_nodd": [n0, n2, nodd]}
    out[lab] = rec
    if len(out) % 20 == 0 or lab == "E0":
        print(len(out), lab, rec, f"{time.time()-t0:.0f}s", flush=True)
suffix = "_".join(map(str, ks))
(W / "raw" / f"c10_relation_coverage_k{suffix}.json").write_text(json.dumps(out, indent=1))
print("done", time.time() - t0)
