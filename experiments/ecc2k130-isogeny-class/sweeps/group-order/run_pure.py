"""Per-curve group order / structure checks for all 263 curves, in pure python3 (no Sage, no PARI).

For every curve y^2 + xy = x^3 + a2 x^2 + b of ground_truth.json:
  1. j = 1/b matches j_int.
  2. Mestre AGM (purebin.agm_trace, own code) -> t; #E = q + 1 - t must be 4N.  Run at two
     precisions / warm-up lengths (80 bits, warm 92) and (96 bits, warm 120); both must agree and the
     d-step product must lie in Z_2 (all 130 non-constant coefficients = 0 mod 2^prec).
  3. Point-order proof (independent of any point counting): random points P with [N]P of exact
     order 4 and [4]P of exact order N => ord(P) = 4N => 4N | #E, and 4N is the only multiple of N
     in the Hasse interval => #E = 4N and E(F_q) = <P> is cyclic, Z/4 x Z/N.
  4. 2-torsion: T2 = (0, sqrt b) is the unique point with P = -P (-(x,y) = (x,x+y)); an explicit
     point P4 with x = b^(1/4) satisfies [2]P4 = T2, [4]P4 = O  => 2-primary part Z/4 (not Z/2xZ/2).
  5. Quadratic twist (a2 xor 1): a point R' with [2*263^2]R' of exact order P114 => #E' = q+1+t
     (P114 > 4 sqrt q, so q+1+t is the only multiple of P114 in the Hasse interval).  263-Sylow structure: cyclic Z/263^2 (a point whose
     263-part has order 263^2) or (Z/263)^2 (two independent points of order 263, exponent 263).
Writes raw/pure_results.json and a log.
"""
import json
import math
import random
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/group-order")
from purebin import GF2m, Curve, agm_trace

GT = "/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json"
OUT = "/Volumes/SSD990/ecdlp-hardness-work/group-order/raw/pure_results.json"

q = 1 << 131
N = 680564733841876926932320129493409985129
T_EXPECTED = -22283658519494248867
P114 = 19678316408850118605767852657510239
TW = q + 1 - T_EXPECTED  # placeholder, recomputed from AGM trace below

F = None


def init():
    global F
    F = GF2m(131, (13, 2, 1, 0))


def exact_order_check(E, P, n, primes):
    """True iff [n]P = O and [n/r]P != O for every prime r | n (primes = distinct prime divisors)."""
    if E.mul(n, P) is not None:
        return False
    return all(E.mul(n // r, P) is not None for r in primes)


def work(args):
    label, a2, b, j_int, do_agm2 = args
    t0 = time.time()
    if do_agm2 == "agm96only":
        t_agm2, inZ2b = agm_trace(F, b, prec=96, warm=120)
        return {"label": label, "agm_t_prec96": str(t_agm2), "agm_prec96_in_Z2": inZ2b,
                "seconds": round(time.time() - t0, 1)}
    rng = random.Random("group-order:" + label)
    rec = {"label": label}
    rec["j_ok"] = (F.inv(b) == j_int)
    # ---- AGM point count ----
    t_agm, inZ2 = agm_trace(F, b, prec=80, warm=92)
    rec["agm_t_prec80"] = str(t_agm)
    rec["agm_prec80_in_Z2"] = inZ2
    if do_agm2:
        t_agm2, inZ2b = agm_trace(F, b, prec=96, warm=120)
        rec["agm_t_prec96"] = str(t_agm2)
        rec["agm_prec96_in_Z2"] = inZ2b
        rec["agm_two_precisions_agree"] = (t_agm2 == t_agm)
    t_a2 = t_agm if a2 == 0 else -t_agm  # a2 = 1 is the nontrivial twist (Tr(1) = 1, d odd)
    order_agm = q + 1 - t_a2
    rec["agm_order"] = str(order_agm)
    rec["agm_order_is_4N"] = (order_agm == 4 * N)
    rec["hasse_ok"] = (t_agm * t_agm <= 4 * q)
    rec["t_agm_mod4"] = t_agm % 4
    E = Curve(F, a2, b)
    # ---- exact-order-4N points ----
    # sample random points until two of them have exact order 4N (probability 1/2 each in Z/4N);
    # every sampled point must have [4]P of exact order N and [4N]P = O.
    pts = []
    n_exact = 0
    a_orders = {1: 0, 2: 0, 4: 0, "other": 0}
    while n_exact < 2 and len(pts) < 40:
        P = E.random_point(rng)
        assert E.on_curve(P)
        A = E.mul(N, P)          # 2-primary component
        B = E.mul(4, P)          # N component
        if A is None:
            aord = 1
        elif E.dbl(A) is None:
            aord = 2
        elif E.mul(4, A) is None:
            aord = 4
        else:
            aord = "other"
        a_orders[aord] += 1
        b_ordN = (B is not None) and (E.mul(N, B) is None)
        exact = (aord == 4) and b_ordN
        n_exact += exact
        pts.append({"x": str(P[0]), "two_part_order": aord, "B_order_N": b_ordN, "order_4N": exact})
    rec["points_sampled"] = pts
    rec["two_part_order_counts"] = {str(k): v for k, v in a_orders.items()}
    rec["all_points_killed_by_4N_and_N_part_exact"] = all(p["B_order_N"] for p in pts) and a_orders["other"] == 0
    rec["order_proof_4N"] = (n_exact >= 2) and rec["all_points_killed_by_4N_and_N_part_exact"]
    # ---- 2-torsion / 4-torsion ----
    T2 = (0, F.sqrt(b))
    rec["T2_on_curve"] = E.on_curve(T2) and E.neg(T2) == T2
    x4 = F.sqrt(F.sqrt(b))
    P4 = E.lift_x(x4)
    if P4 is not None:
        rec["P4_exists"] = True
        rec["P4_double_is_T2"] = (E.dbl(P4) == T2)
        rec["P4_order_4"] = (E.mul(4, P4) is None) and (E.dbl(P4) is not None)
    else:
        rec["P4_exists"] = False
    # the doubling x-map is x(2P) = x^2 + b/x^2, so 2P = T2 iff x^4 = b: x4 is the only candidate
    # and E(F_q)[2] = {O, T2}; Z/2 x Z/2 is impossible.
    rec["two_primary"] = "Z/4" if (rec["P4_exists"] and rec["P4_double_is_T2"] and rec["P4_order_4"]) else "?"
    # ---- quadratic twist ----
    Et = Curve(F, a2 ^ 1, b)
    ntw = q + 1 + t_a2  # = q + 1 - (trace of twist)
    rec["twist_order_expected"] = str(ntw)
    rec["twist_factor_ok"] = (ntw == 2 * 263 * 263 * P114)
    tw = {}
    R = Et.random_point(rng)
    C = Et.mul(2 * 263 * 263, R)
    tw["P114_point"] = (C is not None) and (Et.mul(P114, C) is None)
    tw["n_kills"] = Et.mul(ntw, R) is None
    # 2-part of the twist: a2^1 = 1 => no rational point with x = b^(1/4) (trace obstruction)
    tw["P4_exists_on_twist"] = Et.lift_x(x4) is not None
    tw["T2_on_twist"] = Et.on_curve(T2)
    # 263-Sylow: look at the 263-parts D = [2*P114]R of up to 12 random twist points.
    Ds_all = []
    big = None
    for k in range(12):
        Rk = R if k == 0 else Et.random_point(rng)
        Dk = Et.mul(2 * P114, Rk)
        Ds_all.append(Dk)
        if Dk is not None and Et.mul(263, Dk) is not None:
            big = (Rk, Dk)
            break
    tw["sylow_points_examined"] = len(Ds_all)
    if big is not None:
        Rk, Dk = big
        tw["sylow263"] = "Z/263^2"
        tw["ok_sylow"] = Et.mul(263 * 263, Dk) is None
        tw["sylow263_evidence"] = "point whose 263-part has order 263^2 (v_263(#E')=2 => Sylow cyclic)"
        # cyclic overall: a point of exact order ntw
        tw["cyclic_point"] = exact_order_check(Et, Rk, ntw, (2, 263, P114))
    else:
        # every examined 263-part has order <= 263; show two independent points of order 263
        nz = [Dk for Dk in Ds_all if Dk is not None]
        indep = False
        if len(nz) >= 2:
            span = set()
            Mk = None
            for _ in range(263):
                Mk = Et.add(Mk, nz[0])
                span.add(Mk)
            indep = any(Dk not in span for Dk in nz[1:])
        tw["sylow263"] = "(Z/263)^2" if indep else "?"
        tw["ok_sylow"] = indep
        tw["sylow263_evidence"] = ("%d random points all have 263-part of order <= 263 (exponent 263); two of them "
                                   "independent (second not among the 263 multiples of the first)" % len(Ds_all))
        tw["cyclic_point"] = False
    rec["twist"] = tw
    rec["twist_order_ok"] = tw["P114_point"] and tw["n_kills"] and rec["twist_factor_ok"]
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


def main():
    import os
    mode = sys.argv[1] if len(sys.argv) > 1 else "main"   # "main" or "agm96"
    rawdir = os.path.join(os.path.dirname(OUT), "pure")
    os.makedirs(rawdir, exist_ok=True)
    gt = json.load(open(GT))
    assert int(gt["meta"]["N"]) == N and int(gt["meta"]["t"]) == T_EXPECTED
    jobs = []
    for c in gt["curves"]:
        fn = os.path.join(rawdir, "%s.%s.json" % (c["label"], mode))
        if os.path.exists(fn):
            continue
        jobs.append((c["label"], int(c["a2"]), int(c["b_int"]), int(c["j_int"]),
                     False if mode == "main" else "agm96only"))
    print(mode, "jobs to run:", len(jobs), flush=True)
    t0 = time.time()
    with Pool(12, initializer=init) as pool:
        for r in pool.imap_unordered(work, jobs, chunksize=1):
            fn = os.path.join(rawdir, "%s.%s.json" % (r["label"], mode))
            json.dump(r, open(fn + ".part", "w"), indent=1)
            os.replace(fn + ".part", fn)
            print(r["label"], r["seconds"], round(time.time() - t0, 1), flush=True)
    print("done", mode, round(time.time() - t0, 1), flush=True)


def collect():
    """Merge raw/pure/<label>.main.json (+ .agm96.json) into raw/pure_results.json."""
    import os
    rawdir = os.path.join(os.path.dirname(OUT), "pure")
    gt = json.load(open(GT))
    res = {}
    for c in gt["curves"]:
        lab = c["label"]
        r = json.load(open(os.path.join(rawdir, lab + ".main.json")))
        r2 = json.load(open(os.path.join(rawdir, lab + ".agm96.json")))
        r["agm_t_prec96"] = r2["agm_t_prec96"]
        r["agm_prec96_in_Z2"] = r2["agm_prec96_in_Z2"]
        r["agm_two_precisions_agree"] = (r2["agm_t_prec96"] == r["agm_t_prec80"])
        r["seconds_agm96"] = r2["seconds"]
        res[lab] = r
    out = {"meta": {"method": "pure python3 purebin.py: Mestre AGM (prec 80/warm 92 and prec 96/warm 120) + exact point orders, affine arithmetic",
                    "python": sys.version}, "curves": res}
    json.dump(out, open(OUT, "w"), indent=1)
    bad = [r["label"] for r in res.values() if not (r["j_ok"] and r["agm_order_is_4N"] and r["agm_prec80_in_Z2"]
                                           and r["agm_two_precisions_agree"] and r["agm_prec96_in_Z2"]
                                           and r["order_proof_4N"] and r["two_primary"] == "Z/4"
                                           and r["twist_order_ok"] and r["twist"]["ok_sylow"])]
    print("curves", len(res), "bad", bad)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "collect":
        collect()
    else:
        main()
