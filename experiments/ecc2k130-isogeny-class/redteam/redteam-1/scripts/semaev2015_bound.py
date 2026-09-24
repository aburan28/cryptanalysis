"""Semaev (ePrint 2015/310) splitting variant under its own optimistic heuristic:
S_{m+1} split into m-1 copies of S_3 with m-2 auxiliary F_{2^n} unknowns (n Boolean vars each),
Boolean system of n(m-1) equations in V = m*l + (m-2)*n variables, Groebner degree assumed
<= D (D = 4 is Semaev's claim; 5,6 shown for sensitivity).  Cost per PDP = M^omega,
M = sum_{i<=D} C(V, i).  Relation probability p = min(1, 2^{ml}/(m! 2^n)), relations 2^l,
LA m*2^{2l}.  Disputed heuristic (Kosters-Yeo; Huang-Kosters-Yeo); used only as an upper-
optimistic bound for n = 131."""
import math, json, sys
n = 131
N = 680564733841876926932320129493409985129
rho = 0.5 * math.log2(math.pi * N / (4 * 131))
def lsum(V, D): return math.log2(sum(math.comb(V, i) for i in range(D + 1)))
res = {}
for D in (4, 5, 6):
    for omega in (2.0, 2.81):
        best = None
        for m in range(2, 12):
            for l in range(1, 70):
                V = m * l + max(0, m - 2) * n
                logp = min(0.0, m * l - math.log2(math.factorial(m)) - n)
                calls = l - logp
                tot = max(calls + omega * lsum(V, D), math.log2(m) + 2 * l) + 1
                if best is None or tot < best[0]:
                    best = (round(tot, 2), m, l, V, round(calls, 2), round(omega * lsum(V, D), 2))
        res[f"D{D}_omega{omega}"] = dict(log2_total=best[0], m=best[1], l=best[2], vars=best[3],
                                         log2_calls=best[4], log2_per_pdp=best[5])
        print(D, omega, res[f"D{D}_omega{omega}"])
res["rho_E0_log2"] = rho
json.dump(res, open(sys.argv[1], "w"), indent=1)
