#!/usr/bin/env python3
"""G3 audit of the index-calculus cost model for the ECC2K-130 isogeny class.

Audits index-calculus/costmodel.py (+ costmodel.json) and redteam-1/scripts/
{table_union_extend.py, bounds.py (section F), semaev2015_bound.py}.

  (a) formula-by-formula comparison with a first-principles model (relation probability for
      m-term decompositions over F = {P : x(P) in V_l}; points up to sign; the Z/4 cofactor;
      the m! symmetry; GGMP 2020 Sec 3.1 ordered tau-slots; linear algebra; table / MITM).
      The relation-probability claims are backed by exact toy counts (scripts/relprob.c,
      raw/relprob.jsonl) and H1-vs-H2 solver timings (scripts/pdp_slots.py, raw/pdp_slots_*.jsonl).
  (b) generic-algorithm analysis of the table / MITM rows, memory at their optima.
  (c) break-even PDP cost per call for m = 3..6 vs measured PDP costs (repo pdp-scaling CSVs,
      redteam-1 toy_pdp_summary.json, this audit's msolve runs), extrapolated to n = 131 with an
      explicit fit, plus a fit-free bound.
  (d) Petit-Quisquater (RT6) and Semaev-2015 (RT7) recomputed, verbatim and corrected.
Writes raw/audit.json and margins.json.  Pure python3 + numpy.
"""
import csv, glob, json, math, os, statistics as st, sys
import numpy as np

G = "/Volumes/SSD990/ecdlp-hardness-work/gaps/G3-audit-index-calculus-cost-model/"
REPO = ("/Volumes/SSD990/cryptanalysis/.claude/worktrees/ecc2k-130-volcano-descent-49e6d4/"
        "experiments/pdp-scaling/")
IC = "/Volumes/SSD990/ecdlp-hardness-work/index-calculus/"
RT = "/Volumes/SSD990/ecdlp-hardness-work/redteam-1/"

N = 680564733841876926932320129493409985129
CARD = 4 * N
LOG2E = math.log2(CARD)          # log2 #E0(F_q) = 131 - 2^-66.7
LOG2Q = 131.0
RHO = 0.5 * math.log2(math.pi * N / (4 * 131))       # rho on E0 with <-1,tau>, iterations
RHO_NEG = 0.5 * math.log2(math.pi * N / 4)           # rho with negation only
GENERIC = 0.5 * math.log2(N / 262)                   # Shoup-type bound with the <-1,tau> oracle
M_PER_IT = 6.0                                       # task constant: 2^60.809 it ~ 2^63.4 F_q-mults
LOG2_MIT = math.log2(M_PER_IT)
RHO_M = RHO + LOG2_MIT
FQRUNS = [json.loads(x) for x in open(G + "raw/fqmul_bench_runs.jsonl") if x.strip()]
T_M_LOCAL = min(r["ns_per_mul_throughput4"] for r in FQRUNS) * 1e-9   # measured, M4 Pro, PMULL schoolbook, best of runs
T_M_README = 1e-7 / M_PER_IT                         # README: 1 rho iteration = 1e-7 s
T_M_CONS = max(T_M_LOCAL, T_M_README)                # conservative: fewer mults per second

out = {"constants": dict(log2_N=math.log2(N), log2_card=LOG2E, rho_E0_it=RHO, rho_neg_only_it=RHO_NEG,
                         generic_bound_sqrt_N_over_262=GENERIC, M_per_iteration=M_PER_IT,
                         rho_E0_Fq_mults=RHO_M, t_M_local_s=T_M_LOCAL, t_M_readme_s=T_M_README,
                         t_M_conservative_s=T_M_CONS)}


def lg_add(*xs):
    xs = [x for x in xs if x is not None and x > -1e300]
    m = max(xs)
    return m + math.log2(sum(2 ** (x - m) for x in xs))


def lg_sub(a, b):  # log2(2^a - 2^b), a > b
    return a + math.log2(1 - 2 ** (b - a)) if b < a else None


def lf(k):
    return math.log2(math.factorial(k))


def lcomb(n, k):
    return math.log2(math.comb(n, k))


# ------------------------------------------------------------------------------------------
# 1. verbatim re-implementations, checked against the stored JSON
# ------------------------------------------------------------------------------------------
def cm_cost(m, l, pdp, ggmp=False):  # copied from index-calculus/costmodel.py
    U = l - 1
    logp = min(0.0, m * l - math.log2(math.factorial(m)) - LOG2Q)
    red = math.log2(131) if ggmp else 0.0
    rel = max(0.0, U - red)
    calls = rel - logp
    la = math.log2(m) + 2 * rel
    if pdp == "free":
        return lg_add(calls, la), calls, la, None
    if pdp == "mitm":
        return lg_add(calls + l * math.ceil(m / 2), la), calls, la, None
    best = None
    for k in range(1, m):
        tot = lg_add(k * l - math.log2(math.factorial(k)), calls + (m - k) * l)
        if best is None or tot < best[0]:
            best = (tot, k)
    return lg_add(best[0], la), calls, la, best[1]


def rt3_cost(m, l, union=False, ordered=False):  # copied from redteam-1 table_union_extend.py
    U = l - 1
    logfact = 0.0 if ordered else math.log2(math.factorial(m))
    if union:
        L = l + math.log2(131)
        logp = min(0.0, m * L - math.log2(math.factorial(m)) - LOG2Q)
        rel = U
        best = None
        for k in range(1, m):
            tot = lg_add(k * L - math.log2(math.factorial(k)), rel - logp + (m - k) * L)
            if best is None or tot < best[0]:
                best = (tot, k, k * L - math.log2(math.factorial(k)))
        la = math.log2(m) + 2 * rel
        return lg_add(best[0], la), best[1], best[2]
    logp = min(0.0, m * l - logfact - LOG2Q)
    rel = U
    best = None
    for k in range(1, m):
        tab = k * l - (0.0 if ordered else math.log2(math.factorial(k)))
        tot = lg_add(tab, rel - logp + (m - k) * l)
        if best is None or tot < best[0]:
            best = (tot, k, tab)
    la = math.log2(m) + 2 * rel
    return lg_add(best[0], la), best[1], best[2]


cmj = json.load(open(IC + "costmodel.json"))
chk = {"costmodel_rows": 0, "costmodel_mismatch": []}
cm_rows = {}
for key, v in cmj["table"].items():
    pdp, var, mm = key.split("|")
    m = int(mm[1:])
    ggmp = var.startswith("GGMP")
    best = min((cm_cost(m, l, pdp, ggmp)[0], l) for l in range(2, 66))
    tot, calls, la, k = cm_cost(m, best[1], pdp, ggmp)
    ok = (best[1] == v["best_l"] and round(tot, 2) == v["log2_total"] and round(calls, 2) == v["log2_pdp_calls"]
          and round(la, 2) == v["log2_LA"])
    chk["costmodel_rows"] += 1
    if not ok:
        chk["costmodel_mismatch"].append(key)
    table_T = None
    if pdp == "table":
        table_T = k * best[1] - lf(k)
    cm_rows[key] = dict(stored=v, k=k, table_log2_entries=table_T)
rtj = json.load(open(RT + "raw/table_union_extend.json"))
chk["rt3_rows"] = 0
chk["rt3_mismatch"] = []
rt3_rows = {}
for variant in ("plain", "ordered_tau_slots(GGMP3.1)", "tau_union(=GGMP-hyp)"):
    for m in range(2, 61):
        un, od = variant.startswith("tau_union"), variant.startswith("ordered")
        best = min((rt3_cost(m, l, un, od)[0], l) for l in range(2, 80))
        tot, k, T = rt3_cost(m, best[1], un, od)
        v = rtj[variant][str(m)]
        chk["rt3_rows"] += 1
        if not (round(tot, 3) == v["log2_total"] and best[1] == v["best_l"]):
            chk["rt3_mismatch"].append((variant, m))
        rt3_rows[(variant, m)] = dict(total=tot, l=best[1], k=k, T=T)
out["verbatim_reproduction"] = chk
print("verbatim:", chk["costmodel_rows"], "costmodel rows,", len(chk["costmodel_mismatch"]), "mismatch;",
      chk["rt3_rows"], "RT3 rows,", len(chk["rt3_mismatch"]), "mismatch", flush=True)

# ------------------------------------------------------------------------------------------
# 2. toy evidence for the relation probability (relprob.c)
# ------------------------------------------------------------------------------------------
rp = [json.loads(x) for x in open(G + "raw/relprob.jsonl") if x.strip()]
for f in sorted(glob.glob(G + "raw/relprob_n31_*.json")):
    txt = open(f).read().strip()
    if txt:
        rp.append(json.loads(txt))
_seen = {}
for r in rp:
    _seen[(r["n"], r["m"], r["l"], r["mode"], r["seed"])] = r
rp = list(_seen.values())
tev = {}
for key in sorted({r["mode"] for r in rp}):
    sub = [r for r in rp if r["mode"] == key]
    kert = key.endswith("kertr")
    xr = [r["x_cov_frac"] / ((0.5 * (1 - math.exp(-2 * r["sums"] / r["cardE"]))) if kert else (1 - math.exp(-r["sums"] / r["cardE"])))
          for r in sub]
    big = [r for r in sub if r["F_size"] >= 1000]
    xr_big = [r["hit_G"] / ((1 - math.exp(-2 * r["sums"] / r["cardE"])) if kert else (1 - math.exp(-r["sums"] / r["cardE"]))) for r in big]
    gr = [r["hit_G"] / ((1 - math.exp(-2 * r["sums"] / r["cardE"])) if kert else (1 - math.exp(-r["sums"] / r["cardE"])))
          for r in sub]
    # the costmodel formula evaluated with the TRUE |F| (so only the combinatorics is tested)
    cmr = [r["hit_G"] / (1 - math.exp(-(r["F_size"] ** r["m"] / (math.factorial(r["m"]) if key.startswith("plain") else 1)) / 2 ** r["n"]))
           for r in sub]
    tev[key] = dict(runs=len(sub), cells=sorted({(r["n"], r["m"], r["l"]) for r in sub}),
                    x_coverage_over_poisson_M_over_E=[min(xr), st.median(xr), max(xr)],
                    G_target_hit_over_prediction=[min(gr), st.median(gr), max(gr)],
                    G_target_hit_over_costmodel_formula_true_F=[min(cmr), st.median(cmr), max(cmr)],
                    G_targets_sampled_per_run=sub[0]["n_G"],
                    G_target_hit_over_prediction_cells_with_F_ge_1000=([min(xr_big), st.median(xr_big), max(xr_big)] if xr_big else None),
                    note="x-coverage prediction: 1-exp(-M/#E); ker-Tr: sums lie in 2E so 0.5(1-exp(-2M/#E)) of all x, and G-targets see 1-exp(-2M/#E). Deviations up to -27% occur only at |F| <= 60 (m = 3, 4), where multisets with repeated or cancelling points (P, -P) are a sizeable fraction of M.")
out["toy_relation_probability"] = tev

# H1 vs H2 (msolve, plain vs ordered tau-slots)
ps = []
for f in glob.glob(G + "raw/pdp_slots_m*.jsonl.part_*"):
    ps += [json.loads(x) for x in open(f)]
h12 = {}
for mm in sorted({r["m"] for r in ps}):
    for n in sorted({r["n"] for r in ps if r["m"] == mm}):
        for l in sorted({r["l"] for r in ps if r["m"] == mm and r["n"] == n}):
            for tg in ("planted", "random"):
                a = [r["cpu"] for r in ps if (r["m"], r["n"], r["l"], r["target"], r["variant"]) == (mm, n, l, tg, "plain") and r["cpu"] is not None and r["status"] in ("gb", "unsat")]
                b = [r["cpu"] for r in ps if (r["m"], r["n"], r["l"], r["target"], r["variant"]) == (mm, n, l, tg, "ordered") and r["cpu"] is not None and r["status"] in ("gb", "unsat")]
                if a and b:
                    h12[f"m{mm}_n{n}_l{l}_{tg}"] = dict(plain_median_s=st.median(a), ordered_median_s=st.median(b),
                                                        n_plain=len(a), n_ordered=len(b),
                                                        log2_H2_over_H1=math.log2(st.median(b) / st.median(a)),
                                                        log2_m_factorial=lf(mm))
sol = {}
for r in ps:
    if r["target"] == "planted" and "solutions" in r:
        sol.setdefault(f"m{r['m']}_{r['variant']}", set()).add((r["solutions"], r["verified_solutions"]))
out["H1_vs_H2_msolve"] = dict(cells=h12, planted_solution_counts={k: sorted(v) for k, v in sol.items()},
                              timeouts=sum(1 for r in ps if r["status"] == "timeout"), runs=len(ps),
                              timeout_rows=[{k: r.get(k) for k in ("n", "m", "l", "variant", "target", "cpu_at_timeout", "wall")}
                                            for r in ps if r["status"] == "timeout"],
                              m4_l4_rows=[{k: r.get(k) for k in ("n", "variant", "target", "status", "cpu", "cpu_at_timeout", "wall")}
                                          for r in ps if r["m"] == 4 and r["l"] == 4])
hvals = {}
for mm in sorted({r["m"] for r in ps}):
    vs = [v["log2_H2_over_H1"] for k, v in h12.items() if k.startswith(f"m{mm}_")]
    vs_big = [v["log2_H2_over_H1"] for k, v in h12.items() if k.startswith(f"m{mm}_") and v["plain_median_s"] > 1.0]
    hvals[mm] = dict(all_cells=[min(vs), st.median(vs), max(vs)] if vs else None,
                     cells_over_1s=[min(vs_big), st.median(vs_big), max(vs_big)] if vs_big else None,
                     net_gain_bits_median=lf(mm) - st.median(vs) if vs else None)
out["H1_vs_H2_summary"] = hvals

# ------------------------------------------------------------------------------------------
# 3. corrected model
# ------------------------------------------------------------------------------------------
def model(m, l, pdp="free", kertr=False, ordered=False, union=False, la_c=1.0, la_in_M=True,
          multiset_scan=True, cap=True, mem_cap=None, pdp_log2_it=0.0, rel_plus1=True):
    """log2 cost in rho-iteration units (1 group op = 1 iteration; PDP 'free' = 1 iteration)."""
    if ordered and m * l > 131:
        return None
    U = l - 1
    rel = math.log2(2 ** U + 1) if rel_plus1 else U
    L = l + math.log2(131) if union else l
    logp = m * L - (0.0 if ordered else lf(m)) - LOG2E + (1.0 if kertr else 0.0)
    if cap:
        logp = min(0.0, logp)
    calls = rel - logp
    la = math.log2(la_c) + math.log2(m) + 2 * U - (LOG2_MIT if la_in_M else 0.0)
    res = dict(calls=calls, la=la, logp=logp)
    if pdp == "free":
        res["total"] = lg_add(calls + pdp_log2_it, la)
        return res
    if pdp == "mitm":
        k = math.ceil(m / 2)
        if ordered:
            c = lg_add(k * L, (m - k) * L)
        else:
            c = lg_add(k * L - lf(k), (m - k) * L - lf(m - k))
        res["total"] = lg_add(calls + c, la)
        res["per_call"] = c
        return res
    best = None
    for k in range(1, m):
        T = k * L - (0.0 if ordered else lf(k))
        if mem_cap is not None and T > mem_cap:
            continue
        scan = (m - k) * L - (lf(m - k) if (multiset_scan and not ordered) else 0.0)
        tot = lg_add(T, calls + scan)
        if best is None or tot < best[0]:
            best = (tot, k, T, scan)
    if best is None:
        return None
    res.update(total=lg_add(best[0], la), k=best[1], T=best[2], scan=best[3])
    return res


def best_over_l(m, lr=range(1, 132), **kw):
    b = None
    for l in lr:
        r = model(m, l, **kw)
        if r is None:
            continue
        if b is None or r["total"] < b[1]["total"]:
            b = (l, r)
    return b


fam = {}
for pdp in ("free", "mitm", "table"):
    for name, kw in [("costmodel_formula_l>=2", dict(kertr=False, la_in_M=False, multiset_scan=False, rel_plus1=False, lr=range(2, 66))),
                     ("corrected_plain", dict(kertr=True)),
                     ("corrected_ordered_tau_slots", dict(kertr=True, ordered=True)),
                     ("corrected_tau_union", dict(kertr=True, union=True))]:
        if pdp != "table" and name == "corrected_tau_union":
            continue
        rows = {}
        for m in range(2, 132 if pdp == "table" else 41):
            kw2 = dict(kw)
            lr = kw2.pop("lr", range(1, 132))
            b = best_over_l(m, lr=lr, pdp=pdp, **kw2)
            if b is None:
                continue
            l, r = b
            rows[m] = dict(l=l, total=round(r["total"], 3), calls=round(r["calls"], 3), la=round(r["la"], 3),
                           k=r.get("k"), table_log2_entries=(round(r["T"], 2) if "T" in r else None),
                           boundary_l=(l == min(lr)))
        mn = min(rows.items(), key=lambda kv: kv[1]["total"])
        fam[f"{pdp}|{name}"] = dict(best_m=mn[0], best=mn[1], rows=rows)
out["families"] = fam
for k, v in fam.items():
    print("%-44s best m=%-3d %s" % (k, v["best_m"], v["best"]), flush=True)

# memory-capped tables
memcap = {}
for cap in (40, 50, 60):
    for name, kw in [("corrected_plain", dict(kertr=True)), ("corrected_ordered_tau_slots", dict(kertr=True, ordered=True)),
                     ("corrected_tau_union", dict(kertr=True, union=True))]:
        b = None
        for m in range(2, 132):
            r = best_over_l(m, pdp="table", mem_cap=cap, **kw)
            if r and (b is None or r[1]["total"] < b[2]["total"]):
                b = (m, r[0], r[1])
        memcap[f"table|{name}|mem<=2^{cap}"] = dict(m=b[0], l=b[1], total=round(b[2]["total"], 3),
                                                   log2_entries=round(b[2]["T"], 2))
out["table_memory_capped"] = memcap

# ------------------------------------------------------------------------------------------
# 4. (b) generic analysis of every table / MITM row in costmodel.json and RT3
# ------------------------------------------------------------------------------------------
gen = {"generic_bound_log2": GENERIC, "rho_log2": RHO, "rows_below_generic_bound": [], "rows": {}}
for key, v in cm_rows.items():
    pdp = key.split("|")[0]
    if pdp in ("mitm", "table"):
        tot = v["stored"]["log2_total"]
        gen["rows"]["costmodel:" + key] = dict(total=tot, l=v["stored"]["best_l"], generic=True,
                                               table_log2_entries=v["table_log2_entries"],
                                               boundary_l2=(v["stored"]["best_l"] == 2))
        if tot < GENERIC:
            gen["rows_below_generic_bound"].append("costmodel:" + key)
for (variant, m), v in rt3_rows.items():
    gen["rows"][f"RT3:{variant}|m{m}"] = dict(total=round(v["total"], 3), l=v["l"], generic=True,
                                              table_log2_entries=round(v["T"], 2), boundary_l2=(v["l"] == 2))
    if v["total"] < GENERIC:
        gen["rows_below_generic_bound"].append(f"RT3:{variant}|m{m}")
tabrows = [r for k, r in gen["rows"].items() if r["table_log2_entries"] is not None]
gen["table_rows"] = len(tabrows)
gen["table_rows_min_log2_entries_at_optimum"] = min(r["table_log2_entries"] for r in tabrows)
gen["table_rows_with_entries_over_2^50"] = sum(1 for r in tabrows if r["table_log2_entries"] > 50)
gen["rows_with_optimum_at_l_lower_boundary_2"] = sorted(k for k, r in gen["rows"].items() if r["boundary_l2"])
gen["min_total_over_all_generic_rows"] = min(r["total"] for r in gen["rows"].values())
# analytic floor of the model's own table family: total >= 1 + (rel + LOG2Q + log2(m!/k!)) / 2
gen["model_table_floor"] = dict(
    ordered_rel1=1 + (1 + LOG2Q) / 2,
    formula="T + 2^(rel + 131 + log2(m!/k!)) / T >= 2^(1 + (rel + 131 + log2(m!/k!))/2); ordered: m!/k! -> 1",
    decomposition_of_RT3_67_0_minus_rho={
        "cofactor_4 (collision in E, not G): 0.5*log2(4)": 1.0,
        "no <-1,tau> class reduction: 0.5*log2(262)": 0.5 * math.log2(262),
        "one unknown + BSGS table/scan balance (T + S = 2 sqrt): 1 + 0.5*rel(=1)": 1.5,
        "rho constant: -0.5*log2(pi/2)": -0.5 * math.log2(math.pi / 2),
        "sum": 1.0 + 0.5 * math.log2(262) + 1.5 - 0.5 * math.log2(math.pi / 2),
        "RT3 67.0 - rho": 67.0 - RHO})
out["generic_analysis"] = gen

# ------------------------------------------------------------------------------------------
# 5. (c) break-even PDP cost per call
# ------------------------------------------------------------------------------------------
def budget(m, l, variant):
    """log2 of the PDP cost per call (rho iterations) at which total = rho."""
    if variant == "costmodel":
        U = l - 1; rel = U
        logp = min(0.0, m * l - lf(m) - LOG2Q); la = math.log2(m) + 2 * U
    elif variant == "readme":
        rel = l; U = l
        logp = min(0.0, m * l - lf(m) - LOG2Q); la = math.log2(m) + 2 * l
    else:
        U = l - 1; rel = math.log2(2 ** U + 1)
        ordered = variant.startswith("ordered")
        if ordered and m * l > 131:
            return None
        logp = min(0.0, m * l - (0.0 if ordered else lf(m)) - LOG2E + 1.0)
        la_c = 3.0 if variant.endswith("wiedemann") else 1.0
        la = math.log2(la_c * m) + 2 * U - LOG2_MIT
    calls = rel - logp
    rem = lg_sub(RHO, la)
    if rem is None:
        return None
    return dict(budget_it=rem - calls, calls=calls, la_it=la)


BVAR = ["costmodel", "readme", "corrected_plain", "corrected_plain_wiedemann", "ordered_tau_slots(H2=H1)"]
be = {}
for m in (3, 4, 5, 6, 7, 8):
    for var in BVAR:
        bb = None
        for l in range(2, 80):
            r = budget(m, l, var)
            if r and (bb is None or r["budget_it"] > bb[1]["budget_it"]):
                bb = (l, r)
        if bb is None:
            be[f"m{m}|{var}"] = dict(feasible=False, note="LA alone >= rho for every l with calls < rho, or calls > rho")
            # best free total for information
            continue
        l, r = bb
        be[f"m{m}|{var}"] = dict(feasible=r["budget_it"] > 0, l_opt=l, log2_calls=round(r["calls"], 3),
                                 log2_LA_it=round(r["la_it"], 3), log2_budget_it=round(r["budget_it"], 3),
                                 log2_budget_Fq_mults=round(r["budget_it"] + LOG2_MIT, 3),
                                 budget_seconds_at_t_M_conservative=(2 ** (r["budget_it"] + LOG2_MIT)) * T_M_CONS)
# free-PDP optimum for m = 3 (to show infeasibility) per variant
free3 = {}
for var, kw in [("costmodel", dict(kertr=False, la_in_M=False, rel_plus1=False)),
                ("corrected_plain", dict(kertr=True)), ("corrected_ordered", dict(kertr=True, ordered=True))]:
    b = best_over_l(3, lr=range(2, 80), pdp="free", **kw)
    free3[var] = dict(l=b[0], total=round(b[1]["total"], 3), margin=round(b[1]["total"] - RHO, 3))
out["break_even"] = dict(budgets=be, m3_free_pdp_optimum=free3)
for k, v in be.items():
    print("budget", k, v, flush=True)

# ------------------------------------------------------------------------------------------
# 6. measured PDP costs: fits and bounds
# ------------------------------------------------------------------------------------------
rows = []
for f in sorted(glob.glob(REPO + "results/*.csv")):
    for r in csv.DictReader(open(f)):
        if r["status"] in ("solved", "sat") and r["curve"] == "koblitz":
            rows.append(dict(engine=r["engine"], m=int(r["m"]), n=int(r["n"]), l=int(r["l"]), s=float(r["seconds"]),
                             src=os.path.basename(f)))
        elif r["status"] == "timeout" and r["curve"] == "koblitz":
            rows.append(dict(engine=r["engine"], m=int(r["m"]), n=int(r["n"]), l=int(r["l"]), s=None,
                             timeout=float(r["seconds"]), src=os.path.basename(f)))
# toy_pdp_summary (redteam-1): m = 3 F4 runs on E0/floor/control, medians
tps = json.load(open(RT + "raw/toy_pdp_summary.json"))
for cell, d in tps.items():
    n = int(cell.split("_")[0][1:]); l = int(cell.split("_")[1][1:])
    for kind in ("E0", "floor", "control"):
        rows.append(dict(engine="toyF4(redteam-1)", m=3, n=n, l=l, s=d[kind]["cpu_median"], src="toy_pdp_summary:" + kind))
# this audit's msolve runs (plain and ordered; planted and random)
for r in ps:
    if r["cpu"] is not None and r["status"] in ("gb", "unsat"):
        rows.append(dict(engine=f"msolve-audit-{r['variant']}-{r['target']}", m=r["m"], n=r["n"], l=r["l"], s=r["cpu"],
                         src="pdp_slots"))
    elif r["status"] == "timeout":
        # lower bound = CPU seconds consumed before the wall-clock limit (machine was shared)
        rows.append(dict(engine=f"msolve-audit-{r['variant']}-{r['target']}", m=r["m"], n=r["n"], l=r["l"], s=None,
                         timeout=(r.get("cpu_at_timeout") or 1500.0), src="pdp_slots"))

fits = {}
for eng in sorted({r["engine"] for r in rows}):
    for m in sorted({r["m"] for r in rows if r["engine"] == eng}):
        sub = [r for r in rows if r["engine"] == eng and r["m"] == m and r["s"] is not None and r["s"] > 0]
        ls = sorted({r["l"] for r in sub}); ns = sorted({r["n"] for r in sub})
        if len(sub) < 4 or len(ls) < 2:
            continue
        X = np.array([[1.0, r["l"], r["n"]] for r in sub]) if len(ns) > 1 else np.array([[1.0, r["l"]] for r in sub])
        y = np.array([math.log2(r["s"]) for r in sub])
        coef, res, rk, sv = np.linalg.lstsq(X, y, rcond=None)
        dof = max(1, len(sub) - X.shape[1])
        resid = y - X @ coef
        s2 = float(resid @ resid) / dof
        cov = s2 * np.linalg.inv(X.T @ X)
        se = np.sqrt(np.diag(cov))
        fit = dict(rows=len(sub), l_range=[min(ls), max(ls)], n_values=ns, a=float(coef[0]), c_bits_per_l=float(coef[1]),
                   c_se=float(se[1]), d_bits_per_n=(float(coef[2]) if len(ns) > 1 else None),
                   d_se=(float(se[2]) if len(ns) > 1 else None), resid_sd=math.sqrt(s2))
        # largest-l measured cost (smallest over n) -> fit-free bound ingredient
        lmax = max(ls)
        top = [r for r in sub if r["l"] == lmax]
        fit["largest_l"] = lmax
        fit["min_seconds_at_largest_l"] = min(r["s"] for r in top)
        fit["n_of_min_at_largest_l"] = min(top, key=lambda r: r["s"])["n"]
        tos = [r for r in rows if r["engine"] == eng and r["m"] == m and r["s"] is None]
        fit["timeouts"] = len(tos)
        fits[f"{eng}|m{m}"] = fit
out["measured_fits"] = fits


def fit_eval(f, l, n):
    v = f["a"] + f["c_bits_per_l"] * l
    if f["d_bits_per_n"] is not None:
        v += f["d_bits_per_n"] * n
    return v


cmp = {}
for m in (3, 4, 5, 6):
    for var in ("corrected_plain", "ordered_tau_slots(H2=H1)", "costmodel", "readme"):
        b = be.get(f"m{m}|{var}")
        if b is None:
            continue
        entry = dict(budget=b)
        if not b.get("feasible", False) or "l_opt" not in b:
            entry["verdict"] = "no PDP budget: index calculus cannot tie rho at this m even with a free PDP"
            cmp[f"m{m}|{var}"] = entry
            continue
        l0, bM = b["l_opt"], b["log2_budget_Fq_mults"]
        ev = {}
        for key, f in fits.items():
            eng, fm = key.split("|")
            if int(fm[1:]) != m or eng == "mitm":   # python MITM: exponent exact, time constant meaningless
                continue
            s131 = fit_eval(f, l0, 131)
            s61 = fit_eval(f, l0, 61) if f["d_bits_per_n"] is not None else None
            toM = -math.log2(T_M_CONS)
            ev[eng] = dict(fit_log2_seconds_n131=round(s131, 2), fit_log2_Fq_mults_n131=round(s131 + toM, 2),
                           gap_bits_n131=round(s131 + toM - bM, 2),
                           fit_log2_Fq_mults_n61=(round(s61 + toM, 2) if s61 is not None else None),
                           gap_bits_n61=(round(s61 + toM - bM, 2) if s61 is not None else None),
                           c_bits_per_l=round(f["c_bits_per_l"], 3), fit_l_range=f["l_range"])
            # fit-free bound: cost(l_opt, 131) >= cost(lmax, n*) * 2^{min(0, d - 2 se) (131 - n*)}
            dlo = 0.0
            if f["d_bits_per_n"] is not None:
                dlo = min(0.0, f["d_bits_per_n"] - 2 * f["d_se"])
            lbA = math.log2(f["min_seconds_at_largest_l"]) + toM
            lb = lbA + dlo * (131 - f["n_of_min_at_largest_l"])
            req = (bM - lbA) / (l0 - f["largest_l"])
            ev[eng].update(boundA_log2_Fq_mults=round(lbA, 2), boundA_gap_bits=round(lbA - bM, 2),
                           boundA_assumptions=f"cost non-decreasing in l (from l={f['largest_l']}) and in n (from n={f['n_of_min_at_largest_l']})",
                           boundB_log2_Fq_mults=round(lb, 2), boundB_gap_bits=round(lb - bM, 2),
                           boundB_assumptions=f"cost non-decreasing in l from l={f['largest_l']}; n-trend >= d-2se = {dlo:.3f} bits/n up to n=131",
                           required_slope_bits_per_l_to_meet_budget=round(req, 3))
            # whole-attack totals for this engine (fit and bound), in rho iterations
            calls = b["log2_calls"]; la_it = b["log2_LA_it"]
            ev[eng]["attack_total_fit_it"] = round(lg_add(calls + s131 + toM - LOG2_MIT, la_it), 2)
            ev[eng]["attack_margin_fit_bits"] = round(ev[eng]["attack_total_fit_it"] - RHO, 2)
            ev[eng]["attack_total_boundB_it"] = round(lg_add(calls + lb - LOG2_MIT, la_it), 2)
            ev[eng]["attack_margin_boundB_bits"] = round(ev[eng]["attack_total_boundB_it"] - RHO, 2)
        # fit-free lower bounds from the largest-l cells of every engine (solved runs or timeouts), incl.
        # engines with a single l value (no fit possible), e.g. this audit's msolve m = 4 runs
        toM = -math.log2(T_M_CONS)
        ff = {}
        for eng in sorted({r["engine"] for r in rows if r["m"] == m and r["engine"] != "mitm"}):
            er = [r for r in rows if r["engine"] == eng and r["m"] == m]
            lmax = max(r["l"] for r in er)
            top = [r for r in er if r["l"] == lmax]
            vals = [(r["s"] if r["s"] is not None else r["timeout"], r["n"], r["s"] is None) for r in top]
            # a cell's lower bound: solved time, or the timeout if it did not finish
            lo = min(vals)
            lbA = math.log2(lo[0]) + toM
            ff[eng] = dict(largest_l=lmax, runs_at_largest_l=len(top), timeouts_at_largest_l=sum(v[2] for v in vals),
                           min_seconds_or_timeout=lo[0], n_of_min=lo[1], min_is_timeout_lower_bound=lo[2],
                           boundA_log2_Fq_mults=round(lbA, 2), boundA_gap_bits=round(lbA - bM, 2),
                           required_slope_bits_per_l=round((bM - lbA) / (l0 - lmax), 3))
        entry["fit_free_largest_l"] = ff
        hm = hvals.get(m)
        if var.startswith("ordered") and hm and hm["all_cells"]:
            entry["budget_with_measured_msolve_H2_over_H1"] = round(bM - hm["all_cells"][1], 3)
        # exact MITM (group ops, 1 op = 1 iteration)
        k = math.ceil(m / 2)
        mitm_it = lg_add(k * l0 - lf(k), (m - k) * l0 - lf(m - k))
        entry["mitm_exact"] = dict(log2_group_ops=round(mitm_it, 2), log2_Fq_mults=round(mitm_it + LOG2_MIT, 2),
                                   gap_bits=round(mitm_it + LOG2_MIT - bM, 2))
        # WDSat-type enumeration exponent (UNSAT search visits ~2^(ml)/m! leaves; measured c = 3.01 at m = 3)
        entry["enumeration_2^(ml)/m!_conflicts"] = dict(log2=round(m * l0 - lf(m), 2),
                                                        gap_bits_if_1_conflict_eq_1_Fq_mult=round(m * l0 - lf(m) - bM, 2))
        entry["engines"] = ev
        cmp[f"m{m}|{var}"] = entry
out["measured_vs_budget"] = cmp

# ------------------------------------------------------------------------------------------
# 7. (d) RT6 Petit-Quisquater and RT7 Semaev 2015
# ------------------------------------------------------------------------------------------
def lsum(nv, D):
    return math.log2(sum(math.comb(nv, i) for i in range(0, min(D, nv) + 1)))


def pq(omega, corrected, ordered=False, mr=range(2, 12), lr=range(1, 80)):
    best = None
    for m in mr:
        D = m * m + 1
        for l in lr:
            if ordered and m * l > 131:
                continue
            nv = m * l
            if corrected:
                logp = min(0.0, m * l - (0.0 if ordered else lf(m)) - LOG2E + 1.0)
                rel = math.log2(2 ** (l - 1) + 1)
                calls = rel - logp
                pdp = omega * lsum(nv, D)
                la = math.log2(m) + 2 * (l - 1) - LOG2_MIT
                tot = lg_add(calls + pdp, la)
            else:
                logp = min(0.0, m * l - math.log2(math.factorial(m)) - 131)
                rel = l
                calls = rel - logp
                pdp = omega * lsum(nv, D)
                la = math.log2(m) + 2 * rel
                tot = max(calls + pdp, la) + 1
            if best is None or tot < best[0]:
                best = (tot, m, l, calls, pdp, la, D)
    return dict(log2_total=round(best[0], 3), m=best[1], l=best[2], log2_calls=round(best[3], 3),
                log2_pdp=round(best[4], 3), log2_LA=round(best[5], 3), D=best[6], margin_bits=round(best[0] - RHO, 3))


rt6 = {}
for omega in (2.0, 2.37):
    rt6[f"verbatim_omega{omega}"] = pq(omega, False)
    rt6[f"corrected_omega{omega}"] = pq(omega, True, lr=range(1, 132))
    rt6[f"corrected_ordered_omega{omega}"] = pq(omega, True, ordered=True, lr=range(1, 132))
rt6["stored_redteam"] = json.load(open(RT + "raw/bounds.json"))["F_petit_quisquater_optimistic"]
out["RT6_petit_quisquater"] = rt6


def semaev(D, omega, corrected, ordered=False, uncapped=False):
    best = None
    n = 131
    for m in range(2, 12):
        for l in range(1, 70):
            if ordered and m * l > 131:
                continue
            V = m * l + max(0, m - 2) * n
            pdp = omega * lsum(V, D)
            if corrected:
                lam = m * l - (0.0 if ordered else lf(m)) - LOG2E + 1.0
                logp = lam if uncapped else min(0.0, lam)
                rel = math.log2(2 ** (l - 1) + 1)
                calls = max(0.0, rel - logp)
                la = math.log2(m) + 2 * (l - 1) - LOG2_MIT
                tot = lg_add(calls + pdp, la)
            else:
                logp = min(0.0, m * l - math.log2(math.factorial(m)) - n)
                calls = l - logp
                la = math.log2(m) + 2 * l
                tot = max(calls + pdp, la) + 1
            if best is None or tot < best[0]:
                best = (tot, m, l, V, calls, pdp)
    return dict(log2_total=round(best[0], 3), m=best[1], l=best[2], vars=best[3], log2_calls=round(best[4], 3),
                log2_per_pdp=round(best[5], 3), margin_bits=round(best[0] - RHO, 3))


rt7 = {}
# D = 3 is the Boolean degree of the descended S_3 equations themselves (a floor for any D, not a claim);
# D = 4 is Semaev's heuristic; D = 5, 6 are redteam-1's sensitivity values.
for D in (3, 4, 5, 6):
    for omega in (2.0, 2.37, 2.81):
        rt7[f"verbatim_D{D}_omega{omega}"] = semaev(D, omega, False)
        rt7[f"corrected_D{D}_omega{omega}"] = semaev(D, omega, True)
        rt7[f"corrected_ordered_uncapped_D{D}_omega{omega}"] = semaev(D, omega, True, ordered=True, uncapped=True)
rt7["stored_redteam"] = json.load(open(RT + "raw/semaev2015_bound.json"))
out["RT7_semaev2015"] = rt7

json.dump(out, open(G + "raw/audit.json", "w"), indent=1, default=str)
print("RT6", json.dumps({k: v for k, v in rt6.items() if k != "stored_redteam"}, indent=0))
print("RT7 D4", {k: v for k, v in rt7.items() if "D4" in k})
print("written raw/audit.json")
