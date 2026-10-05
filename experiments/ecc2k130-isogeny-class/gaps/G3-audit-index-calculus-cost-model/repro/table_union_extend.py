"""Extend the index-calculus sweep's 'table' (amortised k-sum) cost model to large m,
with the tau-union factor base U = union_{i<131} tau^i(F) on E0 (realisable for
combinatorial decomposition: membership = 131 subspace tests; |F| unknowns, 131|F| points;
this is exactly the sweep's 'GGMP-hyp(E0)' row).  Also adds GGMP 3.1 ordered tau-slots
(m! more distinct sums) for the plain factor base.  Uses the sweep's formulas verbatim
(copied from index-calculus/costmodel.py) so the numbers are comparable."""
import json, math, sys
N = 680564733841876926932320129493409985129
LOG2Q = 131.0
RHO_E0 = 0.5 * math.log2(math.pi * N / (4 * 131))
def lg_add(a, b):
    m = max(a, b); return m + math.log2(2 ** (a - m) + 2 ** (b - m))
def cost_table(m, l, union=False, ordered=False):
    # l = log2 |F|; U = l-1 unknowns (points up to sign)
    U = l - 1
    logfact = 0.0 if ordered else math.log2(math.factorial(m))
    if union:
        # factor base U has 131 |F| points, unknowns still |F|/2
        L = l + math.log2(131)
        logp = min(0.0, m * L - math.log2(math.factorial(m)) - LOG2Q)
        rel = U
        best = None
        for k in range(1, m):
            tot = lg_add(k * L - math.log2(math.factorial(k)), rel - logp + (m - k) * L)
            best = tot if best is None or tot < best else best
        la = math.log2(m) + 2 * rel
        return lg_add(best, la)
    logp = min(0.0, m * l - logfact - LOG2Q)
    rel = U
    best = None
    for k in range(1, m):
        tab = k * l - (0.0 if ordered else math.log2(math.factorial(k)))
        tot = lg_add(tab, rel - logp + (m - k) * l)
        best = tot if best is None or tot < best else best
    la = math.log2(m) + 2 * rel
    return lg_add(best, la)
res = {}
for variant in ("plain", "ordered_tau_slots(GGMP3.1)", "tau_union(=GGMP-hyp)"):
    rows = {}
    for m in range(2, 61):
        best = min((cost_table(m, l, union=variant.startswith("tau_union"),
                               ordered=variant.startswith("ordered")), l) for l in range(2, 80))
        rows[m] = dict(log2_total=round(best[0], 3), best_l=best[1])
    res[variant] = rows
    mn = min(rows.items(), key=lambda kv: kv[1]["log2_total"])
    print(variant, "min over m<=60:", mn, " m=7:", rows[7], " m=60:", rows[60])
res["rho_E0_log2"] = RHO_E0
res["note"] = ("Cost unit = one table lookup / group op; ignores memory (table 2^(kL)/k! entries) "
               "and all constants; the sweep's own model.")
json.dump(res, open(sys.argv[1], "w"), indent=1)
