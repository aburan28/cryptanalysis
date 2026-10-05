# run-01 "random" profile (k=4) for all 263 curves. The basis is regenerated exactly as in Codex's
# run-01/executed-source.py coordinate_basis(): random.Random(20260923).getrandbits(131), keeping linearly
# independent vectors; element = integer bitmask (bit i = z^i). Same counting definitions as c10.
import json, itertools, time, sys, random
from pathlib import Path
from sage.all import GF, PolynomialRing, EllipticCurve, Integer, set_random_seed
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
GT = json.loads(Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json").read_text())
R = PolynomialRing(GF(2), "z"); zz = R.gen()
K = GF(2**131, name="z", modulus=zz**131 + zz**13 + zz**2 + zz + 1)
N = Integer(GT["meta"]["N"])
si, ns = int(sys.argv[1]), int(sys.argv[2]); k = 4
rng = random.Random(20260923); basis = []; piv = {}
while len(basis) < k:
    u = rng.getrandbits(131); v = u
    while v and v.bit_length() - 1 in piv: v ^= piv[v.bit_length() - 1]
    if v:
        piv[v.bit_length() - 1] = v; basis.append(K.from_integer(u))
outf = W / "raw" / f"c10d_random_k4_shard{si}of{ns}.jsonl"
done = set()
if outf.exists():
    done = {json.loads(l)["label"] for l in outf.read_text().splitlines() if l.strip()}
set_random_seed(2000 + si); t0 = time.time()
for idx, c in enumerate(GT["curves"]):
    if idx % ns != si or c["label"] in done: continue
    E = EllipticCurve(K, [1, int(c["a2"]), 0, 0, K.from_integer(int(c["b_int"]))])
    while True:
        T = N * E.random_point()
        if not (2*T).is_zero(): break
    Tm = [E(0), T, 2*T, 3*T]
    pts = []
    for mask in range(1, 2**k):
        x = sum((basis[i] for i in range(k) if (mask >> i) & 1), K(0))
        if x == 0: continue
        L = E.lift_x(x, all=True)
        if L: pts.append(L[0])
    tags = [Tm.index(N*P) for P in pts]; n = len(pts)
    elig = inf = 0; targets = set()
    for i, j, l in itertools.combinations(range(n), 3):
        for a, b, cc in itertools.product((1, -1), repeat=3):
            if (a*tags[i] + b*tags[j] + cc*tags[l]) % 4: continue
            elig += 1
            S = a*pts[i] + b*pts[j] + cc*pts[l]
            if S.is_zero(): inf += 1
            else: targets.add((S[0], S[1]))
    rec = {"label": c["label"], "4r": {"factor_base_x_count": n, "factor_base_signed_point_count": 2*n,
           "all_signed_triples": 8*(n*(n-1)*(n-2)//6), "eligible_signed_triples": elig, "infinity_triples": inf,
           "prime_subgroup_distinct_targets": len(targets),
           "tag_split_n0_n2_nodd": [tags.count(0), tags.count(2), n - tags.count(0) - tags.count(2)]}}
    with open(outf, "a") as fh: fh.write(json.dumps(rec) + "\n")
    print(c["label"], f"{time.time()-t0:.0f}s", flush=True)
print("done", flush=True)
