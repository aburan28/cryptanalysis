"""(3d) Exact minimum-norm endomorphism for every eigenvalue of order < 2^20.
For each h in F_N^* with ord(h) = d < 2^20 (4,902,008 values), find the minimum-norm alpha in the order
(O_263 or O_K) whose eigenvalue on the N-subgroup is h, by exact 2-D CVP (cvp_lib, self-tested).
Usage: python3 cvp_search.py O263|OK  -> cvp_<order>.json
"""
import sys, json, math, time
from multiprocessing import Pool
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/rho-endomorphisms")
import common_rho as C
from cvp_lib import OrderLattice, elements_by_order

which = sys.argv[1]
N = C.N
if which == "O263":
    W, CC = C.W_O263, C.C_O263
else:
    W, CC = C.W_OK, C.C_OK
BOUND = 2 ** 20
KEEP_BELOW = 2 ** 100          # keep every target whose min norm is below this (for cross-checks)
L = OrderLattice(N, W, CC)


def work(chunk):
    res = []
    for d, h in chunk:
        qv, x, y = L.cvp(h)
        assert (x + y * W - h) % N == 0 and qv == x * x + x * y + CC * y * y
        res.append((d, h, qv, x, y))
    return res


if __name__ == "__main__":
    t0 = time.time()
    targets = list(elements_by_order(N, C.NM1_FACT, BOUND))
    for d, h in targets[:2000]:
        assert C.order_mod_N(h) == d
    print(which, "targets", len(targets), "reduced basis", L.b1, L.b2,
          "Q(b1)/N=%.3f Q(b2)/N=%.3f" % (L.Q(*L.b1) / N, L.Q(*L.b2) / N), flush=True)
    chunks = [targets[i:i + 20000] for i in range(0, len(targets), 20000)]
    per_d = {}
    kept = []
    overall = []
    with Pool(7) as pool:
        for res in pool.imap_unordered(work, chunks):
            for d, h, qv, x, y in res:
                rec = per_d.setdefault(d, {"count": 0, "min": None, "argmin": None, "min_y_nonzero": None,
                                           "argmin_y_nonzero": None, "sum_log2": 0.0})
                rec["count"] += 1
                lq = math.log2(qv)
                rec["sum_log2"] += lq
                if rec["min"] is None or qv < rec["min"]:
                    rec["min"], rec["argmin"] = qv, (x, y, h)
                if y != 0 and (rec["min_y_nonzero"] is None or qv < rec["min_y_nonzero"]):
                    rec["min_y_nonzero"], rec["argmin_y_nonzero"] = qv, (x, y, h)
                if qv < KEEP_BELOW:
                    kept.append({"d": d, "h": str(h), "norm": str(qv), "norm_log2": lq, "x": x, "y": y})
                if y == 0 and d > 2:
                    overall.append(("y0", d, x))
    sqrtD = math.sqrt(4 * CC - 1)
    from math import gcd
    def phi(n):
        r, m, pp = n, n, 2
        while pp * pp <= m:
            if m % pp == 0:
                while m % pp == 0:
                    m //= pp
                r -= r // pp
            pp += 1
        if m > 1:
            r -= r // m
        return r
    table = []
    for d in sorted(per_d):
        rec = per_d[d]
        pred = sqrtD * N / (2 * math.pi * phi(d))      # expected min over phi(d) random cosets
        row = {"d": d, "phi(d)": rec["count"], "min_norm_log2": math.log2(rec["min"]),
               "argmin_xy": rec["argmin"][:2],
               "min_norm_y_nonzero_log2": (math.log2(rec["min_y_nonzero"]) if rec["min_y_nonzero"] else None),
               "argmin_y_nonzero_xy": (rec["argmin_y_nonzero"][:2] if rec["argmin_y_nonzero"] else None),
               "mean_log2_min_norm": rec["sum_log2"] / rec["count"],
               "heuristic_expected_min_log2": math.log2(pred),
               "class_size_with_negation": d if d % 2 == 0 else 2 * d}
        table.append(row)
    nontriv = [r for r in table if r["d"] > 2]
    best = min(nontriv, key=lambda r: r["min_norm_y_nonzero_log2"])
    out = {"order": which, "c": CC, "w": str(W), "N": str(N), "bound_order": BOUND,
           "num_targets": len(targets),
           "reduced_basis": [list(L.b1), list(L.b2)],
           "reduced_basis_Q_over_N": [L.Q(*L.b1) / N, L.Q(*L.b2) / N],
           "per_order_table": table,
           "smallest_norm_over_all_orders_3..2^20_y_nonzero": best,
           "kept_targets_norm_below_2^100": sorted(kept, key=lambda r: r["norm_log2"]),
           "y0_minimisers_with_order_gt_2": overall,
           "seconds": round(time.time() - t0, 1)}
    json.dump(out, open("cvp_%s.json" % which, "w"), indent=1, default=str)
    print(which, "done in", out["seconds"], "s; best nontrivial:", best, "kept:", len(kept), flush=True)
    for r in table[:12]:
        print(r)
