"""G6 steps (1) and (2): label sets and value cross-checks of every per-curve sweep.

Run:  export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; timeout 2400 python3 crosscheck.py
Needs nt_checks.json (sage -python nt_checks.py) in the same directory.

Reads (read-only):
  ground_truth/ground_truth.json, ground_truth/class_polynomial_D-484183.hex
  <sweep>/per_curve.json for the 11 sweeps (toy-analogue-b excluded: toy labels)
  sweep side files that store per-curve values: transport-263/kernels_all.json,
  weil-descent-ghs/raw_magic_numbers.json, index-calculus/raw_counts.json,
  ground_truth_check/my_floor_j.json, p-levels/levels.json, literature/levels.json
  verify/**.json outputs that store per-curve values (listed in VERIFY_SOURCES below)
Writes: crosscheck_report.json (checks, disagreements, recomputed values, verify coverage)
"""
import json, os, sys, math, hashlib, time, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gf2_131 as F

T0 = time.time()
W = "/Volumes/SSD990/ecdlp-hardness-work"
SWEEPS = ["group-order", "endomorphism-ring", "pairing-transfer", "weil-descent-ghs",
          "rho-endomorphisms", "transport-263", "index-calculus", "codex-crosscheck",
          "p-levels", "literature", "toy-analogue-a"]

def P(*a):
    return os.path.join(W, *a)

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def load(path):
    with open(path) as fh:
        return json.load(fh)

INPUTS = {}
def jload(rel):
    INPUTS[rel] = sha256(P(rel))
    return load(P(rel))

F.selftest()
gt = jload("ground_truth/ground_truth.json")
nt = load(os.path.join(HERE, "nt_checks.json"))
INPUTS["gaps/G6-consolidate-and-cross-check-per-curve/nt_checks.json"] = sha256(os.path.join(HERE, "nt_checks.json"))
meta = gt["meta"]
REC = {c["label"]: c for c in gt["curves"]}
LABELS = [c["label"] for c in gt["curves"]]
LABELSET = set(LABELS)
FLOOR = [l for l in LABELS if l != "E0"]
sw = {s: jload(s + "/per_curve.json") for s in SWEEPS}

N = int(nt["N"]); t = int(nt["t"]); q = 2 ** 131
CARD = int(nt["card"]); TW = int(nt["twist_card"]); P114 = int(nt["P114"]); p = int(nt["p"])
RHO_E0 = nt["rho_log2"]["E0_neg_tau_class_262"]
RHO_NEG = nt["rho_log2"]["neg_only_class_2"]
RHO_TW_TAU = nt["rho_log2"]["twist_P114_neg_tau_class_262"]
RHO_TW_NEG = nt["rho_log2"]["twist_P114_neg_only_class_2"]
GAP = nt["rho_log2"]["gap_bits_half_log2_131"]

# ------------------------------------------------------------------ bookkeeping
checks = {}
disagreements = []

def cmp(cid, desc, src, key, label, value, ref, ref_src, eq=None):
    c = checks.setdefault(cid, {"description": desc, "n_compared": 0, "n_agree": 0,
                                "sources": [], "reference": ref_src})
    c["n_compared"] += 1
    if src not in c["sources"]:
        c["sources"].append(src)
    try:
        ok = (value == ref) if eq is None else bool(eq(value, ref))
    except Exception as e:  # malformed value
        ok = False
    if ok:
        c["n_agree"] += 1
    else:
        disagreements.append({"check": cid, "file": src, "key": key, "label": label,
                              "value": value, "reference_value": ref, "reference_source": ref_src})
    return ok

def ndec(x):
    s = repr(float(x))
    if "e" in s or "E" in s:
        return 15
    return len(s.split(".")[1]) if "." in s else 0

def feq(stored, exact):
    """equal to the precision the value was stored with (half an ulp of its last decimal), >= 1e-9"""
    d = ndec(stored)
    tol = max(0.5 * 10 ** (-d), 1e-9) + 1e-12
    return abs(float(stored) - float(exact)) <= tol

def get(d, path):
    cur = d
    for k in path.split("/"):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return KeyError
    return cur

# ------------------------------------------------------------------ step 1: label sets
step1 = {}
for s in SWEEPS:
    ks = set(sw[s].keys())
    step1[s] = {"file": s + "/per_curve.json", "n_labels": len(ks), "equals_ground_truth_263": ks == LABELSET,
                "missing": sorted(LABELSET - ks), "extra": sorted(ks - LABELSET)}
step1["_excluded"] = {"toy-analogue-b/per_curve.json": "excluded by task (toy labels); toy-a and toy-b are symlinks/duplicates of toy-analogue-a and toy-analogue-b"}

# ------------------------------------------------------------------ recompute per-curve field data
level = {l: REC[l]["level"] for l in LABELS}
orbit = {l: REC[l]["orbit"] for l in LABELS}
b_of = {l: int(REC[l]["b_int"]) for l in LABELS}
j_of = {l: int(REC[l]["j_int"]) for l in LABELS}
recomputed = {}
for l in LABELS:
    b, j = b_of[l], j_of[l]
    rc = {}
    rc["j_times_b_is_1"] = F.mul(j, b) == 1
    rc["j_in_F2"] = F.sq(j) == j
    rc["j_degree_over_F2"] = 1 if rc["j_in_F2"] else (131 if F.frob(j, 131) == j else None)
    rc["Tr_b"] = F.trace(b)
    rc["Tr_sqrt_b"] = F.trace(F.sqrt(b))
    rc["conj_rank_b"] = F.conj_rank(b)          # = deg Ord_b = dim span conj(sqrt b)
    rc["conj_rank_sqrt_b"] = F.conj_rank(F.sqrt(b))
    rc["mq_magic_number"] = F.mq_magic_number(b)
    rc["ghs_genus_2^(m-1)"] = str(2 ** (rc["mq_magic_number"] - 1))
    recomputed[l] = rc

# class polynomial H_D mod 2 evaluated at every j (parity of the hex coefficients)
hd_lines = [ln.strip() for ln in open(P("ground_truth/class_polynomial_D-484183.hex")) if ln.strip()]
INPUTS["ground_truth/class_polynomial_D-484183.hex"] = sha256(P("ground_truth/class_polynomial_D-484183.hex"))
hd_bits = [int(s.lstrip("-"), 16) & 1 for s in hd_lines]     # low degree first
for l in LABELS:
    acc = 0
    for bit in reversed(hd_bits):
        acc = F.mul(acc, j_of[l]) ^ bit
    recomputed[l]["HD_mod2_at_j_is_zero"] = acc == 0
    recomputed[l]["H_-7_mod2_at_j_is_zero"] = (j_of[l] ^ 1) == 0     # H_-7 = X + 3375 = X + 1 mod 2
checks_meta_hd = {"HD_degree": len(hd_lines) - 1, "HD_mod2_nonzero_terms": sum(hd_bits)}

# ---- (B) field identities and labels ----------------------------------------------------
for l in LABELS:
    cmp("B1_j_times_b", "j*b == 1 in F_q (pure-python GF(2^131))", "ground_truth/ground_truth.json",
        "curves[].j_int,b_int", l, recomputed[l]["j_times_b_is_1"], True, "G6 gf2_131.py")
    cmp("B2_j_in_F2_iff_E0", "j in F_2 exactly for E0 (floor j has degree 131)", "ground_truth/ground_truth.json",
        "curves[].j_int", l, recomputed[l]["j_in_F2"], l == "E0", "label")
    cmp("B2b_HD_root", "H_{-7*263^2}(j) = 0 mod 2 exactly for floor curves (H_D from class_polynomial hex, mod 2)",
        "ground_truth/class_polynomial_D-484183.hex", "coefficients mod 2", l,
        recomputed[l]["HD_mod2_at_j_is_zero"], l != "E0", "label")
    cmp("B0_a2", "a2 = 0 (the order-4N twist)", "ground_truth/ground_truth.json", "curves[].a2", l, REC[l]["a2"], 0, "task statement")
for X in ("A", "B"):
    for k in range(131):
        cur, nxt = "%s%03d" % (X, k), "%s%03d" % (X, (k + 1) % 131)
        cmp("B3_frobenius_labels", "j(X_{k+1 mod 131}) = j(X_k)^2", "ground_truth/ground_truth.json",
            "curves[].j_int", nxt, j_of[nxt], F.sq(j_of[cur]), "square of j(%s)" % cur)
    base = "%s000" % X
    others = [j_of["%s%03d" % (X, k)] for k in range(131)]
    cmp("B3b_X000_is_min", "X000 has the smallest integer j of its orbit (Codex label rule)", "ground_truth/ground_truth.json",
        "curves[].j_int", base, j_of[base], min(others), "min over orbit")

# other stores of b / j
rm = jload("weil-descent-ghs/raw_magic_numbers.json")
for l in LABELS:
    cmp("B4_b_raw_magic", "b_int stored by weil-descent-ghs raw_magic_numbers.json == ground truth",
        "weil-descent-ghs/raw_magic_numbers.json", "curves.%s.b_int" % l, l, rm["curves"][l]["b_int"], REC[l]["b_int"], "ground_truth.json b_int")
mfj = jload("ground_truth_check/my_floor_j.json")
for X, orb in (("A", mfj["orbits"][0]), ("B", mfj["orbits"][1])):
    for k in range(131):
        l = "%s%03d" % (X, k)
        cmp("B5_j_derive_floor", "Velu-derived floor j (ground_truth_check/my_floor_j.json orbits[] in Frobenius order) == ground truth",
            "ground_truth_check/my_floor_j.json", "orbits[%d][%d]" % ("AB".index(X), k), l, orb[k], REC[l]["j_int"], "ground_truth.json j_int")
lc = jload("verify/codex-crosscheck/C1-recompute/labels_check.json")
for l in FLOOR:
    cmp("B6_j_codex_C1", "verify/codex-crosscheck/C1-recompute my_labels_j == ground truth",
        "verify/codex-crosscheck/C1-recompute/labels_check.json", "my_labels_j.%s" % l, l, lc["my_labels_j"].get(l), REC[l]["j_int"], "ground_truth.json j_int")

# ---- (A) orbit / frob_index / level consistency ------------------------------------------
def conductor_class(s):
    s = str(s).replace(" ", "")
    if "263p" in s or "263*p" in s:
        return "263p"
    if "263" in s:
        return "263"
    if s in ("1",) or "O_K" in s or "Z[tau]" in s:
        return "1"
    return "?" + s

for l in LABELS:
    for s, key in (("endomorphism-ring", "orbit"), ("pairing-transfer", "orbit"), ("rho-endomorphisms", "orbit"),
                   ("index-calculus", "orbit"), ("p-levels", "orbit"), ("literature", "orbit"), ("toy-analogue-a", "orbit")):
        cmp("A1_orbit", "orbit label vs ground truth", s + "/per_curve.json", key, l, sw[s][l].get(key), orbit[l], "ground_truth.json orbit")
    for s in ("endomorphism-ring", "literature", "rho-endomorphisms"):
        if "frob_index" in sw[s][l]:
            cmp("A2_frob_index", "frob_index vs ground truth", s + "/per_curve.json", "frob_index", l,
                sw[s][l]["frob_index"], REC[l]["frob_index"], "ground_truth.json frob_index")
    cmp("A0_label_field", "stored label field == key", "endomorphism-ring/per_curve.json", "label", l, sw["endomorphism-ring"][l]["label"], l, "dict key")
    for s, key in (("endomorphism-ring", "level"), ("pairing-transfer", "level"), ("rho-endomorphisms", "level"),
                   ("toy-analogue-a", "level"), ("literature", "level_conductor")):
        cmp("A3_level", "volcano level / conductor (1 = crater, 263 = floor) vs ground truth", s + "/per_curve.json", key, l,
            sw[s][l][key], level[l], "ground_truth.json level")
    cmp("E1_conductor", "conductor vs ground truth level", "endomorphism-ring/per_curve.json", "conductor", l,
        conductor_class(sw["endomorphism-ring"][l]["conductor"]), str(level[l]), "ground_truth.json level")
    cmp("E1_conductor", "conductor vs ground truth level", "p-levels/per_curve.json", "conductor", l,
        conductor_class(sw["p-levels"][l]["conductor"]), str(level[l]), "ground_truth.json level")
    for s, key in (("endomorphism-ring", "end_ring"), ("rho-endomorphisms", "End"), ("literature", "end_ring")):
        cmp("E2_end_ring", "End ring string -> conductor class (O_K -> 1; O_263 / Z+263 O_K / Z[(1+263 sqrt-7)/2] -> 263)",
            s + "/per_curve.json", key, l, conductor_class(sw[s][l][key]), str(level[l]), "ground_truth.json level")

# ---- (E) endomorphism-ring internals vs recomputation --------------------------------------
er = sw["endomorphism-ring"]
for l in LABELS:
    rc = recomputed[l]
    cmp("E3_j_degree", "j degree over F_2", "endomorphism-ring/per_curve.json", "j_degree_over_F2", l, er[l]["j_degree_over_F2"], rc["j_degree_over_F2"], "G6 recompute (gf2_131)")
    cmp("E3_j_in_F2", "j in F_2", "endomorphism-ring/per_curve.json", "j_in_F2", l, er[l]["j_in_F2"], rc["j_in_F2"], "G6 recompute (gf2_131)")
    cmp("E3_j_in_F2", "j in F_2", "p-levels/per_curve.json", "j_in_F2 (computed)", l, sw["p-levels"][l]["j_in_F2 (computed)"], rc["j_in_F2"], "G6 recompute (gf2_131)")
    cmp("E3_frob_orbit_size", "Frobenius orbit size of j", "endomorphism-ring/per_curve.json", "frobenius_orbit_size", l, er[l]["frobenius_orbit_size"], rc["j_degree_over_F2"], "G6 recompute (gf2_131)")
    cmp("E4_HD_root", "H_D(j) = 0 mod 2", "endomorphism-ring/per_curve.json", "HD_mod2_at_j_is_zero", l, er[l]["HD_mod2_at_j_is_zero"], rc["HD_mod2_at_j_is_zero"], "G6 recompute (H_D hex mod 2, Horner in gf2_131)")
    cmp("E4_H7_root", "H_-7(j) = 0 mod 2 (j == 1)", "endomorphism-ring/per_curve.json", "H_minus7_mod2_at_j_is_zero(j==1)", l, er[l]["H_minus7_mod2_at_j_is_zero(j==1)"], rc["H_-7_mod2_at_j_is_zero"], "G6 recompute")
    cmp("E5_tau_available", "tau (x->x^2) is an endomorphism iff j in F_2", "p-levels/per_curve.json", "tau_endomorphism_available", l, sw["p-levels"][l]["tau_endomorphism_available"], rc["j_in_F2"], "G6 recompute (j in F_2)")
    exp_rat = 264 if l == "E0" else 1
    cmp("E6_phi263_rational", "number of F_q-rational 263-isogenies (264 on crater, 1 ascending on floor)", "endomorphism-ring/per_curve.json",
        "phi263_Fq_rational_263_isogenies", l, er[l]["phi263_Fq_rational_263_isogenies"], exp_rat, "volcano structure (kronecker(-7,263)=+1, h=262)")
    prod = 1
    for v in er[l]["ellgroup_Fq2_pari"]:
        prod *= int(v)
    cmp("C6_card_Fq2", "#E(F_{q^2}) (PARI ellgroup product) == (q+1-t)(q+1+t)", "endomorphism-ring/per_curve.json", "ellgroup_Fq2_pari", l, prod, CARD * TW, "nt_checks card*twist")

# Phi_263 root data: endomorphism-ring vs verify/codex-crosscheck/C3-recompute (separate PARI/Sage run)
phr = {}
for i in range(6):
    rel = "verify/codex-crosscheck/C3-recompute/phi263_roots_%d.jsonl" % i
    INPUTS[rel] = sha256(P(rel))
    for line in open(P(rel)):
        d = json.loads(line)
        phr[d["label"]] = d
for l in LABELS:
    d = phr[l]
    cmp("E6b_phi263_roots", "Phi_263(j,Y) mod 2: #distinct F_q roots and multiplicity of Y=1 (crater (263,2), floor (1,1))",
        "endomorphism-ring/per_curve.json", "phi263_distinct_Fq_roots,phi263_mult_root_j=1", l,
        [er[l]["phi263_distinct_Fq_roots"], er[l]["phi263_mult_root_j=1"]], [d["n_distinct_Fq_roots"], d["mult_root_1"]],
        "verify/codex-crosscheck/C3-recompute/phi263_roots_*.jsonl")
    cmp("E6b_phi263_roots", "Phi_263 root pattern matches the volcano level", "verify/codex-crosscheck/C3-recompute/phi263_roots_*.jsonl",
        "n_distinct_Fq_roots,mult_root_1", l, [d["n_distinct_Fq_roots"], d["mult_root_1"]], [263, 2] if l == "E0" else [1, 1], "ground_truth.json level")

# ---- (C) group orders, trace, structure ------------------------------------------------------
go = sw["group-order"]
E0_TW_EXP = 2 * 263 * P114
for l in LABELS:
    g = go[l]
    cmp("C1_order", "#E(F_q) == 4N", "ground_truth/ground_truth.json", "order_pari", l, int(REC[l]["order_pari"]), CARD, "nt_checks (Lucas t)")
    cmp("C1_order", "#E(F_q) == 4N", "group-order/per_curve.json", "order", l, int(g["order"]), CARD, "nt_checks (Lucas t)")
    cmp("C1_order", "#E(F_q) == 4N", "group-order/per_curve.json", "evidence/pari_ellgroup", l, [int(x) for x in g["evidence"]["pari_ellgroup"]], [CARD], "nt_checks; cyclic")
    cmp("C2_trace", "AGM trace == t", "group-order/per_curve.json", "evidence/agm_trace_prec80", l, int(g["evidence"]["agm_trace_prec80"]), t, "nt_checks t")
    cmp("C2_trace", "AGM trace == t", "group-order/per_curve.json", "evidence/agm_trace_prec96", l, int(g["evidence"]["agm_trace_prec96"]), t, "nt_checks t")
    cmp("C3_twist", "twist order == q+1+t", "ground_truth/ground_truth.json", "twist_order_pari", l, int(REC[l]["twist_order_pari"]), TW, "nt_checks")
    cmp("C3_twist", "twist order == q+1+t", "group-order/per_curve.json", "twist_order", l, int(g["twist_order"]), TW, "nt_checks")
    cmp("C3_twist", "twist order == q+1+t", "pairing-transfer/per_curve.json", "twist_order", l, int(sw["pairing-transfer"][l]["twist_order"]), TW, "nt_checks")
    exp_tw_grp = [E0_TW_EXP, 263] if l == "E0" else [TW]
    cmp("C4_twist_group", "twist group (PARI ellgroup): E0' = Z/(2*263*P114) x Z/263, floor twists cyclic",
        "group-order/per_curve.json", "evidence/pari_twist_ellgroup", l, [int(x) for x in g["evidence"]["pari_twist_ellgroup"]], exp_tw_grp, "nt_checks P114; level")
    cmp("C4_structure", "E(F_q) structure string", "group-order/per_curve.json", "structure", l, g["structure"], "Z/4 x Z/N = Z/4N (cyclic)", "cyclic of order 4N (N prime, 2-part Z/4)")
    cmp("C4_structure", "2-primary part", "group-order/per_curve.json", "two_primary", l, g["two_primary"], "Z/4", "Tr(b)=1, a2=0 -> point of order 4")
    exp_twist_struct = "Z/263 x Z/(2*263*P114)" if l == "E0" else "cyclic Z/(2*263^2*P114)"
    cmp("C4_twist_structure", "twist structure string", "group-order/per_curve.json", "twist_structure", l, g["twist_structure"], exp_twist_struct, "level (crater: (Z/263)^2, floor: cyclic)")
    cmp("C4_twist_factorization", "twist factorization string names P114", "group-order/per_curve.json", "twist_factorization", l,
        str(P114) in g["twist_factorization"] and "263^2" in g["twist_factorization"], True, "nt_checks P114")
    ph = g["pohlig_hellman"]
    cmp("C5_PH", "largest prime subgroup bits == log2 N (2 dp)", "group-order/per_curve.json", "pohlig_hellman/largest_prime_subgroup_bits", l, ph["largest_prime_subgroup_bits"], nt["N_log2"], "nt_checks", eq=feq)
    cmp("C5_PH", "PH cofactor == 4", "group-order/per_curve.json", "pohlig_hellman/cofactor", l, ph["cofactor"], 4, "#E = 4N")
    cmp("C5_PH", "PH saving 0 bits", "group-order/per_curve.json", "pohlig_hellman/ph_saving_bits", l, ph["ph_saving_bits"], 0.0, "N prime, cofactor 4")
    cmp("C5_twist_PH", "twist largest prime bits == log2 P114 (2 dp)", "group-order/per_curve.json", "twist_pohlig_hellman/largest_prime_subgroup_bits", l, g["twist_pohlig_hellman"]["largest_prime_subgroup_bits"], nt["P114_log2"], "nt_checks", eq=feq)
    cmp("C3_N", "N stored by pairing-transfer", "pairing-transfer/per_curve.json", "N", l, int(sw["pairing-transfer"][l]["N"]), N, "nt_checks")

# ---- 263-structure over F_{q^2} (== twist 263-part) across sweeps --------------------------
def s263(s):
    s = str(s).replace(" ", "")
    if "(Z/263)^2" in s or "Z/263xZ/263" in s:
        return "(Z/263)^2"
    if "263^2" in s:
        return "Z/263^2"
    return "?" + s
for l in LABELS:
    exp = "(Z/263)^2" if l == "E0" else "Z/263^2"
    for s, key in (("group-order", "evidence/twist_sylow263"), ("endomorphism-ring", "sylow263_pari"),
                   ("endomorphism-ring", "sylow263_structure_q2"), ("pairing-transfer", "pairing_263/structure_E(L)[263^inf]")):
        cmp("E7_sylow263", "263-Sylow of E(F_{q^2}) (= of the twist): crater (Z/263)^2, floor cyclic Z/263^2",
            s + "/per_curve.json", key, l, s263(get(sw[s][l], key)), exp, "level")

# ---- (D) embedding degree and pairings --------------------------------------------------------
pt = sw["pairing-transfer"]
def norm_fac(s):
    return str(s).replace(" ", "")
for l in LABELS:
    r = pt[l]
    cmp("D1_embedding_degree", "embedding degree ord_N(q)", "pairing-transfer/per_curve.json", "embedding_degree_N", l, r["embedding_degree_N"], nt["embedding_degree_ord_N_q"], "nt_checks (Sage multiplicative_order)")
    cmp("D1_embedding_degree", "embedding degree bits", "pairing-transfer/per_curve.json", "embedding_degree_N_bits", l, r["embedding_degree_N_bits"], nt["embedding_degree_bits"], "nt_checks")
    cmp("D1_embedding_degree", "embedding degree log2 (4 dp)", "pairing-transfer/per_curve.json", "embedding_degree_N_log2", l, r["embedding_degree_N_log2"], nt["embedding_degree_log2"], "nt_checks", eq=feq)
    cmp("D1_embedding_degree", "ord_N(2)", "pairing-transfer/per_curve.json", "ord_N_2", l, r["ord_N_2"], nt["ord_N_2"], "nt_checks")
    cmp("D1_embedding_degree", "factorization of N-1", "pairing-transfer/per_curve.json", "N_minus_1_factorization", l, norm_fac(r["N_minus_1_factorization"]), norm_fac(nt["N_minus_1_factorization"]), "nt_checks (Sage factor)")
    tpe = r["twist_prime_embedding_degrees"]
    cmp("D2_twist_embedding", "ord_263(q)", "pairing-transfer/per_curve.json", "twist_prime_embedding_degrees/263/ord_r_q", l, tpe["263"]["ord_r_q"], nt["ord_263_q"], "nt_checks")
    cmp("D2_twist_embedding", "ord_{263^2}(q)", "pairing-transfer/per_curve.json", "twist_prime_embedding_degrees/263/ord_r^e_q", l, tpe["263"]["ord_r^e_q"], nt["ord_263sq_q"], "nt_checks")
    cmp("D2_twist_embedding", "ord_P114(q)", "pairing-transfer/per_curve.json", "twist_prime_embedding_degrees/P114/ord_r_q", l, tpe[str(P114)]["ord_r_q"], nt["ord_P114_q"], "nt_checks")
    cmp("D3_tate_QN", "reduced Tate pairing t_263(P, Q_N) == 1 (sweep)", "pairing-transfer/per_curve.json", "pairing_263/tate_t263(P,Q_N)", l, r["pairing_263"]["tate_t263(P,Q_N)"], "1", "gcd(N,263)=1 => Q_N in 263E")
cmp("D1_embedding_degree", "embedding degree (literature global)", "literature/levels.json", "global/embedding_degree_ord_N_q", "class", jload("literature/levels.json")["global"]["embedding_degree_ord_N_q"], nt["embedding_degree_ord_N_q"], "nt_checks")

# ---- (GHS) weil-descent-ghs vs recomputation ---------------------------------------------------
wd = sw["weil-descent-ghs"]
def ord_string(rank):
    return "x + 1" if rank == 1 else ("x^131 + 1" if rank == 131 else "rank%d" % rank)
for l in LABELS:
    rc = recomputed[l]; r = wd[l]; rr = rm["curves"][l]
    m = rc["mq_magic_number"]
    cmp("G1_ghs_m", "GHS magic number m (Menezes-Qu rank of (1, sqrt(b)^(2^i)))", "weil-descent-ghs/per_curve.json", "magic_number", l, r["magic_number"], m, "G6 recompute (gf2_131 rank)")
    cmp("G1_ghs_m", "GHS magic number m", "literature/per_curve.json", "ghs_magic_number_m_computed", l, sw["literature"][l]["ghs_magic_number_m_computed"], m, "G6 recompute (gf2_131 rank)")
    for key in ("magic_number_rank_sage", "magic_number_rank_bitmask", "magic_number_menezes_teske_formula"):
        cmp("G1_ghs_m", "GHS magic number m", "weil-descent-ghs/raw_magic_numbers.json", "curves.%s.%s" % (l, key), l, rr[key], m, "G6 recompute (gf2_131 rank)")
    cmp("G2_ord_b", "deg Ord_b = dim span of conjugates of b", "weil-descent-ghs/per_curve.json", "deg_Ord_b", l, r["deg_Ord_b"], rc["conj_rank_b"], "G6 recompute")
    cmp("G2_ord_b", "dim span conjugates sqrt(b)", "weil-descent-ghs/per_curve.json", "dim_span_conjugates_sqrt_b", l, r["dim_span_conjugates_sqrt_b"], rc["conj_rank_sqrt_b"], "G6 recompute")
    cmp("G2_ord_b", "Ord_b polynomial", "weil-descent-ghs/per_curve.json", "Ord_b", l, r["Ord_b"].replace("x^131+1", "x^131 + 1"), ord_string(rc["conj_rank_b"]), "G6 recompute (rank 1 -> x+1, 131 -> x^131+1)")
    cmp("G2_ord_b", "b is a normal element", "weil-descent-ghs/per_curve.json", "b_is_normal_element", l, r["b_is_normal_element"], rc["conj_rank_b"] == 131, "G6 recompute")
    cmp("G3_ghs_genus", "GHS genus 2^(m-1)", "weil-descent-ghs/per_curve.json", "ghs_genus", l, r["ghs_genus"], rc["ghs_genus_2^(m-1)"], "G6 recompute")
    cmp("G3_ghs_genus", "GHS genus log2 = m-1", "weil-descent-ghs/per_curve.json", "ghs_genus_log2", l, r["ghs_genus_log2"], float(m - 1), "G6 recompute", eq=feq)
    cmp("G3_ghs_genus", "GHS genus string", "literature/per_curve.json", "ghs_cover_genus", l, sw["literature"][l]["ghs_cover_genus"], "2^%d or 2^%d-1" % (m - 1, m - 1), "G6 recompute")
    cmp("G4_trace_b", "Tr(b)", "weil-descent-ghs/per_curve.json", "trace_b", l, r["trace_b"], rc["Tr_b"], "G6 recompute (gf2_131 trace)")
    cmp("G4_trace_b", "Tr(b)", "weil-descent-ghs/raw_magic_numbers.json", "curves.%s.trace_b" % l, l, rr["trace_b"], rc["Tr_b"], "G6 recompute")
    cmp("G4_trace_b", "Tr(sqrt b)", "weil-descent-ghs/raw_magic_numbers.json", "curves.%s.trace_sqrt_b" % l, l, rr["trace_sqrt_b"], rc["Tr_sqrt_b"], "G6 recompute")
    cmp("G4_trace_b", "Tr(b)", "index-calculus/per_curve.json", "Tr_b", l, sw["index-calculus"][l]["Tr_b"], rc["Tr_b"], "G6 recompute (gf2_131 trace)")
    cmp("G4_trace_b", "b in F_2", "weil-descent-ghs/raw_magic_numbers.json", "curves.%s.b_in_F2" % l, l, rr["b_in_F2"], rc["j_in_F2"], "G6 recompute")
    cmp("G5_descent_subfields", "only proper subfield of F_{2^131} is F_2 (131 prime)", "weil-descent-ghs/per_curve.json", "descent_subfields", l, r["descent_subfields"], ["F_2"], "131 prime")
    cmp("G6_rho_baseline", "GHS sweep native rho baseline", "weil-descent-ghs/per_curve.json", "rho_baseline_log2_iterations", l, r["rho_baseline_log2_iterations"], RHO_E0 if l == "E0" else RHO_NEG, "nt_checks rho", eq=feq)
    w = r.get("gghs_witness")
    if l == "E0":
        cmp("G7_gghs_witness", "no gGHS witness for E0", "weil-descent-ghs/per_curve.json", "gghs_witness", l, w, None, "b = 1")
    else:
        g1, g2 = int(w["gamma1_int"]), int(w["gamma2_int"])
        cmp("G7_gghs_witness", "gGHS decomposition gamma1*gamma2 == sqrt(b)", "weil-descent-ghs/per_curve.json", "gghs_witness/gamma1_int,gamma2_int", l, F.mul(g1, g2), F.sqrt(b_of[l]), "G6 recompute sqrt(b)")
        cmp("G7_gghs_witness", "deg Ord_gamma1", "weil-descent-ghs/per_curve.json", "gghs_witness/Ord_gamma1_deg", l, w["Ord_gamma1_deg"], F.conj_rank(g1), "G6 recompute rank")
        cmp("G7_gghs_witness", "deg Ord_gamma2", "weil-descent-ghs/per_curve.json", "gghs_witness/Ord_gamma2_deg", l, w["Ord_gamma2_deg"], F.conj_rank(g2), "G6 recompute rank")
        cmp("G7_gghs_witness", "gGHS genus for (Phi131,Phi131) pair = 2^130 - 1", "weil-descent-ghs/per_curve.json", "gghs_witness/genus", l, w["genus"], rm["summary"]["gghs_genus_table_by_Ord_types"]["Phi131,Phi131"], "raw_magic_numbers summary table")

# gGHS minimal pairs listed by raw_magic_numbers: a factor of type x+1 is 1 (F_2^*), so the other
# factor is sqrt(b) itself and must have sqrt(b)'s own type (rank 1 -> x+1, 130 -> Phi131, 131 -> x^131+1)
def ord_type(rank):
    return {1: "x+1", 130: "Phi131", 131: "x^131+1"}.get(rank, "rank%d" % rank)
for l in LABELS:
    t_sqrt = ord_type(recomputed[l]["conj_rank_sqrt_b"])
    for pair in rm["curves"][l].get("gghs_min_pairs", []):
        a_, b_ = pair
        if "x+1" in (a_, b_):
            other = b_ if a_ == "x+1" else a_
            cmp("G8_gghs_pairs_realizable", "listed gGHS min pair containing x+1 is realizable (other factor = sqrt(b), of type %s)" % "Ord(sqrt b)",
                "weil-descent-ghs/raw_magic_numbers.json", "curves.%s.gghs_min_pairs" % l, l, pair,
                sorted([t_sqrt, "x+1"]) if other == t_sqrt else "unrealizable: sqrt(b) has type %s, not %s" % (t_sqrt, other),
                "G6 recompute (rank of conjugates of sqrt(b))", eq=lambda v, r: isinstance(r, list))
        else:
            cmp("G8_gghs_pairs_realizable", "listed gGHS min pair without x+1 has a verified witness (G7)",
                "weil-descent-ghs/raw_magic_numbers.json", "curves.%s.gghs_min_pairs" % l, l, pair,
                pair, "G7 witness check", eq=lambda v, r: l == "E0" or (v == ["Phi131", "Phi131"]))

# ---- (T) transport kernels (transport-263/kernels_all.json) ----------------------------------
ka = jload("transport-263/kernels_all.json")
vmine = {}
kern = {}
for l in FLOOR:
    xs = [int(h, 16) for h in ka[l]]
    kern[l] = xs
    b = b_of[l]
    sx = set(xs)
    cmp("T1_kernel_shape", "131 distinct nonzero kernel x-coordinates", "transport-263/kernels_all.json", l, l, (len(xs), len(sx), 0 in sx), (131, 131, False), "(263-1)/2 = 131")
    v = 0
    for x in xs:
        v ^= x
    vmine[l] = v
    cmp("T2_b_v_v2", "codomain of [1,0,0,v,b+v] is E0: b + v + v^2 == 1 (v = sum of kernel x)", "transport-263/kernels_all.json", l, l, b ^ v ^ F.sq(v), 1, "Velu, char 2")
    nolift = all(F.trace(x ^ F.mul(b, F.inv(F.sq(x)))) == 1 for x in xs)
    cmp("T3_kernel_not_rational", "every kernel x has Tr(x + b/x^2) = 1 (points over F_{q^2} only; pi = -1 on the kernel)", "transport-263/kernels_all.json", l, l, nolift, True, "pi acts as t/2 = -1 mod 263 on the ascending kernel")
    # x-only doubling x -> x^2 + b/x^2 permutes the set in one 131-cycle (2 has order 131 mod 263, -1 not a power of 2)
    img = {F.sq(x) ^ F.mul(b, F.inv(F.sq(x))) for x in xs}
    cyc, x0, n = 0, xs[0], 0
    x = x0
    while True:
        x = F.sq(x) ^ F.mul(b, F.inv(F.sq(x)))
        n += 1
        if x == x0 or n > 200:
            break
    cmp("T4_doubling_cycle", "x-doubling maps the kernel x-set onto itself as a single 131-cycle", "transport-263/kernels_all.json", l, l, (img == sx, n), (True, 131), "[2] on a cyclic group of order 263 (ord_263(2)=131)")
for X in ("A", "B"):
    for k in range(131):
        cur, nxt = "%s%03d" % (X, k), "%s%03d" % (X, (k + 1) % 131)
        cmp("T5_kernel_frobenius", "kernel(X_{k+1}) = {x^2 : x in kernel(X_k)}", "transport-263/kernels_all.json", nxt, nxt,
            set(kern[nxt]) == {F.sq(x) for x in kern[cur]}, True, "Galois equivariance of the unique ascending kernel")

# v in other sources
def vcheck(src, key, l, val, base=None):
    if isinstance(val, str):
        vv = int(val, 16) if (base == 16 or val.startswith("0x")) else int(val)
    else:
        vv = int(val)
    cmp("T6_v_cross_source", "transport kernel v (sum of kernel x) stored by other audits == G6 v from kernels_all.json", src, key, l, vv, vmine[l], "G6 XOR of transport-263/kernels_all.json")
va = jload("verify/toy-analogue-a/C5-audit/audit_c5_all.json")["per_curve"]
vr = jload("verify/toy-analogue-a/C5-recompute/c5_sweep_results.json")["per_curve"]
vb = {r_["id"]: r_ for r_ in jload("verify/toy-analogue-b/C3-audit/real131_transport.json")["records"]}
t1a = jload("verify/transport-263/C1-audit/results_pure.json")
t1r = jload("verify/transport-263/C1-recompute/results_c1.json")["per_curve"]
for l in FLOOR:
    vcheck("verify/toy-analogue-a/C5-audit/audit_c5_all.json", "per_curve.%s.v_hex" % l, l, va[l]["v_hex"], 16)
    vcheck("verify/toy-analogue-a/C5-recompute/c5_sweep_results.json", "per_curve.%s.v_int" % l, l, vr[l]["v_int"])
    vcheck("verify/toy-analogue-b/C3-audit/real131_transport.json", "records[id=%s].v" % l, l, vb[l]["v"])
    vcheck("verify/transport-263/C1-audit/results_pure.json", "%s.v_hex" % l, l, t1a[l]["v_hex"], 16)
    vcheck("verify/transport-263/C1-recompute/results_c1.json", "per_curve.%s.v_int" % l, l, t1r[l]["v_int"])

# transport-263 per-curve flags / costs
tr = sw["transport-263"]
TR_FLAGS = ["transport_ok", "codomain_j_is_1", "planted_check_ok", "kernel_ok", "kernel_galois_stable_Fq2", "twist_263_sylow_cyclic",
            "sage_agrees_explicit", "hom_full_group_ok", "toy_dlp_recovered_on_E0", "dual_ok", "frobenius_conjugate_kernel_ok",
            "frobenius_conjugate_transport_planted_ok", "pari_ellisogeny_ok"]
for l in FLOOR:
    for fl in TR_FLAGS:
        cmp("T7_transport_flags", "transport-263 per-curve boolean checks all true", "transport-263/per_curve.json", fl, l, tr[l].get(fl), True, "expected")
    cmp("T8_eval_ops", "Velu evaluation op count per point", "transport-263/per_curve.json", "eval_ops_per_point", l, tr[l]["eval_ops_per_point"],
        {"M": 914, "S": 131, "I": 1, "A": 788}, "verify/transport-263/C4-audit/count_ops.json velu_eval_instrumented (A counted incl. final +v)")
ca = jload("verify/transport-263/C4-audit/count_ops.json")
for l, rec_ in ca["build_instrumented"].items():
    cmp("T9_build_ops", "build op count (sweep counter) re-run by C4-audit", "transport-263/per_curve.json", "build_ops", l, tr[l]["build_ops"], rec_["sweep_manual_counter_rerun"], "verify/transport-263/C4-audit/count_ops.json")
rng = {k: [min(tr[l]["build_ops"][k] for l in FLOOR), max(tr[l]["build_ops"][k] for l in FLOOR)] for k in ("M", "S", "I", "A")}
cmp("T9_build_ops", "build op ranges over 262 curves", "transport-263/per_curve.json", "build_ops (min,max over floor)", "floor", rng, ca["build_ops_range_all_262"], "verify/transport-263/C4-audit/count_ops.json build_ops_range_all_262")

# ---- (R) rho figures -------------------------------------------------------------------
def native(l):
    return RHO_E0 if l == "E0" else RHO_NEG
RHO_KEYS = [  # (sweep, key, kind)
    ("group-order", "pohlig_hellman/generic_rho_log2_iterations_on_this_curve_alone", "native"),
    ("weil-descent-ghs", "rho_baseline_log2_iterations", "native"),
    ("rho-endomorphisms", "intrinsic_rho_log2", "native"),
    ("rho-endomorphisms", "effective_rho_log2", "effective"),
    ("transport-263", "rho_direct_log2", "native"),
    ("transport-263", "effective_log2", "effective"),
    ("p-levels", "log2_rho_intrinsic", "native"),
    ("literature", "native_log2_iterations", "native"),
    ("literature", "effective_log2_iterations_best_known", "effective"),
    ("toy-analogue-a", "native_rho_log2_iters", "native"),
    ("toy-analogue-a", "effective_log2_iters", "effective"),
]
for l in LABELS:
    for s, key, kind in RHO_KEYS:
        v = get(sw[s][l], key)
        ref = native(l) if kind == "native" else RHO_E0
        cmp("R1_rho_" + kind, "%s rho log2 (native: E0 %.5f with <-1,tau>, floor %.5f with <-1>; effective: %.5f)" % (kind, RHO_E0, RHO_NEG, RHO_E0),
            s + "/per_curve.json", key, l, v, ref, "nt_checks sqrt(pi*N/(2*class)) at 200-bit precision", eq=feq)
    e = tr[l]["effective_log2"]
    cmp("R2_transport_increment", "transport-263 effective - rho_E0 in [0, 1e-9] bits", "transport-263/per_curve.json", "effective_log2", l, 0 <= e - RHO_E0 < 1e-9, True, "nt_checks rho_E0")
    if l != "E0":
        cmp("R3_gap", "native - effective = log2(131)/2 (3 dp)", "toy-analogue-a/per_curve.json", "native_minus_effective_log2", l, sw["toy-analogue-a"][l]["native_minus_effective_log2"], GAP, "nt_checks", eq=feq)
    re_ = sw["rho-endomorphisms"][l]
    cmp("R4_class_size", "rho equivalence-class size (262 = 2*131 with tau on E0, 2 with negation only)", "rho-endomorphisms/per_curve.json", "class_size", l, re_["class_size"], 262 if l == "E0" else 2, "j in F_2 iff tau exists")
    cmp("R4_class_size", "rho group", "rho-endomorphisms/per_curve.json", "rho_group", l, re_["rho_group"], "<-1, tau>" if l == "E0" else "<-1>", "j in F_2 iff tau exists")
    cmp("R5_twist_rho", "twist rho on P114 (E0': <-1,tau>, floor twists: <-1>)", "group-order/per_curve.json", "twist_pohlig_hellman/generic_rho_log2_iterations", l,
        go[l]["twist_pohlig_hellman"]["generic_rho_log2_iterations"], RHO_TW_TAU if l == "E0" else RHO_TW_NEG, "nt_checks", eq=feq)

# ---- (L) literature small-isogeny neighbours vs Phi_l mod 2 root finding ---------------------------
lit = sw["literature"]
for l in LABELS:
    for key in ("l=2", "l=11", "l=29"):
        mine = sorted([list(x) for x in nt["small_isogeny_neighbours"][l][key]["Fq_roots_with_mult"]])
        theirs = sorted([list(x) for x in lit[l]["small_isogeny_neighbours_computed"][key]])
        cmp("L1_neighbours", "F_q-rational l-isogeny neighbours with multiplicity (roots of Phi_l(j,Y) mod 2)", "literature/per_curve.json",
            "small_isogeny_neighbours_computed/" + key, l, theirs, mine, "G6 nt_checks.py (classical_modular_polynomial mod 2, roots over F_q)")
# the l=11 neighbours are X_{k+-16}: consistent with rho-endomorphisms' 11-isogeny o Frob^16 endomorphism
for l in FLOOR:
    X, k = l[0], int(l[1:])
    exp = sorted([["%s%03d" % (X, (k + 16) % 131), 1], ["%s%03d" % (X, (k - 16) % 131), 1]])
    mine = sorted([list(x) for x in nt["small_isogeny_neighbours"][l]["l=11"]["Fq_roots_with_mult"]])
    cmp("L2_11_isogeny_shift16", "11-neighbours of X_k are X_{k+-16} (rho-endomorphisms: psi = 11-isogeny o Frob^16)",
        "rho-endomorphisms/per_curve.json", "cheapest_explicit_endo", l, mine, exp, "G6 nt_checks.py neighbours")
    cmp("L2_11_isogeny_shift16", "rho-endomorphisms names the 11-isogeny o Frob^16 endomorphism", "rho-endomorphisms/per_curve.json", "cheapest_explicit_endo", l,
        "11-isogeny o Frob^16" in sw["rho-endomorphisms"][l]["cheapest_explicit_endo"], True, "string")

# ---- (P) p-levels per-curve fields ---------------------------------------------------------------
pl = sw["p-levels"]
for l in LABELS:
    r = pl[l]
    cmp("P1_c", "pi acts on E[p] as the scalar c = t/2 mod p", "p-levels/per_curve.json", "pi_on_E[p]", l, nt["c_t_over_2_mod_p"] in r["pi_on_E[p]"], True, "nt_checks c")
    cmp("P2_num_p_isog", "number of p-isogenies = p+1", "p-levels/per_curve.json", "num_p_isogenies", l, r["num_p_isogenies"], nt["num_p_isogenies_p_plus_1"], "nt_checks")
    cmp("P2_num_p_isog", "number of F_q-rational p-isogenies = p+1 (pi scalar on E[p])", "p-levels/per_curve.json", "num_p_isogenies_Fq_rational", l, r["num_p_isogenies_Fq_rational"], nt["num_p_isogenies_p_plus_1"], "nt_checks")
    cmp("P3_horizontal", "0 horizontal p-isogenies (p inert: kronecker(-7,p) = -1)", "p-levels/per_curve.json", "num_p_isogenies_horizontal", l, r["num_p_isogenies_horizontal"], 0 if nt["kronecker_-7_p"] == -1 else None, "nt_checks kronecker")
    cmp("P4_r", "p-kernel point field degree r = ord_p(c)", "p-levels/per_curve.json", "p_kernel_point_field_degree_over_Fq", l, r["p_kernel_point_field_degree_over_Fq"], nt["r_ord_p_c"], "nt_checks")
    cmp("P4_r", "p-kernel x field degree r/2", "p-levels/per_curve.json", "p_kernel_x_field_degree_over_Fq", l, r["p_kernel_x_field_degree_over_Fq"], nt["r_x"], "nt_checks")
    cmp("P5_land", "p-isogenies land on level p (from E0) / 263p (from floor)", "p-levels/per_curve.json", "p_isogenies_land_on_level", l, r["p_isogenies_land_on_level"],
        "p (conductor p)" if l == "E0" else "263p (conductor 263p)", "conductor * p")

# ---- (I) index calculus counts -------------------------------------------------------------------
ic = sw["index-calculus"]
rc_counts = jload("index-calculus/raw_counts.json")
canon = [int(x) for x in rc_counts["log"]["subspace_bases"]["canon"]]
cmp("I0_trace_mask", "index-calculus trace mask == G6 trace mask", "index-calculus/raw_counts.json", "log/trace_mask_int", "class", int(rc_counts["log"]["trace_mask_int"]), F.TRMASK, "G6 gf2_131.TRMASK")
cc = jload("verify/index-calculus/C1-density-matches-null-audit:/counts_c.json")["counts"]
cm = jload("verify/index-calculus/C1-density-matches-null-recompute:/counts_mine.json")["counts"]
def recount(b, k):
    basis = canon[:k]
    cnt = 0
    for mask in range(1 << k):
        x = 0
        for i in range(k):
            if (mask >> i) & 1:
                x ^= basis[i]
        if x == 0 or F.trace(x ^ F.mul(b, F.inv(F.sq(x)))) == 0:
            cnt += 1
    return cnt
RECOUNT_K = (8, 10)
for l in LABELS:
    r = ic[l]
    for k in (8, 10, 12, 14, 16):
        c_sw = r["count_incl_x0"]["canon"]["k%d" % k]
        cmp("I1_density", "density_k == count_incl_x0/2^k", "index-calculus/per_curve.json", "density_k%d" % k, l, r["density_k%d" % k], c_sw / 2 ** k, "same file count_incl_x0.canon")
        cmp("I2_counts_vs_audit", "canon counts vs verify/index-calculus C1 audit (C code)", "index-calculus/per_curve.json", "count_incl_x0/canon/k%d" % k, l, c_sw, cc[l]["canon"][k - 1], "verify/index-calculus/C1-density-matches-null-audit:/counts_c.json")
        cmp("I2_counts_vs_audit", "canon counts vs verify/index-calculus C1 recompute", "index-calculus/per_curve.json", "count_incl_x0/canon/k%d" % k, l, c_sw, cm[l]["canon"][str(k)], "verify/index-calculus/C1-density-matches-null-recompute:/counts_mine.json")
    for k in RECOUNT_K:
        mine = recount(b_of[l], k)
        recomputed[l]["canon_count_k%d" % k] = mine
        cmp("I3_counts_recount", "canon counts recounted here (pure python, first k canon basis vectors)", "index-calculus/per_curve.json", "count_incl_x0/canon/k%d" % k, l, r["count_incl_x0"]["canon"]["k%d" % k], mine, "G6 recount")

# ---- codex-crosscheck and other booleans ------------------------------------------------------
cx = sw["codex-crosscheck"]
for l in LABELS:
    cmp("X1_codex", "codex_label_match and codex_values_match", "codex-crosscheck/per_curve.json", "codex_label_match,codex_values_match", l,
        (cx[l]["codex_label_match"], cx[l]["codex_values_match"]), (True, True), "expected")
    allb = all(v for sect in ("label_checks", "value_checks") for v in cx[l].get(sect, {}).values())
    cmp("X1_codex", "all label_checks / value_checks true", "codex-crosscheck/per_curve.json", "label_checks,value_checks", l, allb, True, "expected")
    ta = sw["toy-analogue-a"][l].get("transport")
    if l != "E0":
        cmp("X2_toy_transport", "toy-analogue-a real-curve transport flags", "toy-analogue-a/per_curve.json", "transport", l,
            (ta["codomain_j_is_1"], ta["pi_acts_as_minus_1_on_kernel"], ta["kernel_x_in_Fq"], ta["E_Fq2_263_torsion_is_one_line"], ta["planted_relations_ok"]),
            (True, True, True, True, "3/3"), "expected")

# ---- a2 as stored by verify outputs ----------------------------------------------------------------
for d in jload("verify/index-calculus/C4-class-wide-Tr(b)=1-recompute:/check_class_own.json")["per_curve"]:
    cmp("B0b_a2_verify", "a2 stored by verify outputs == ground truth", "verify/index-calculus/C4-class-wide-Tr(b)=1-recompute:/check_class_own.json", "per_curve[].a2", d["label"], d["a2"], REC[d["label"]]["a2"], "ground_truth.json a2")
for l, d in jload("verify/pairing-transfer/C2-audit/c2_pure_python.json")["per_curve"].items():
    cmp("B0b_a2_verify", "a2 stored by verify outputs == ground truth", "verify/pairing-transfer/C2-audit/c2_pure_python.json", "per_curve.%s.a2" % l, l, d["a2"], REC[l]["a2"], "ground_truth.json a2")
for d in jload("verify/pairing-transfer/C5-recompute/c5_recompute.json")["per_curve"]:
    cmp("B0b_a2_verify", "a2 stored by verify outputs == ground truth", "verify/pairing-transfer/C5-recompute/c5_recompute.json", "per_curve[].a2", d["label"], d["a2"], REC[d["label"]]["a2"], "ground_truth.json a2")

# ---- every stored copy of the class constants (non-toy JSON under the sweeps, ground_truth_check, verify/) ----
import glob
CONST = {"t": t, "N": N, "p": p, "f": int(nt["f"]), "card": CARD, "twist": TW, "P114": P114}
KEYMAP = {"t": ["t", "trace_t", "t (Lucas, own)", "t (from tau^131 in Z[w])", "t (Lucas V_131, ladder)", "t = 2A - B", "trace t", "t_from_pari_card", "agm_trace_prec80", "agm_trace_prec96"],
          "N": ["N", "N = #E0/4", "N_E"],
          "p": ["p", "p = f/263"],
          "f": ["f", "f = |B| (index of Z[pi] in O_K)", "f = |coefficient of w in pi|", "f = |U_131| (Lucas U, ladder), t^2-4q == -7 f^2"],
          "card": ["card", "card_4N", "CARD", "#E0 = q+1-t", "card_derived", "card_proved", "cardE", "order", "order_pari"],
          "twist": ["twist_card", "twist_order", "cardTwist", "TW", "twist_order_pari"],
          "P114": ["P114", "TW_cofactor"]}
REV = {k: c_ for c_, ks in KEYMAP.items() for k in ks}
# contexts where these key names do not denote the class constants (recorded in the report)
EXCLUDED_CONTEXTS = {"null_curves": "random null-model curves (index-calculus), different orders by design",
                     "cheap_family": "rho-endomorphisms: 'order' = eigenvalue order of an endomorphism",
                     "all_y_nonzero": "rho-endomorphisms: eigenvalue orders",
                     "codex_psi_candidates": "rho-endomorphisms: eigenvalue orders",
                     "/h/": "p-levels: class numbers keyed by level ('p' -> h(O_p) = p+1)",
                     "/h per level": "p-levels: class numbers keyed by level",
                     "toy": "toy-scale parameters",
                     "synth": "synthetic toy parameters (also files named *synth*, e.g. RT2-13-0/synth_summary.json N = 549756390943)",
                     "/Fq2/": "#E(F_{q^2}); compared separately with (q+1-t)(q+1+t)"}
const_files = []
for pat in [s_ + "/*.json" for s_ in SWEEPS] + ["ground_truth_check/*.json", "verify/*/*/*.json", "verify/*/*/raw/*.json"]:
    const_files += glob.glob(P(pat))
n_const_files = 0
for fpath in sorted(set(const_files)):
    rel = os.path.relpath(fpath, W)
    if "toy" in rel.lower() or "synth" in rel.lower() or os.path.getsize(fpath) > 5_000_000:
        continue
    try:
        dd = load(fpath)
    except Exception:
        continue
    n_const_files += 1
    def walkc(x, path):
        if isinstance(x, dict):
            for k_, v_ in x.items():
                fullp = path + "/" + str(k_) + "/"
                if "/Fq2/" in fullp and k_ == "card":
                    cmp("K2_card_Fq2", "#E(F_{q^2}) stored copies == (q+1-t)(q+1+t)", rel, fullp[:200], "class", int(v_), CARD * TW, "nt_checks card*twist")
                if any(xc in fullp for xc in EXCLUDED_CONTEXTS):
                    walkc(v_, path + "/" + str(k_))
                    continue
                if k_ in REV and isinstance(v_, (int, str)) and not isinstance(v_, bool):
                    try:
                        iv = int(v_)
                    except (ValueError, TypeError):
                        iv = None
                    if iv is not None and abs(iv) > 10 ** 9:
                        cmp("K1_class_constants", "stored copies of t, N, p, f, #E, twist order, P114 (non-toy files)", rel, (path + "/" + k_)[:200], "class",
                            iv, CONST[REV[k_]], "nt_checks (%s)" % REV[k_])
                walkc(v_, path + "/" + str(k_))
        elif isinstance(x, list):
            for i_, v_ in enumerate(x[:300]):
                walkc(v_, path + "[%d]" % i_)
    walkc(dd, "")
checks_meta_hd["n_files_scanned_for_constants"] = n_const_files

# ------------------------------------------------------------------ verify coverage (for verified_by)
cov = {}   # field -> label -> list of verify dirs
def covadd(field, label, vdir):
    cov.setdefault(field, {}).setdefault(label, [])
    if vdir not in cov[field][label]:
        cov[field][label].append(vdir)

for line in open(P("verify/codex-crosscheck/C1-recompute/order_out.jsonl")):
    d = json.loads(line)
    if d.get("card_is_4N") and d.get("all_killed_by_4N"):
        covadd("order", d["label"], "verify/codex-crosscheck/C1-recompute")
for d in jload("verify/codex-crosscheck/C2-recompute/all_curves_N_divides.json")["per_curve"]:
    if d.get("N_divides_order"):
        covadd("order", d["label"], "verify/codex-crosscheck/C2-recompute")
c3p = jload("verify/codex-crosscheck/C3-audit/c3_pure.json")["curves"]
for l, d in c3p.items():
    if d.get("E_order_4N_proof"):
        covadd("order", l, "verify/codex-crosscheck/C3-audit")
    if d.get("twist_killed_by_q+1+t"):
        covadd("twist_order", l, "verify/codex-crosscheck/C3-audit")
    if s263(d.get("twist_263_structure")) == ("(Z/263)^2" if l == "E0" else "Z/263^2"):
        covadd("level_263_structure", l, "verify/codex-crosscheck/C3-audit")
pe = jload("verify/codex-crosscheck/C3-recompute/pari_ellgroup_result.json")["curves"]
for l, d in pe.items():
    if int(d["cardE"]) == CARD:
        covadd("order", l, "verify/codex-crosscheck/C3-recompute")
    if int(d["cardTwist"]) == TW:
        covadd("twist_order", l, "verify/codex-crosscheck/C3-recompute")
    if s263(d["twist_263_structure"]) == ("(Z/263)^2" if l == "E0" else "Z/263^2"):
        covadd("level_263_structure", l, "verify/codex-crosscheck/C3-recompute")
oa = jload("verify/codex-crosscheck/C3-recompute/own_arith_result.json")
for l, d in oa["twist"].items() if isinstance(oa.get("twist"), dict) else []:
    if s263(d.get("structure")) == ("(Z/263)^2" if l == "E0" else "Z/263^2"):
        covadd("level_263_structure", l, "verify/codex-crosscheck/C3-recompute")
for d in jload("verify/index-calculus/C4-class-wide-Tr(b)=1-recompute:/check_class_own.json")["per_curve"]:
    if d.get("Tr_b") == recomputed[d["label"]]["Tr_b"] and d.get("a2") == 0:
        covadd("Tr_b", d["label"], "verify/index-calculus/C4-class-wide-Tr(b)=1-recompute:")
    if d.get("point_of_order_4N"):
        covadd("order", d["label"], "verify/index-calculus/C4-class-wide-Tr(b)=1-recompute:")
for d in jload("verify/index-calculus/C4-class-wide-Tr(b)=1-recompute:/check_pari.json")["class_per_curve"]:
    if d.get("Tr_b_pari") == recomputed[d["label"]]["Tr_b"]:
        covadd("Tr_b", d["label"], "verify/index-calculus/C4-class-wide-Tr(b)=1-recompute:")
    if d.get("card_eq_4N"):
        covadd("order", d["label"], "verify/index-calculus/C4-class-wide-Tr(b)=1-recompute:")
for l in LABELS:
    if cc.get(l) and all(cc[l]["canon"][k - 1] == ic[l]["count_incl_x0"]["canon"]["k%d" % k] for k in (8, 10, 12, 14, 16)):
        covadd("index_calculus_density", l, "verify/index-calculus/C1-density-matches-null-audit:")
    if cm.get(l) and all(cm[l]["canon"][str(k)] == ic[l]["count_incl_x0"]["canon"]["k%d" % k] for k in (8, 10, 12, 14, 16)):
        covadd("index_calculus_density", l, "verify/index-calculus/C1-density-matches-null-recompute:")
p2a = jload("verify/pairing-transfer/C2-audit/c2_pure_python.json")["per_curve"]
for l, d in p2a.items():
    if d.get("k_E") == nt["embedding_degree_ord_N_q"]:
        covadd("embedding_degree", l, "verify/pairing-transfer/C2-audit")
    if d.get("N_Q_is_O") and d.get("gt_order_pari_matches"):
        covadd("order", l, "verify/pairing-transfer/C2-audit")
    if d.get("twist_[q+1+t]R_is_O") and d.get("gt_twist_order_pari_matches"):
        covadd("twist_order", l, "verify/pairing-transfer/C2-audit")
p2r = jload("verify/pairing-transfer/C2-recompute/c2_own_arith.json")["per_curve"]
for l, d in p2r.items():
    if d.get("k") == nt["embedding_degree_ord_N_q"]:
        covadd("embedding_degree", l, "verify/pairing-transfer/C2-recompute")
    if int(d.get("card_proved", 0)) == CARD:
        covadd("order", l, "verify/pairing-transfer/C2-recompute")
for d in jload("verify/pairing-transfer/C3-recompute/c3_results_all.json")["curves"]:
    pp = d["pairing_263"]
    okQN = any(k_.startswith("t(P,Q_N)==1") and v_ is True for k_, v_ in pp.items())
    if okQN:
        covadd("tate_263_QN_trivial", d["label"], "verify/pairing-transfer/C3-recompute")
    if s263(pp.get("structure")) == ("(Z/263)^2" if d["label"] == "E0" else "Z/263^2"):
        covadd("level_263_structure", d["label"], "verify/pairing-transfer/C3-recompute")
p4a = jload("verify/pairing-transfer/C4-audit/c4_pure_python_all.json")["per_curve"]
for l, d in p4a.items():
    if d.get("twist_TW_kills_point") and d.get("twist_r_divides_point_order"):
        covadd("twist_order", l, "verify/pairing-transfer/C4-audit")
    if d.get("E_4N_point_check"):
        covadd("order", l, "verify/pairing-transfer/C4-audit")
    if s263(d.get("twist_263_part")) == ("(Z/263)^2" if l == "E0" else "Z/263^2"):
        covadd("level_263_structure", l, "verify/pairing-transfer/C4-audit")
for d in jload("verify/pairing-transfer/C5-recompute/c5_recompute.json")["per_curve"]:
    if d.get("a2") == 0 and d.get("jb_eq_1"):
        covadd("curve_model", d["label"], "verify/pairing-transfer/C5-recompute")
    if d.get("point_of_order_4N"):
        covadd("order", d["label"], "verify/pairing-transfer/C5-recompute")
    if d.get("twist_killed_by_q+1+t"):
        covadd("twist_order", d["label"], "verify/pairing-transfer/C5-recompute")
def allbool(d, minimum=3):
    bs = [v for k_, v in d.items() if isinstance(v, bool) and not k_.startswith("info")]
    return len(bs) >= minimum and all(bs)
# transport verification (floor)
for l, d in t1a.items():
    if d.get("all_ok"):
        covadd("transport", l, "verify/transport-263/C1-audit")
for l, d in t1r.items():
    if allbool(d):
        covadd("transport", l, "verify/transport-263/C1-recompute")
for l, d in jload("verify/transport-263/C2-audit/indep_results.json").items():
    if isinstance(d, dict) and allbool(d):
        covadd("transport", l, "verify/transport-263/C2-audit")
for l, d in jload("verify/transport-263/C2-recompute/results.json").items():
    if isinstance(d, dict) and d.get("all_ok"):
        covadd("transport", l, "verify/transport-263/C2-recompute")
for d in jload("verify/transport-263/C3-recompute/c3_pure_all.json")["per_curve"]:
    if allbool(d):
        covadd("transport", d["label"], "verify/transport-263/C3-recompute")
for l, d in jload("verify/transport-263/C3-recompute/c3_gp_phi_merged.json")["per_label"].items():
    if d.get("ok") and d.get("n_rational_roots") == 1 and d.get("root_is_1"):
        covadd("level_phi263", l, "verify/transport-263/C3-recompute")
for line in open(P("verify/transport-263/C4-recompute/run.jsonl")):
    d = json.loads(line)
    lab = d.get("label") or d.get("L")
    if lab and all(d.get(k_) == 1 for k_ in ("kernel_ok", "codomain_is_E0", "image_on_E0", "dlp_preserved", "hom", "image_order_N")):
        covadd("transport", lab, "verify/transport-263/C4-recompute")
for l, d in jload("verify/transport-263/C5-recompute/c5_results.json")["per_curve"].items():
    if d.get("S5_codomain_is_E0") and d.get("S5_planted_scalar_ok"):
        covadd("transport", l, "verify/transport-263/C5-recompute")
for l, d in va.items():
    if d.get("all_ok"):
        covadd("transport", l, "verify/toy-analogue-a/C5-audit")
for l, d in vr.items():
    if allbool(d):
        covadd("transport", l, "verify/toy-analogue-a/C5-recompute")
for l, d in vb.items():
    if all(d.get(k_) == 1 for k_ in ("codomain_is_E0", "images_on_E0", "image_order_N", "dlp_preserved_upto_sign")):
        covadd("transport", l, "verify/toy-analogue-b/C3-audit")
for l, d in phr.items():
    if [d["n_distinct_Fq_roots"], d["mult_root_1"]] == ([263, 2] if l == "E0" else [1, 1]):
        covadd("level_phi263", l, "verify/codex-crosscheck/C3-recompute")
covsummary = {f_: {"n_labels": len(v), "dirs": sorted({d for ds in v.values() for d in ds})} for f_, v in cov.items()}

# ------------------------------------------------------------------ write
summary = {cid: {"description": c["description"], "n_compared": c["n_compared"], "n_agree": c["n_agree"],
                 "n_disagree": c["n_compared"] - c["n_agree"], "sources": c["sources"], "reference": c["reference"]}
           for cid, c in sorted(checks.items())}
report = {
    "script": "crosscheck.py",
    "inputs_sha256": INPUTS,
    "step1_label_sets": step1,
    "n_checks": len(summary),
    "n_comparisons": sum(c["n_compared"] for c in summary.values()),
    "n_disagreements": len(disagreements),
    "checks": summary,
    "disagreements": disagreements,
    "hd_mod2_meta": checks_meta_hd,
    "class_constant_scan_excluded_contexts": EXCLUDED_CONTEXTS,
    "recomputed_per_curve": {l: {**recomputed[l], **({"transport_v_int": str(vmine[l])} if l in vmine else {})} for l in LABELS},
    "verify_coverage": {"summary": covsummary, "per_field_label": cov},
    "seconds": round(time.time() - T0, 1),
}
json.dump(report, open(os.path.join(HERE, "crosscheck_report.json"), "w"), indent=1, default=str)
print("checks", len(summary), "comparisons", report["n_comparisons"], "disagreements", len(disagreements), "seconds", report["seconds"])
for cid, c in summary.items():
    flag = "" if c["n_disagree"] == 0 else "   <-- %d disagree" % c["n_disagree"]
    print("  %-26s %5d/%5d%s" % (cid, c["n_agree"], c["n_compared"], flag))
print("coverage:", json.dumps(covsummary)[:1500])
