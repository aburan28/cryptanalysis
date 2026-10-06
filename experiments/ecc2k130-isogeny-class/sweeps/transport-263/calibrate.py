"""
Calibration for transport-263: cost of F_q operations and of one E0 point addition in the same
Sage/NTL + Python environment used by transport.py, plus the rho baselines.
Writes raw/calibration.json.   Run: sage -python calibrate.py
"""
import sys, os, json, time, random
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecc2k
from sage.all import EllipticCurve, RealField, pi as PI, log, sqrt, set_random_seed
import transport as T

R200 = RealField(200)
N = ecc2k.N
K = ecc2k.field()
rng = random.Random(7)
set_random_seed(7)
els = [K.from_integer(rng.getrandbits(131)) for _ in range(2000)]
els = [u for u in els if u != 0]


def bench(fn, reps):
    best = None
    for _ in range(5):
        c = time.process_time()
        fn(reps)
        d = (time.process_time() - c) / reps
        best = d if best is None else min(best, d)
    return best


def loop_M(n):
    a = els[0]
    for i in range(n):
        a = a * els[i % 1000 + 1]


def loop_S(n):
    a = els[0]
    for i in range(n):
        a = a * a


def loop_I(n):
    for i in range(n):
        els[i % 1000] ** -1


def loop_A(n):
    a = els[0]
    for i in range(n):
        a = a + els[i % 1000 + 1]


def loop_empty(n):
    for i in range(n):
        els[i % 1000 + 1]


E0 = EllipticCurve(K, [1, 0, 0, 0, 1])
E0.set_order(ecc2k.CARD)
pts = [E0.random_point() for _ in range(64)]
tp = [(P[0], P[1]) for P in pts]
one = K(0)


def loop_padd(n):
    ops = T.Ops()
    R = tp[0]
    for i in range(n):
        R = T.padd(R, tp[i % 63 + 1], one, ops)


def loop_sage_add(n):
    R = pts[0]
    for i in range(n):
        R = R + pts[i % 63 + 1]


def loop_tau(n):
    R = tp[0]
    for i in range(n):
        R = (R[0] * R[0], R[1] * R[1])


res = {}
res["loop_overhead_s"] = bench(loop_empty, 200000)
res["M_s"] = bench(loop_M, 200000)
res["S_s"] = bench(loop_S, 200000)
res["I_s"] = bench(loop_I, 50000)
res["A_s"] = bench(loop_A, 200000)
res["E0_affine_add_python_s"] = bench(loop_padd, 50000)     # T.padd: 1I + 2M + 1S (counted formula)
res["E0_add_sage_s"] = bench(loop_sage_add, 20000)
res["tau_python_s"] = bench(loop_tau, 50000)
res["note"] = ("CPU seconds per operation (min over 5 runs, time.process_time) in Sage 10.9/NTL GF(2^131) "
               "with Python loop overhead included; the machine was heavily loaded (load avg ~200 on 14 cores), "
               "CPU time (not wall) is used.")

# rho baselines (expected iterations), recomputed here
rE0 = sqrt(R200(PI) * N / (4 * 131))
rfl = sqrt(R200(PI) * N / 4)
rplain = sqrt(R200(PI) * N / 2)
res["rho_E0_neg_tau_log2"] = float(log(rE0, 2))
res["rho_floor_neg_only_log2"] = float(log(rfl, 2))
res["rho_no_speedup_log2"] = float(log(rplain, 2))
res["N"] = str(N)
# Itoh-Tsujii inversion in F_{2^131}: a^-1 = (a^(2^130-1))^2 ; chain 1,2,4,8,16,32,64,128,130 -> 8 M, 130 S
res["IT_inversion_M"] = 8
res["IT_inversion_S"] = 130
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw", "calibration.json")
json.dump(res, open(out, "w"), indent=1)
print(json.dumps(res, indent=1))
