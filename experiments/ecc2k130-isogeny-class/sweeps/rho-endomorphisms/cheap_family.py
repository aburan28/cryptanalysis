"""(3) explicit 'cheap' endomorphisms of the floor curves: alpha in O_263 with norm = l * 2^k,
l = 1 or an odd prime <= 2000, k <= 110 (one horizontal l-isogeny composed with Frobenius / Verschiebung powers).
All solutions from PARI qfbsolve(Qfb(1,1,121046), n, 3) (all solutions up to sign, incl. imprimitive).
Also: exact orders of ALL alpha with y != 0 and norm <= 2^28 (smallest orders found).
-> cheap_family.json"""
import sys, json, math, time
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/rho-endomorphisms")
import common_rho as C
from multiprocessing import Pool

N, W, CC = C.N, C.W_O263, C.C_O263
LOGX = 28
X = 1 << LOGX
D = 4 * CC - 1
def work(yr):
    best = []
    cnt = 0
    hist = {}
    for y in range(*yr):
        if y == 0:
            continue
        disc = 4 * X - D * y * y
        if disc < 0:
            continue
        s = math.isqrt(disc)
        for x in range(-((y + s) // 2), (s - y) // 2 + 1):
            o = C.order_mod_N(x + y * W)
            cnt += 1
            idx = (N - 1) // o
            hist[idx] = hist.get(idx, 0) + 1
            best.append((o, x, y))
            if len(best) > 200:
                best.sort(); best = best[:20]
    best.sort()
    return best[:20], cnt, hist
if __name__ == "__main__":
    from sage.all import pari, primes, factor
    t0 = time.time()
    fam = []
    for l in [1] + list(primes(3, 2001)):
        for k in range(0, 111):
            n = l * 2 ** k
            sols = pari("qfbsolve(Qfb(1,1,%d), %d, 3)" % (CC, n))
            for s_ in sols:
                x, y = int(s_[0]), int(s_[1])
                if y == 0:
                    continue
                assert x * x + x * y + CC * y * y == n
                for sg in (1, -1):
                    e = (sg * (x + y * W)) % N
                    o = C.order_mod_N(e)
                    fam.append({"l": l, "k": k, "x": sg * x, "y": sg * y, "order_log2": math.log2(o), "order": str(o)})
    fam.sort(key=lambda r: r["order_log2"])
    ls_present = sorted(set(r["l"] for r in fam))
    out = {"cheap_family": {"description": "alpha in O_263, y != 0, norm = l*2^k, l in {1} U odd primes <= 2000, k <= 110",
                            "num_elements": len(fam), "l_values_occurring": ls_present,
                            "min_order_log2": fam[0]["order_log2"] if fam else None,
                            "smallest_10": fam[:10],
                            "smallest_norm_examples": sorted(fam, key=lambda r: r["l"] * 2 ** r["k"])[:10]}}
    print("cheap family:", len(fam), "min order log2", out["cheap_family"]["min_order_log2"], time.time() - t0, flush=True)

    ymax = math.isqrt(4 * X // D) + 1
    rng_ = [(a, min(a + 1, ymax + 1)) for a in range(-ymax, ymax + 1)]
    allbest, total, H = [], 0, {}
    with Pool(12) as pool:
        for b_, c_, h_ in pool.imap_unordered(work, rng_):
            allbest += b_; total += c_
            for k_, v_ in h_.items():
                H[k_] = H.get(k_, 0) + v_
    allbest.sort()
    out["all_y_nonzero_norm_le_2^28"] = {
        "num_elements": total,
        "smallest_orders": [{"order_log2": math.log2(o), "order": str(o), "x": x, "y": y,
                             "norm_log2": math.log2(x * x + x * y + CC * y * y),
                             "index_(N-1)/order": str((N - 1) // o),
                             "index_factored": str(factor((N - 1) // o))} for o, x, y in allbest[:10]],
        "largest_index": str(max(H)), "index_histogram_top": sorted(((int(k), v) for k, v in H.items()), key=lambda kv: -kv[0])[:15]}
    out["seconds"] = round(time.time() - t0, 1)
    json.dump(out, open("cheap_family.json", "w"), indent=1, default=str)
    print("norm<=2^28:", total, out["all_y_nonzero_norm_le_2^28"]["smallest_orders"][:3], out["seconds"])
