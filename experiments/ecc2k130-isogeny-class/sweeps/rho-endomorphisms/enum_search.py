"""(3c) Exhaustive enumeration: every alpha = x + y*w0 in the order with norm <= X, testing whether its
eigenvalue on the N-subgroup has multiplicative order < 2^20.  Independent of the CVP code: for each y the
admissible x form an interval, whose eigenvalues form an interval [e_y + x_lo, e_y + x_hi] mod N; we look up
the sorted set S of all 4,902,008 order-<2^20 eigenvalues in that interval (exact, no lattice reduction).
Usage: python3 enum_search.py O263|OK log2X nproc  -> enum_<order>_<log2X>.json
"""
import sys, json, math, time
import numpy as np
from multiprocessing import Pool
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/rho-endomorphisms")
import common_rho as C
from cvp_lib import elements_by_order

which, LOGX, NPROC = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
N = C.N
W, CC = (C.W_O263, C.C_O263) if which == "O263" else (C.W_OK, C.C_OK)
D = 4 * CC - 1
X = 1 << LOGX
SH = 66                                   # coarse key h >> 66 fits in uint64 (N < 2^130)
assert 2 * math.isqrt(X) + 2 < (1 << SH)  # each x-interval touches <= 2 coarse buckets

S = sorted(elements_by_order(N, C.NM1_FACT, 2 ** 20), key=lambda t: t[1])
S_h = [h for d, h in S]
S_d = [d for d, h in S]
KEY = np.array([h >> SH for h in S_h], dtype=np.uint64)


def lookup(a, b):
    """indices i with a <= S_h[i] <= b (0 <= a <= b < N)"""
    i0 = int(np.searchsorted(KEY, np.uint64(a >> SH), "left"))
    i1 = int(np.searchsorted(KEY, np.uint64(b >> SH), "right"))
    return [i for i in range(i0, i1) if a <= S_h[i] <= b]


def work(yr):
    y0, y1 = yr
    hits, npts = [], 0
    e = (y0 * W) % N
    for y in range(y0, y1):
        disc = 4 * X - D * y * y
        if disc >= 0:
            s = math.isqrt(disc)
            xlo, xhi = -((y + s) // 2), (s - y) // 2      # |2x + y| <= s  <=>  Q(x,y) <= X
            if xlo <= xhi:
                npts += xhi - xlo + 1
                lo = (e + xlo) % N
                hi = lo + (xhi - xlo)
                segs = [(lo, hi)] if hi < N else [(lo, N - 1), (0, hi - N)]
                for a, b in segs:
                    for i in lookup(a, b):
                        h = S_h[i]
                        x = xlo + ((h - lo) % N)
                        assert (x + y * W - h) % N == 0
                        qv = x * x + x * y + CC * y * y
                        assert qv <= X
                        hits.append((x, y, S_d[i], qv, h))
        e = (e + W) % N
    return hits, npts


if __name__ == "__main__":
    t0 = time.time()
    ymax = math.isqrt(4 * X // D) + 1
    step = max(1, (2 * ymax + 1) // (NPROC * 16) + 1)
    ranges = [(a, min(a + step, ymax + 1)) for a in range(-ymax, ymax + 1, step)]
    allhits, total = [], 0
    with Pool(NPROC) as pool:
        for hits, npts in pool.imap_unordered(work, ranges):
            allhits += hits
            total += npts
    allhits.sort(key=lambda r: r[3])
    area = 2 * math.pi * X / math.sqrt(D)
    out = {"order": which, "log2X": LOGX, "points_enumerated_incl_y0": total,
           "expected_points_area": area, "y_range": [-ymax, ymax],
           "hits_total": len(allhits),
           "hits_y_nonzero": [dict(x=x, y=y, order=d, norm=str(qv), norm_log2=math.log2(qv), h=str(h))
                              for x, y, d, qv, h in allhits if y != 0],
           "hits_y_zero": [dict(x=x, order=d) for x, y, d, qv, h in allhits if y == 0],
           "seconds": round(time.time() - t0, 1)}
    json.dump(out, open("enum_%s_%d.json" % (which, LOGX), "w"), indent=1)
    print(which, LOGX, "points", total, "area", round(area), "hits", len(allhits),
          "y!=0 hits", len(out["hits_y_nonzero"]), "time", out["seconds"])
    print("first hits:", [(r["x"], r["y"], r["order"], round(r["norm_log2"], 2)) for r in out["hits_y_nonzero"][:12]])
    print("y0 hits:", out["hits_y_zero"][:10])
