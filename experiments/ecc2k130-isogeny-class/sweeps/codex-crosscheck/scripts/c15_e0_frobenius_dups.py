# E0-specific Codex claims (run-02/run-03):
#  (a) 2*P3 + P5 + P17 = O for the points with x = 1+z, 1+z^2, 1+z^4 (appropriate signs): tau^2 + tau + 2 = 0
#  (b) E0 k=7 polynomial-subspace coverage: eligible 79,848, distinct 79,788 (excess 60)
import json, itertools, time
from pathlib import Path
from sage.all import GF, PolynomialRing, EllipticCurve, Integer, set_random_seed
set_random_seed(77)
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
R = PolynomialRing(GF(2), "z"); zz = R.gen()
K = GF(2**131, name="z", modulus=zz**131 + zz**13 + zz**2 + zz + 1); z = K.gen()
N = Integer(680564733841876926932320129493409985129)
E = EllipticCurve(K, [1, 0, 0, 0, 1])
res = {}
P3 = E.lift_x(1 + z)
tau = lambda P: E(P[0]**2, P[1]**2)
P5, P17 = tau(P3), tau(tau(P3))
res["x(P5)==1+z^2"] = P5[0] == 1 + z**2; res["x(P17)==1+z^4"] = P17[0] == 1 + z**4
res["2P3+tau(P3)+tau^2(P3)==O"] = (2*P3 + P5 + P17).is_zero()
res["holds_for_random_point"] = all((2*Q + tau(Q) + tau(tau(Q))).is_zero() for Q in [E.random_point() for _ in range(3)])
# (b) k = 7 census on E0
while True:
    T = N * E.random_point()
    if not (2*T).is_zero(): break
Tm = [E(0), T, 2*T, 3*T]
t0 = time.time()
for k in [7]:
    pts = []
    for mask in range(1, 2**k):
        x = sum(z**i for i in range(k) if (mask >> i) & 1)
        L = E.lift_x(x, all=True)
        if L: pts.append(L[0])
    tags = [Tm.index(N*P) for P in pts]; n = len(pts)
    signed = [[P, -P] for P in pts]
    pair = {}
    for i, j in itertools.combinations(range(n), 2):
        for a in (0, 1):
            for b in (0, 1):
                pair[(i, j, a, b)] = signed[i][a] + signed[j][b]
    elig = inf = 0; targets = {}
    for i, j, l in itertools.combinations(range(n), 3):
        for a in (0, 1):
            for b in (0, 1):
                for c in (0, 1):
                    if ((1-2*a)*tags[i] + (1-2*b)*tags[j] + (1-2*c)*tags[l]) % 4: continue
                    elig += 1
                    S = pair[(i, j, a, b)] + signed[l][c]
                    if S.is_zero(): inf += 1
                    else: targets[(S[0], S[1])] = targets.get((S[0], S[1]), 0) + 1
    res[f"E0_k{k}"] = {"x_count": n, "eligible": elig, "infinity": inf, "distinct": len(targets),
                       "excess": elig - inf - len(targets), "max_multiplicity": max(targets.values()),
                       "codex": {"eligible": 79848, "distinct": 79788, "excess": 60}, "seconds": time.time() - t0}
print(json.dumps(res, indent=1, default=str))
(W / "raw" / "c15_e0_frobenius_dups.json").write_text(json.dumps(res, indent=1, default=str))
