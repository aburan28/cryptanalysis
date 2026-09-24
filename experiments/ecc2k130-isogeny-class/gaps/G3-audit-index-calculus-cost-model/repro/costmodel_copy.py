"""Index-calculus vs rho cost model for every curve of the ECC2K-130 class.

Model (the standard one, as in pdp-scaling/README.md and GGMP 2020 Thm 2.4/2.5):
  factor base F_V with |F| ~ 2^l points (x in an l-dim subspace; half the x lift, 2 points each),
  unknowns U = 2^(l-1) (points up to sign), relations needed ~ U,
  relation probability per random target  p = min(1, |F|^m / (m! 2^131)),
  PDP calls = U / p,
  LA (sparse, Wiedemann/Lanczos) = m * U^2,
  per-PDP cost c(m,l):  (a) free (oracle: isolates relation count + LA),
                        (a') table: precompute all k-sums once, then 2^((m-k) l) per target
                             (amortised generic decomposition; memory 2^(k l)/k!),
                        (b) meet-in-the-middle 2^(l*ceil(m/2)) group ops (the best MEASURED
                            decomposition; pdp-scaling README: every algebraic engine measured
                            has a steeper l-slope than this),
  Hypothetical GGMP Frobenius-invariant factor base on E0 (only E0 has tau):
     relations / 131 and LA / 131^2 at the same |F|  (GGMP Thm 3.4/3.5 best case, H3 = H1).
  Per-curve density deviation: |F| -> |F| (1 + delta), delta = z * 2^(-l/2); log2 p shifts by
     m * log2(1 + delta).  z = best z an attacker can buy by screening S subspaces (or curves),
     z ~ sqrt(2 ln S).
Output: costmodel.json and a console table.  Pure python3.
"""
import json, math

OUT = "/Volumes/SSD990/ecdlp-hardness-work/gaps/G3-audit-index-calculus-cost-model/repro/"
N = 680564733841876926932320129493409985129
LOG2Q = 131.0
RHO = {"E0 (neg+tau)": 0.5 * math.log2(math.pi * N / (4 * 131)),
       "floor native (neg only)": 0.5 * math.log2(math.pi * N / 4)}
RHO["floor via 263-isogeny to E0"] = RHO["E0 (neg+tau)"]


def lg_add(a, b):
    m = max(a, b)
    return m + math.log2(2 ** (a - m) + 2 ** (b - m))


def cost(m, l, pdp, ggmp=False, delta_bits=0.0):
    U = l - 1
    logp = min(0.0, m * l - math.log2(math.factorial(m)) - LOG2Q + delta_bits)
    red = math.log2(131) if ggmp else 0.0
    rel = max(0.0, U - red)
    calls = rel - logp
    la = math.log2(m) + 2 * rel
    if pdp == "free":
        return lg_add(calls, la), calls, la
    if pdp == "mitm":
        return lg_add(calls + l * math.ceil(m / 2), la), calls, la
    if pdp == "table":
        # precompute all k-sums once (2^(k l)/k! entries), then each target costs 2^((m-k) l)
        best = None
        for k in range(1, m):
            tot = lg_add(k * l - math.log2(math.factorial(k)), calls + (m - k) * l)
            if best is None or tot < best:
                best = tot
        return lg_add(best, la), calls, la
    raise ValueError


table = {}
for pdp in ("free", "mitm", "table"):
    for ggmp in (False, True):
        for m in range(2, 8):
            best = min((cost(m, l, pdp, ggmp)[0], l) for l in range(2, 66))
            tot, calls, la = cost(m, best[1], pdp, ggmp)
            table["%s|%s|m%d" % (pdp, "GGMP-hyp(E0)" if ggmp else "plain", m)] = {
                "best_l": best[1], "log2_total": round(tot, 2), "log2_pdp_calls": round(calls, 2),
                "log2_LA": round(la, 2)}

# density effect at attack sizes: best-of-S screening
dens = {}
for l in (20, 24, 28, 29):
    for S in (263 * 4, 2 ** 20, 2 ** 40):
        zmax = math.sqrt(2 * math.log(S))
        delta = zmax * 2 ** (-l / 2)
        dens["l%d_S2^%.1f" % (l, math.log2(S))] = {
            "z_best": round(zmax, 2), "rel_|F|_gain": delta,
            "log2_relprob_gain_m4": 4 * math.log2(1 + delta), "log2_relprob_gain_m6": 6 * math.log2(1 + delta)}

# pdp-scaling README numbers (read from experiments/pdp-scaling/README.md, not recomputed)
readme = {
    "source": "/Volumes/SSD990/cryptanalysis/.claude/worktrees/ecc2k-130-volcano-descent-49e6d4/experiments/pdp-scaling/README.md",
    "rho_E0_log2": 60.81,
    "rows": [
        {"m": 4, "l": 29, "pdp_calls_log2": 48.6, "budget_per_pdp_log2": 12.2, "mitm_log2": 58, "gap_bits": 46,
         "sat_fit_log2": 195},
        {"m": 5, "l": 28, "pdp_calls_log2": 28.0, "budget_per_pdp_log2": 32.8, "mitm_log2": 84, "gap_bits": 51},
        {"m": 6, "l": 24, "pdp_calls_log2": 24.0, "budget_per_pdp_log2": 36.8, "mitm_log2": 72, "gap_bits": 35},
        {"m": 3, "l": 44, "note": "LA alone exceeds rho", "wdsat_fit_log2": 137}],
    "fits_bits_per_l": {"mitm_m3": 1.93, "sat_m3": 3.95, "sat_m4": 6.97, "wdsat_m3": 3.02, "msolve_m3": 5.25},
    "trace_constraint_gain_bits": "about 1 (constant, all curves with a2 with Tr(a2)=0 and odd n)",
}
json.dump({"rho_log2": RHO, "model": __doc__, "table": table, "density_effect": dens,
           "pdp_scaling_readme": readme}, open(OUT + "costmodel.json", "w"), indent=1)
print("rho:", {k: round(v, 2) for k, v in RHO.items()})
for k, v in table.items():
    print("%-28s %s" % (k, v))
for k, v in dens.items():
    print(k, v)
