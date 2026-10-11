"""
Aggregate transport-263 shards -> per_curve.json + summary.json, with extra global checks:
  * all 262 floor labels present, every per-curve flag true
  * Frobenius relation: kernel x-set of frobenius_next(X) = { x^2 : x in kernel x-set of X }  (all 262 edges,
    including the wrap X130 -> X000), and v(next) = v(X)^2
  * transported conjugate kernel really transports: for each X, rebuild phi for next(X) from the SQUARED
    kernel of X and re-run the planted-scalar check on next(X) (independent random R, k)
  * the dual (descending) E0-kernels found per curve are 262 distinct, non-horizontal subgroups of E0'[263]
  * effective hardness per curve
Run: sage -python aggregate.py
"""
import sys, os, json, glob, time, math, random, statistics, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
sys.path.insert(0, HERE)
import ecc2k
import transport as T
from sage.all import EllipticCurve, set_random_seed

N = ecc2k.N
K = ecc2k.field()
E0 = EllipticCurve(K, [1, 0, 0, 0, 1])
E0.set_order(ecc2k.CARD)

recs, kers = {}, {}
for fn in sorted(glob.glob(os.path.join(HERE, "raw", "shard_*.json"))):
    if fn.endswith(".part"):
        continue
    recs.update(json.load(open(fn)))
for fn in sorted(glob.glob(os.path.join(HERE, "raw", "kernels_*.json"))):
    kers.update(json.load(open(fn)))
floor = [lab for lab in ecc2k.LABELS if lab != "E0"]
json.dump({lab: kers[lab] for lab in floor if lab in kers}, open(os.path.join(HERE, "kernels_all.json"), "w"))
missing = [lab for lab in floor if lab not in recs or lab not in kers]
print("records:", len(recs), "kernels:", len(kers), "missing:", missing)
assert not missing

cal = json.load(open(os.path.join(HERE, "raw", "calibration.json")))
RHO = cal["rho_E0_neg_tau_log2"]
RHO_FLOOR_DIRECT = cal["rho_floor_neg_only_log2"]

G = {}  # global checks


# ------------------------------------------------------------------ Frobenius relation of kernels
def xs_of(lab):
    return [K.from_integer(int(h, 16)) for h in kers[lab]]


frob_ok, v_ok, frob_time = {}, {}, []
for lab in floor:
    nxt = ecc2k.frobenius_next(lab)
    xs = xs_of(lab)
    c = time.process_time()
    sq = [u * u for u in xs]
    frob_time.append(time.process_time() - c)
    frob_ok[lab] = set(sq) == set(xs_of(nxt))
    v = K.from_integer(int(recs[lab]["v_int"]))
    v_ok[lab] = K.from_integer(int(recs[nxt]["v_int"])) == v * v
    # sha fields consistent too
    frob_ok[lab] &= recs[lab]["kernel_sq_xs_sha256"] == recs[nxt]["kernel_xs_sha256"]
G["frobenius_kernel_relation_all_262_edges"] = all(frob_ok.values())
G["frobenius_v_relation_all_262_edges"] = all(v_ok.values())
G["frobenius_conjugate_kernel_seconds_median"] = statistics.median(frob_time)

# ------------------------------------------------------------------ conjugate-built transport: planted check
conj_ok = {}
cc = []
for lab in floor:
    nxt = ecc2k.frobenius_next(lab)
    xs = [u * u for u in xs_of(lab)]            # kernel for nxt, obtained ONLY by conjugating lab's kernel
    sqs = [u * u for u in xs]
    v = sum(xs)
    b = K.from_integer(int(ecc2k.RECORDS[nxt]["b_int"]))
    E = EllipticCurve(K, [1, 0, 0, 0, b])
    set_random_seed(int(hashlib.sha256(("conj:" + nxt).encode()).hexdigest()[:15], 16))
    rng = random.Random("conj:" + nxt)
    R = 4 * E.random_point()
    k = rng.randrange(2, N - 1)
    S = k * R
    c = time.process_time()
    pR = E0(*T.velu_eval(xs, sqs, v, R[0], R[1], T.Ops()))
    pS = E0(*T.velu_eval(xs, sqs, v, S[0], S[1], T.Ops()))
    cc.append((time.process_time() - c) / 2)
    conj_ok[nxt] = bool(b + v + v * v == 1 and not R.is_zero() and (N * R).is_zero() and not pR.is_zero()
                        and (N * pR).is_zero() and pS == k * pR)
G["conjugate_built_transport_planted_ok_all_262"] = all(conj_ok.values())

# ------------------------------------------------------------------ dual kernels distinct
desc = T.precompute_E0_kernels(K)
idx_seen = {}
dual_consistent = True
for lab in floor:
    b = int(ecc2k.RECORDS[lab]["b_int"])
    m = desc.get(b, [])
    dual_consistent &= len(m) == 1 and str(m[0][0]) == recs[lab].get("dual_kernel_index")
    idx_seen[lab] = str(m[0][0]) if m else None
horiz = [str(e[0]) for e in desc[1]]
G["dual_kernel_index_recomputed_matches_shards"] = bool(dual_consistent)
G["dual_kernels_262_distinct"] = len(set(idx_seen.values())) == 262
G["dual_kernels_avoid_the_2_horizontal"] = not (set(idx_seen.values()) & set(horiz))
G["E0_horizontal_kernel_indices"] = horiz
G["dual_sign_counts"] = {s: sum(1 for lab in floor if recs[lab]["dual_psi_phi_R_eq"] == s)
                         for s in ["+263R", "-263R", "FAIL"]}

# ------------------------------------------------------------------ costs and effective hardness
IM, IS = cal["IT_inversion_M"], cal["IT_inversion_S"]


def m_equiv_upper(ops):
    """upper bound in F_q multiplications: S counted as 1 M, I as Itoh-Tsujii 8 M + 130 S"""
    return ops["M"] + ops["S"] + ops["I"] * (IM + IS)


def log2_add(a_log2, c):
    """log2(2^a + c)"""
    return a_log2 + math.log1p(c / 2.0 ** a_log2) / math.log(2.0)


PARI = {}
for fn in sorted(glob.glob(os.path.join(HERE, "raw", "pari_check_*of*.json"))):
    PARI.update(json.load(open(fn)))

per = {}
per["E0"] = {"transport_ok": True, "transport": "identity (E0 is the crater curve itself)",
             "codomain_j_is_1": True, "planted_check_ok": None, "build_seconds": 0.0, "eval_seconds": 0.0,
             "rho_direct_log2": RHO, "effective_log2": RHO}
rows = []
for lab in floor:
    r = recs[lab]
    ops_build, ops_eval = r["build_ops"], r["eval_ops_per_point"]
    # transport of one DLP instance = build once + evaluate 2 points (base point and target)
    M_up = m_equiv_upper(ops_build) + 2 * m_equiv_upper(ops_eval)
    sec_expl = r["build_seconds"] + 2 * r["eval_seconds"]
    sec_sage = r["sage_build_seconds"] + 2 * r["sage_eval_seconds"]
    adds_expl = sec_expl / cal["E0_affine_add_python_s"]           # in E0 affine-add equivalents, same env
    adds_sage = sec_sage / cal["E0_affine_add_python_s"]
    worst = max(adds_expl, adds_sage, M_up)                        # most pessimistic "iterations" figure
    rec = {
        "transport_ok": bool(r["transport_ok"] and frob_ok[lab] and v_ok[lab] and conj_ok[lab]),
        "codomain_j_is_1": bool(r["codomain_j_is_1"] and r["sage_codomain_j_is_1"]),
        "planted_check_ok": bool(r["planted_check_ok"]),
        "build_seconds": r["build_seconds"],
        "eval_seconds": r["eval_seconds"],
        "sage_build_seconds": r["sage_build_seconds"],
        "sage_eval_seconds": r["sage_eval_seconds"],
        "build_wall_seconds": r["build_wall_seconds"],
        "sage_build_wall_seconds": r["sage_build_wall_seconds"],
        "fq2_kernel_seconds": r["fq2_seconds"],
        "build_ops": ops_build,
        "eval_ops_per_point": ops_eval,
        "transport_cost_M_equiv_upper": M_up,
        "transport_cost_log2_M_equiv_upper": math.log2(M_up),
        "transport_cost_E0add_equiv_explicit": adds_expl,
        "transport_cost_E0add_equiv_sage": adds_sage,
        "kernel_ok": r["kernel_ok"],
        "kernel_galois_stable_Fq2": r["fq2_kernel_galois_stable_frob_eq_minus"],
        "twist_263_sylow_cyclic": r["twist_263_sylow_cyclic"],
        "sage_agrees_explicit": r["sage_agrees_explicit"],
        "hom_full_group_ok": r["hom_full_group_ok"],
        "toy_dlp_recovered_on_E0": r["toy_dlp_recovered_on_E0"],
        "dual_ok": r["dual_ok"],
        "dual_psi_phi_R_eq": r["dual_psi_phi_R_eq"],
        "frobenius_conjugate_kernel_ok": bool(frob_ok[lab] and v_ok[lab]),
        "frobenius_conjugate_transport_planted_ok": conj_ok[lab],
        "planted_k": r["planted_k"],
        "pari_ellisogeny_ok": PARI.get(lab, {}).get("pari_ok"),
        "pari_build_seconds": PARI.get(lab, {}).get("pari_build_seconds"),
        "rho_direct_log2": RHO_FLOOR_DIRECT,
        "effective_log2": log2_add(RHO, worst),
        "effective_minus_E0_log2": log2_add(RHO, worst) - RHO,
    }
    per[lab] = rec
    rows.append(rec)

json.dump(per, open(os.path.join(HERE, "per_curve.json"), "w"), indent=1)


def stat(key):
    vals = [r[key] for r in rows]
    return {"min": min(vals), "median": statistics.median(vals), "max": max(vals)}


summary = {
    "n_floor_curves": len(floor),
    "n_transport_ok": sum(r["transport_ok"] for r in rows),
    "n_codomain_j_is_1": sum(r["codomain_j_is_1"] for r in rows),
    "n_planted_check_ok": sum(r["planted_check_ok"] for r in rows),
    "n_sage_agrees_explicit": sum(r["sage_agrees_explicit"] for r in rows),
    "n_dual_ok": sum(r["dual_ok"] for r in rows),
    "n_toy_dlp_ok": sum(r["toy_dlp_recovered_on_E0"] for r in rows),
    "n_kernel_ok": sum(r["kernel_ok"] for r in rows),
    "n_pari_ellisogeny_ok": sum(bool(r["pari_ellisogeny_ok"]) for r in rows),
    "n_frobenius_conjugate_transport_planted_ok": sum(r["frobenius_conjugate_transport_planted_ok"] for r in rows),
    "global_checks": G,
    "build_seconds": stat("build_seconds"),
    "eval_seconds": stat("eval_seconds"),
    "sage_build_seconds": stat("sage_build_seconds"),
    "sage_eval_seconds": stat("sage_eval_seconds"),
    "fq2_kernel_seconds": stat("fq2_kernel_seconds"),
    "transport_cost_M_equiv_upper": stat("transport_cost_M_equiv_upper"),
    "transport_cost_log2_M_equiv_upper": stat("transport_cost_log2_M_equiv_upper"),
    "transport_cost_E0add_equiv_explicit": stat("transport_cost_E0add_equiv_explicit"),
    "transport_cost_E0add_equiv_sage": stat("transport_cost_E0add_equiv_sage"),
    "effective_log2": stat("effective_log2"),
    "effective_minus_E0_log2": stat("effective_minus_E0_log2"),
    "eval_ops_per_point_distinct": sorted({json.dumps(r["eval_ops_per_point"], sort_keys=True) for r in rows}),
    "rho_E0_log2": RHO,
    "rho_floor_direct_log2": RHO_FLOOR_DIRECT,
    "calibration": cal,
}
json.dump(summary, open(os.path.join(HERE, "summary.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in summary.items() if k != "calibration"}, indent=1))
