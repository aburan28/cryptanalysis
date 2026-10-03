# k=6 polynomial-subspace coverage census (same definition as c10), sharded: argv = shard_index n_shards.
# Uses precomputed pair sums so each eligible signed triple costs one point addition.
import json, itertools, time, sys
from pathlib import Path
from sage.all import GF, PolynomialRing, EllipticCurve, Integer, set_random_seed
set_random_seed(66)
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
GT = json.loads(Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json").read_text())
R = PolynomialRing(GF(2), "z"); zz = R.gen()
K = GF(2**131, name="z", modulus=zz**131 + zz**13 + zz**2 + zz + 1); z = K.gen()
N = Integer(GT["meta"]["N"])
si, ns = int(sys.argv[1]), int(sys.argv[2]); k = 6
labels = [c for i, c in enumerate(GT["curves"]) if i % ns == si]
out = {}; t0 = time.time()
for c in labels:
    lab = c["label"]
    E = EllipticCurve(K, [1, int(c["a2"]), 0, 0, K.from_integer(int(c["b_int"]))])
    while True:
        T = N * E.random_point()
        if not (2*T).is_zero(): break
    Tm = [E(0), T, 2*T, 3*T]
    pts = []
    for mask in range(1, 2**k):
        x = sum(z**i for i in range(k) if (mask >> i) & 1)
        L = E.lift_x(x, all=True)
        if L: pts.append(L[0])
    tags = [Tm.index(N*P) for P in pts]
    n = len(pts)
    signed = [[P, -P] for P in pts]
    pair = {}
    for i, j in itertools.combinations(range(n), 2):
        for a in (0, 1):
            for b in (0, 1):
                pair[(i, j, a, b)] = signed[i][a] + signed[j][b]
    elig = inf = 0; targets = set()
    for i, j, l in itertools.combinations(range(n), 3):
        for a in (0, 1):
            for b in (0, 1):
                for cc in (0, 1):
                    s = ((1 - 2*a)*tags[i] + (1 - 2*b)*tags[j] + (1 - 2*cc)*tags[l]) % 4
                    if s: continue
                    elig += 1
                    S = pair[(i, j, a, b)] + signed[l][cc]
                    if S.is_zero(): inf += 1
                    else: targets.add((S[0], S[1]))
    out[lab] = {"6": {"factor_base_x_count": n, "factor_base_signed_point_count": 2*n,
                      "all_signed_triples": 8 * (n*(n-1)*(n-2)//6), "eligible_signed_triples": elig,
                      "infinity_triples": inf, "prime_subgroup_distinct_targets": len(targets),
                      "tag_split_n0_n2_nodd": [tags.count(0), tags.count(2), n - tags.count(0) - tags.count(2)]}}
    print(lab, out[lab]["6"], f"{time.time()-t0:.0f}s", flush=True)
(W / "raw" / f"c10b_k6_shard{si}of{ns}.json").write_text(json.dumps(out, indent=1))
print("done", time.time() - t0)
