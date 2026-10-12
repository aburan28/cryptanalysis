# Re-derive Codex run-06 numbers for E0, A090, B021, B067 on span{1..z^(k-1)}, k = 8, 9, 10:
#  natural rational x counts, exact tag-compatible signed 4-tuples (distinct x), collision-free coverage
#  log2(eligible/(N-1)), and the optimistic 10%-overdetermined relation-target lower bound
#  log2(ceil(1.1*xcount)/coverage) -- compared with Codex (2^-95.84..2^-95.56, 2^104.92 E0, 2^104.71 A090,
#  +22.05% A090 vs E0 eligible 4-tuples at k=10), and the gap to E0 signed-Frobenius rho 2^60.809.
import json, math
from pathlib import Path
from sage.all import GF, PolynomialRing, EllipticCurve, Integer, set_random_seed, RR, log
set_random_seed(11)
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
GT = json.loads(Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json").read_text())
gt = {c["label"]: c for c in GT["curves"]}
R = PolynomialRing(GF(2), "z"); zz = R.gen()
K = GF(2**131, name="z", modulus=zz**131 + zz**13 + zz**2 + zz + 1); z = K.gen()
N = Integer(GT["meta"]["N"])
rho = float(RR(log(RR.pi()*N/(4*131), 2)/2))
out = {"E0_rho_log2": rho}
for lab in ["E0", "A090", "B021", "B067"]:
    E = EllipticCurve(K, [1, 0, 0, 0, K.from_integer(int(gt[lab]["b_int"]))])
    while True:
        T = N * E.random_point()
        if not (2*T).is_zero(): break
    Tm = [E(0), T, 2*T, 3*T]
    tags = {}
    for mask in range(1, 2**10):
        x = sum(z**i for i in range(10) if (mask >> i) & 1)
        L = E.lift_x(x, all=True)
        if L:
            tags[mask] = Tm.index(N * L[0])
    rec = {}
    for k in [8, 9, 10]:
        tg = [g for m, g in tags.items() if m < 2**k]
        dp = [[0]*4 for _ in range(5)]; dp[0][0] = 1
        for g in tg:
            new = [row[:] for row in dp]
            for m in range(4):
                for r in range(4):
                    c = dp[m][r]
                    if c:
                        new[m+1][(r+g) % 4] += c; new[m+1][(r-g) % 4] += c
            dp = new
        elig = dp[4][0]
        cov = math.log2(elig) - math.log2(int(N) - 1)
        rows = math.ceil(1.1 * len(tg))
        rec[str(k)] = {"x_count": len(tg), "eligible_signed_4tuples": elig, "coverage_log2": cov,
                       "rows_needed": rows, "targets_lower_bound_log2": math.log2(rows) - cov,
                       "bits_above_E0_rho": math.log2(rows) - cov - rho,
                       "tag_counts": [tg.count(i) for i in range(4)]}
    out[lab] = rec
    print(lab, json.dumps(rec), flush=True)
e0 = out["E0"]["10"]["eligible_signed_4tuples"]; a = out["A090"]["10"]["eligible_signed_4tuples"]
out["A090_vs_E0_eligible_k10_percent"] = 100.0 * (a / e0 - 1)
# ideal half-density extrapolation: where does the target lower bound cross the E0 rho line?
def lb(k):
    n = 2**(k-1); elig = math.comb(n, 4) * 16 / 4
    return math.log2(math.ceil(1.1*n)) - (math.log2(elig) - math.log2(int(N) - 1))
out["half_density_crossover"] = {str(k): lb(k) for k in range(20, 29)}
print(json.dumps({k: v for k, v in out.items() if k not in ("E0", "A090", "B021", "B067")}, indent=1))
(W / "raw" / "c12_run06_bounds.json").write_text(json.dumps(out, indent=1))
