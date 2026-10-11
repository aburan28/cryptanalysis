#!/usr/bin/env python3
"""Merge the per-curve sweep outputs into report/per_curve_hardness.csv.

Plain python3, no Sage.  Reads only JSON outputs already on disk under
/Volumes/SSD990/ecdlp-hardness-work/, cross-checks every column against every
other sweep that stores the same quantity, recomputes the closed-form numbers
(rho log2, log2 of N, k, class numbers) from the integers stored in
ground_truth.json, and writes:

  report/per_curve_hardness.csv          one row per curve (E0 + 262 floor curves)
  report/per_curve_hardness.columns.json column dictionary + provenance
  report/hardness_by_level.csv           levels 1, 263, p, 263p
  report/merge_check.json                missing values, cross-sweep disagreements, recomputed constants
"""
import csv, json, math, os, sys, hashlib
from fractions import Fraction

W = "/Volumes/SSD990/ecdlp-hardness-work"
OUT = os.path.join(W, "report")


def load(rel):
    with open(os.path.join(W, rel)) as fh:
        return json.load(fh)


def sha(rel):
    with open(os.path.join(W, rel), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


INPUTS = [
    "ground_truth/ground_truth.json",
    "group-order/per_curve.json",
    "endomorphism-ring/per_curve.json",
    "pairing-transfer/per_curve.json",
    "weil-descent-ghs/per_curve.json",
    "gaps/G2-verify-weil-descent-ghs/per_curve_G2.json",
    "rho-endomorphisms/per_curve.json",
    "gaps/G1-verify-rho-endomorphisms/per_curve.json",
    "transport-263/per_curve.json",
    "transport-263/summary.json",
    "index-calculus/per_curve.json",
    "codex-crosscheck/per_curve.json",
    "p-levels/per_curve.json",
    "literature/per_curve.json",
    "toy-analogue-a/per_curve.json",
    "gaps/G5-per-curve-summation-polynomial-n131/per_curve.json",
    "gaps/G6-consolidate-and-cross-check-per-curve/per_curve_hardness.json",
    "gaps/G4-reconcile-B2-levels-and-literature/levels_reconciled.json",
]

gt = load("ground_truth/ground_truth.json")
go = load("group-order/per_curve.json")
er = load("endomorphism-ring/per_curve.json")
pt = load("pairing-transfer/per_curve.json")
gh = load("weil-descent-ghs/per_curve.json")
g2 = load("gaps/G2-verify-weil-descent-ghs/per_curve_G2.json")["curves"]
re_ = load("rho-endomorphisms/per_curve.json")
g1 = load("gaps/G1-verify-rho-endomorphisms/per_curve.json")
tr = load("transport-263/per_curve.json")
trs = load("transport-263/summary.json")
ic = load("index-calculus/per_curve.json")
cx = load("codex-crosscheck/per_curve.json")
pl = load("p-levels/per_curve.json")
li = load("literature/per_curve.json")
ta = load("toy-analogue-a/per_curve.json")
g5 = load("gaps/G5-per-curve-summation-polynomial-n131/per_curve.json")
g6 = load("gaps/G6-consolidate-and-cross-check-per-curve/per_curve_hardness.json")
g4 = load("gaps/G4-reconcile-B2-levels-and-literature/levels_reconciled.json")

meta = gt["meta"]
q = 2 ** 131
t = int(meta["t"])
N = int(meta["N"])
CARD = int(meta["card"])
TW = int(meta["twist_card"])
p = int(meta["p"])
f = int(meta["f"])

# ---------------------------------------------------------------- recomputed constants
recomputed = {}
assert q + 1 - t == CARD == 4 * N
assert q + 1 + t == TW
assert t * t - 4 * q == -7 * f * f and f == 263 * p
recomputed["log2_N"] = math.log2(N)
recomputed["rho_E0_log2"] = 0.5 * math.log2(math.pi * N / (2 * 262))
recomputed["rho_floor_native_log2"] = 0.5 * math.log2(math.pi * N / (2 * 2))
recomputed["rho_no_negation_log2"] = 0.5 * math.log2(math.pi * N / 2)
recomputed["native_minus_E0_bits"] = recomputed["rho_floor_native_log2"] - recomputed["rho_E0_log2"]
recomputed["half_log2_131"] = 0.5 * math.log2(131)
# embedding degree: ord_N(q) by factoring N-1 with the factorisation stored in pairing-transfer
fac = {2: 3, 3: 1, 11: 1, 109: 1, 131: 1, 263: 1, 32326729: 1, 21234899465981031419669: 1}
prod = 1
for pr, e in fac.items():
    prod *= pr ** e
assert prod == N - 1, "stored N-1 factorisation does not multiply back"
k = N - 1
for pr, e in fac.items():
    for _ in range(e):
        if pow(q, k // pr, N) == 1:
            k //= pr
recomputed["embedding_degree_k"] = str(k)
recomputed["embedding_degree_bitlength"] = k.bit_length()
recomputed["embedding_degree_log2"] = math.log2(k)
recomputed["(N-1)/k"] = (N - 1) // k
assert pow(q, k, N) == 1
# class numbers at the four levels (kronecker(-7,263)=+1, kronecker(-7,p)=-1, unit index 1)
def kron_m7(l):
    # Legendre symbol (-7/l) for odd prime l != 7 via Euler's criterion
    return 1 if pow((-7) % l, (l - 1) // 2, l) == 1 else -1
recomputed["kronecker(-7,263)"] = kron_m7(263)
recomputed["kronecker(-7,p)"] = kron_m7(p)
h263 = 263 - kron_m7(263)
hp = p - kron_m7(p)
recomputed["h"] = {"1": 1, "263": h263, "p": hp, "263p": h263 * hp}
recomputed["log2_h"] = {kk: (math.log2(v) if v > 1 else 0.0) for kk, v in recomputed["h"].items()}
recomputed["sqrt_h_log2"] = {"p": 0.5 * math.log2(hp), "263p": 0.5 * math.log2(h263 * hp)}
recomputed["log2_p"] = math.log2(p)
# order of c = t/2 mod p
c = (t * pow(2, -1, p)) % p
recomputed["c=t/2 mod p"] = str(c)

# ---------------------------------------------------------------- merge
labels = [r["label"] for r in gt["curves"]]
assert len(labels) == 263 and labels[0] == "E0"
gtc = {r["label"]: r for r in gt["curves"]}
disagree = []   # (label, column, detail)


def chk(label, col, cond, detail):
    if not cond:
        disagree.append({"label": label, "column": col, "detail": detail})


# curves with extra per-label evidence, all read from files named in the notes
explicit_transport_demo = {
    "rho-endomorphisms transfer demo": {"A000", "A064", "B000", "B097"},
    "endomorphism-ring transfer demo": {"A000", "B095"},
    "ground_truth_check explicit Kohel isogeny + order transfer": {"A000", "A001", "A010", "A064", "A090", "A112", "A127",
                                                                  "B000", "B021", "B064", "B095", "B130"},
    "Codex run-04 explicit 263-map (reproduced by codex-crosscheck C4)": {"A090", "B021", "B067"},
}
phi263_cofactor_irreducible = {"A000", "A001", "A064", "A090", "B000", "B021", "B067", "B130",  # codex-crosscheck C3-recompute
                               "A065"}                                                            # endomorphism-ring
divpoly_263_unique = {"A000", "B000", "B077"}                                                    # transport-263 C3-audit
order4N_flag_vacuous_in_replay = {"A001", "A010", "A130"}                                         # transport-263 C2-audit replay
g5_measured = set(g5.keys())

rows = []
for lab in labels:
    g = gtc[lab]
    is_e0 = lab == "E0"
    level = int(g["level"])
    j = int(g["j_int"])
    b = int(g["b_int"])
    notes = []

    # level / orbit consistency
    chk(lab, "level", er[lab]["level"] == level and pt[lab]["level"] == level and re_[lab]["level"] == level
        and li[lab]["level_conductor"] == level and int(er[lab]["conductor"]) == level
        and ta[lab]["level"] == level, "level differs between sweeps")
    chk(lab, "orbit", all(src[lab]["orbit"] == g["orbit"] for src in (er, pt, re_, ic, pl, li, ta)), "orbit label differs")
    chk(lab, "frob_index", er[lab]["frob_index"] == g["frob_index"] and li[lab]["frob_index"] == g["frob_index"], "frob_index differs")
    chk(lab, "b_hex", int(g2[lab]["b_int"]) == b and int(g6["curves"][lab]["curve"]["value"]["b_int"]) == b, "b differs from G2/G6")
    chk(lab, "j*b", True, "")
    chk(lab, "a2", g["a2"] == 0 and g2[lab]["a2"] == 0, "a2 != 0")

    # order
    order_ok = (go[lab]["order_ok"] is True and g["order_verified"] is True and g["order_point_proof"] is True
                and int(g["order_pari"]) == CARD and int(go[lab]["order"]) == CARD
                and cx[lab]["value_checks"].get("order_4N_point_proof") is True
                and er[lab]["card_Fq_own_arith"].startswith("4N")
                and go[lab]["evidence"]["agm_trace_prec96"] == meta["t"])
    chk(lab, "order_ok", order_ok, "an order check is not true")
    two_part = go[lab]["two_primary"]
    chk(lab, "two_part_structure", two_part == "Z/4" and go[lab]["two_torsion_points"] == 1
        and go[lab]["evidence"]["explicit_order4_point_x_eq_b^(1/4)"] is True, "2-part not Z/4")

    # endomorphism ring
    ring = er[lab]["end_ring"]
    ncrit = er[lab]["num_independent_criteria"]
    ring_short = "O_K" if is_e0 else "O_263"
    chk(lab, "end_ring_certified", (ring.startswith("O_K") if is_e0 else ring.startswith("O_263"))
        and (ncrit == 4 if is_e0 else ncrit == 3)
        and er[lab]["sylow263_pari_and_own_agree"] is True
        and er[lab]["phi263_Fq_rational_263_isogenies"] == (264 if is_e0 else 1)
        and li[lab]["end_ring"].startswith(ring_short)
        and g6["curves"][lab]["conductor"]["value"]["conductor"] == str(level), "End ring / conductor evidence inconsistent")
    end_ring_cert = f"{ring_short} (conductor {level}; {ncrit} independent criteria)"

    # embedding degree
    chk(lab, "embedding_degree_bits", pt[lab]["embedding_degree_N"] == recomputed["embedding_degree_k"]
        and pt[lab]["embedding_degree_N_bits"] == recomputed["embedding_degree_bitlength"]
        and pt[lab]["N_subgroup_point_check"] is True
        and g6["curves"][lab]["embedding_degree"]["value"]["k"] == recomputed["embedding_degree_k"], "embedding degree differs")
    emb_bits = pt[lab]["embedding_degree_N_bits"]

    # GHS
    m = gh[lab]["magic_number"]
    chk(lab, "ghs_magic_number", m == g2[lab]["magic_number"] == li[lab]["ghs_magic_number_m_computed"]
        == g6["curves"][lab]["ghs"]["value"]["magic_number_m"] and m == (1 if is_e0 else 131)
        and gh[lab]["trace_b"] == 1 and g2[lab]["trace_b"] == 1 and ic[lab]["Tr_b"] == 1, "GHS m / Tr(b) differs")

    # rho classes
    cls = re_[lab]["class_size"]
    chk(lab, "aut_class_size", cls == (262 if is_e0 else 2) and re_[lab]["Aut_order"] == 2, "class size / Aut differ")
    intrinsic = recomputed["rho_E0_log2"] if is_e0 else recomputed["rho_floor_native_log2"]
    for name, val in (("rho-endomorphisms", re_[lab]["intrinsic_rho_log2"]),
                      ("transport-263", tr[lab]["rho_direct_log2"]),
                      ("p-levels", pl[lab]["log2_rho_intrinsic"]),
                      ("toy-analogue-a", ta[lab]["native_rho_log2_iters"]),
                      ("literature", li[lab]["native_log2_iterations"]),
                      ("G6", g6["curves"][lab]["native_rho_log2"]["value"]["exact"])):
        chk(lab, "intrinsic_rho_log2", abs(val - intrinsic) < 6e-3, f"{name} stores {val}")

    # transport
    T = tr[lab]
    if is_e0:
        tr_ok = "identity"
        tr_cost = 0.0
        chk(lab, "transport_to_E0_ok", T["transport_ok"] is True, "E0 transport flag")
    else:
        flags = ["transport_ok", "codomain_j_is_1", "planted_check_ok", "kernel_ok", "kernel_galois_stable_Fq2",
                 "twist_263_sylow_cyclic", "sage_agrees_explicit", "hom_full_group_ok", "toy_dlp_recovered_on_E0",
                 "dual_ok", "frobenius_conjugate_kernel_ok", "frobenius_conjugate_transport_planted_ok",
                 "pari_ellisogeny_ok"]
        allok = all(T.get(fl) is True for fl in flags) and T["dual_psi_phi_R_eq"] == "-263R"
        allok = allok and er[lab]["velu_up_to_j1"] is True and ta[lab]["transport"]["codomain_j_is_1"] is True \
            and ta[lab]["transport"]["planted_relations_ok"] == "3/3"
        chk(lab, "transport_to_E0_ok", allok, "a transport flag is not true")
        tr_ok = "true" if allok else "false"
        tr_cost = T["transport_cost_log2_M_equiv_upper"]
    eff = T["effective_log2"]
    for name, val in (("rho-endomorphisms", re_[lab]["effective_rho_log2"]),
                      ("toy-analogue-a", ta[lab]["effective_log2_iters"]),
                      ("literature", li[lab]["effective_log2_iterations_best_known"]),
                      ("G6", g6["curves"][lab]["effective_rho_log2"]["value"]["exact"])):
        chk(lab, "effective_hardness_log2", abs(val - eff) < 6e-3, f"{name} stores {val}")
    chk(lab, "effective_hardness_log2", abs(eff - recomputed["rho_E0_log2"]) < 1e-10, "effective differs from E0 rho")

    # index-calculus density
    z16 = ic[lab]["zscores"]["canon"]["k16"]
    maxz = ic[lab]["max_abs_z"]

    # notes
    if is_e0:
        notes.append("crater; Koblitz curve; tau acts as s of order 131 on the N-subgroup")
        notes.append("GHS m=1 cover is E0/F_2 (order 4), kills the N-subgroup")
        notes.append("twist Z/263 x Z/(2*263*P114): x-only oracle only, 2^53.27")
    else:
        notes.append("floor: j of degree 131 over F_2, no tau; unique F_q-rational 263-isogeny goes up to E0")
        nb = li[lab]["small_isogeny_neighbours_computed"]
        notes.append("l=11 nbrs " + "/".join(x[0] for x in nb["l=11"]) + "; l=29 nbrs " + "/".join(x[0] for x in nb["l=29"]))
        notes.append(f"transport build+2 evals <= 2^{tr_cost:.2f} F_q-mult")
    if maxz >= 3.0:
        worst = max(((abs(z), sub, kk, z) for sub, zz in ic[lab]["zscores"].items() for kk, z in zz.items()))
        notes.append(f"IC density max|z|={maxz} ({worst[1]} {worst[2]}, z={worst[3]}); not significant after multiplicity (IC C1)")
    if lab == "B019":
        notes.append("lowest canonical z of the class (-4.16 at k=12, nested -3.36 at k=14); P(min<=obs)=0.017, not significant family-wise")
    if lab == "B113":
        notes.append("wins the canonical best-ratio contest at 5 of 9 k (IC C2 audit, post hoc, ~2% null tail; no density anomaly)")
    if lab == "B063":
        notes.append("canonical best ratio at k=15,16 (0.964 at k=16), also a Codex k=13-16 winner via its 'poly' candidate")
    if lab == "A073":
        notes.append("canonical best ratio at k=8 (0.599), winner's-curse range")
    if lab == "B067":
        notes.append("Codex EXPLOITABILITY: +20.67% relation coverage at k=5 = selection effect (codex-review, codex-crosscheck)")
    if lab == "B023":
        notes.append("Codex: +4.17% coverage at k=4 random (finite constant on a tiny factor base)")
    if lab == "A092":
        notes.append("Codex: +2.17% coverage at k=6 (finite constant on a tiny factor base)")
    if lab == "A010":
        notes.append("Codex 'best same-size descendant at k=4' is one of 30 tied at 80 targets")
    for name, s in explicit_transport_demo.items():
        if lab in s:
            notes.append(name)
    if lab in phi263_cofactor_irreducible:
        notes.append("Phi_263(j,Y) cofactor of degree 263 shown irreducible (explicit; others by Frobenius conjugacy)")
    if lab in divpoly_263_unique:
        notes.append("263-division polynomial has exactly 131 F_q-roots (uniqueness of the rational 263-line, transport C3 audit)")
    if lab in order4N_flag_vacuous_in_replay:
        notes.append("sweep's order_4N_preserved flag was vacuous in replay; re-proved with a chosen order-4N point (transport C2 audit)")
    if lab in g5_measured:
        if is_e0:
            notes.append("n=131 Semaev PDP: d_reg 8 vs 10-11 on the polynomial basis only; every class curve gets 7 on span{(b+1)^j} -> 0-bit difference (G5)")
        else:
            notes.append("n=131 Semaev PDP measured (G5): indistinguishable from random dense-b curves")
    if not is_e0:
        notes.append("errata ERR-01 (eval add count 787 vs 788) and ERR-08 (gGHS pair label) apply; no hardness effect")

    rows.append({
        "label": lab,
        "orbit": g["orbit"],
        "frob_index": g["frob_index"],
        "level": level,
        "j_hex": hex(j),
        "b_hex": hex(b),
        "a2": g["a2"],
        "order_ok": "true" if order_ok else "false",
        "two_part_structure": two_part,
        "end_ring_certified": end_ring_cert,
        "embedding_degree_bits": emb_bits,
        "ghs_magic_number": m,
        "aut_class_size": cls,
        "intrinsic_rho_log2": f"{intrinsic:.4f}",
        "transport_to_E0_ok": tr_ok,
        "transport_cost": f"{tr_cost:.3f}",
        "effective_hardness_log2": f"{eff:.4f}",
        "ic_density_z_k16": f"{z16:.4f}",
        "notes": "; ".join(notes),
    })

# check j*b = 1 in F_q (polynomial basis) with a tiny GF(2^131) implementation
MOD = int(meta["modulus_int"])


def gmul(a, b_):
    r = 0
    while b_:
        if b_ & 1:
            r ^= a
        b_ >>= 1
        a <<= 1
        if a >> 131:
            a ^= MOD
    return r


jb_fail = [lab for lab in labels if gmul(int(gtc[lab]["j_int"]), int(gtc[lab]["b_int"])) != 1]
recomputed["j*b==1 failures"] = jb_fail
# Frobenius labels: j(X_{k+1}) = j(X_k)^2
frob_fail = []
for orb in "AB":
    for kk in range(131):
        a_ = int(gtc[f"{orb}{kk:03d}"]["j_int"])
        b_ = int(gtc[f"{orb}{(kk + 1) % 131:03d}"]["j_int"])
        if gmul(a_, a_) != b_:
            frob_fail.append(f"{orb}{kk:03d}")
recomputed["frobenius_label_failures"] = frob_fail

COLS = ["label", "orbit", "frob_index", "level", "j_hex", "b_hex", "a2", "order_ok", "two_part_structure",
        "end_ring_certified", "embedding_degree_bits", "ghs_magic_number", "aut_class_size", "intrinsic_rho_log2",
        "transport_to_E0_ok", "transport_cost", "effective_hardness_log2", "ic_density_z_k16", "notes"]
with open(os.path.join(OUT, "per_curve_hardness.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=COLS)
    w.writeheader()
    for r in rows:
        w.writerow(r)

missing = {c_: [r["label"] for r in rows if r[c_] in (None, "", "None", "nan")] for c_ in COLS}
missing = {k_: v for k_, v in missing.items() if v}

columns = {
    "label": "curve label (Codex labels reproduced by ground_truth): E0 crater, A000..A130 / B000..B130 floor; source ground_truth/ground_truth.json",
    "orbit": "crater | A | B (Frobenius orbit = F_2-irreducible factor of H_{-7*263^2} mod 2); ground_truth, cross-checked in 7 sweeps",
    "frob_index": "k with j(X_k) = j(X000)^(2^k); ground_truth; recomputed here (j squaring along every orbit edge)",
    "level": "conductor of End(E) in O_K: 1 (E0) or 263 (floor); ground_truth, endomorphism-ring, pairing-transfer, rho-endomorphisms, literature, toy-analogue-a",
    "j_hex": "j-invariant, polynomial basis F_2[z]/(z^131+z^13+z^2+z+1), bit i = z^i; ground_truth",
    "b_hex": "b = 1/j for the model y^2+xy=x^3+a2 x^2+b; ground_truth; j*b=1 recomputed here",
    "a2": "a2 of the twist with order 4N (0 for all 263); ground_truth, G2",
    "order_ok": "#E(F_q)=4N: true iff group-order order_ok, ground_truth order_verified+order_point_proof+order_pari, codex-crosscheck order_4N_point_proof, endomorphism-ring own-arith card and the pure-python AGM trace all agree",
    "two_part_structure": "2-primary part of E(F_q) (group-order: one 2-torsion point, explicit point of order 4 at x=b^(1/4))",
    "end_ring_certified": "End(E) and number of independent certificates run on that curve (endomorphism-ring); conductor cross-checked with literature and G6",
    "embedding_degree_bits": "bit length of k = ord_N(q) = 216464610000596986937760855436835237 (log2 117.38); pairing-transfer, recomputed here from the N-1 factorisation",
    "ghs_magic_number": "GHS magic number m (weil-descent-ghs), equal in G2 (independent), literature and G6",
    "aut_class_size": "size of the rho equivalence class natively available on the curve: 262 = <-1,tau> on E0, 2 = <-1> on the floor (rho-endomorphisms; Aut = {+-1} everywhere)",
    "intrinsic_rho_log2": "log2 sqrt(pi*N/(2*class size)) ideal parallel-rho iterations on the curve itself; recomputed here, equal (<6e-3) to rho-endomorphisms, transport-263, p-levels, toy-analogue-a, literature, G6",
    "transport_to_E0_ok": "ascending F_q-rational 263-isogeny to E0 built and verified on this curve (13 transport-263 flags incl. planted-scalar, dual psi.phi=-263, Sage/PARI agreement; endomorphism-ring Velu j'=1; toy-analogue-a 3/3 planted relations). 'identity' for E0",
    "transport_cost": "log2 of F_q-multiplication equivalents for one transport (build + 2 point evaluations, I = 8M+130S, S = M), upper figure from transport-263; audits: expected ~15.55, worst case (full rebuild, p~1/263) ~16.19",
    "effective_hardness_log2": "log2 ideal rho iterations of the best known attack (transport-263 effective_log2 = E0 rho + transport); equal (<6e-3) in rho-endomorphisms, toy-analogue-a, literature, G6. Practical BBB09 walk: +0.098 (60.91)",
    "ic_density_z_k16": "z-score of the liftable-x count on the canonical subspace V_16 = span{1..z^15}, Tr(b)=1-corrected null (index-calculus zscores.canon.k16)",
    "notes": "per-curve evidence and caveats, with the sweep that produced them",
}
with open(os.path.join(OUT, "per_curve_hardness.columns.json"), "w") as fh:
    json.dump({"columns": columns, "inputs_sha256": {r: sha(r) for r in INPUTS}}, fh, indent=1)

# ---------------------------------------------------------------- levels table
L = g4["levels"]
lvl_rows = [
    {"level": "1 (crater)", "conductor": "1", "End": "O_K", "class_count": "1", "log2_class_count": "0",
     "explicit_curves": "E0 (given)", "native_rho_log2": f"{recomputed['rho_E0_log2']:.3f}",
     "effective_hardness_log2": f"{recomputed['rho_E0_log2']:.3f}",
     "effective_basis": "parallel rho on <-1,tau> classes (BBB09 walk 60.91)",
     "transport_to_E0": "identity", "construct_one_curve": "given"},
    {"level": "263 (floor)", "conductor": "263", "End": "Z+263 O_K", "class_count": "262", "log2_class_count": f"{math.log2(262):.3f}",
     "explicit_curves": "all 262 (ground_truth)", "native_rho_log2": f"{recomputed['rho_floor_native_log2']:.3f}",
     "effective_hardness_log2": f"{trs['effective_log2']['median']:.3f}",
     "effective_basis": "ascending 263-isogeny (implemented, 262/262 verified) then E0 rho",
     "transport_to_E0": f"<=2^{trs['transport_cost_log2_M_equiv_upper']['max']:.2f} F_q-mult per instance", "construct_one_curve": "seconds (roots of H_D mod 2 or Velu)"},
]
for key, lab_ in (("p", "p"), ("263p", "263p")):
    Lk = L[key]
    lvl_rows.append({
        "level": lab_, "conductor": Lk["conductor"], "End": Lk["end_ring"], "class_count": Lk["class_count"],
        "log2_class_count": f"{float(Lk['log2_class_count']):.3f}",
        "explicit_curves": "none known",
        "native_rho_log2": f"{Lk['native_rho_log2_iterations']:.3f}",
        "effective_hardness_log2": f"[{Lk['effective_log2_interval'][0]:.3f}, {Lk['effective_log2_interval'][1]:.3f}]",
        "effective_basis": "64.33 unless a char-2 dim-2 (l,l)-isogeny algorithm exists (Galbraith 2024 Kani transport, O~(p^1/2)); then 60.81-63.40 for kappa<=100",
        "transport_to_E0": "none implemented; conditional dim-2 Kani models (G4): 2^43.4-2^55.7 F_q-mult per unit per-step constant C (reference settings); dim 8 (Thm 1 as proved) gives >= 71.6",
        "construct_one_curve": "2^64.94 candidates, >= 2^72.97 F_q-mult (>= 2^9.58 E0-rho solves)",
    })
LCOLS = list(lvl_rows[0].keys())
with open(os.path.join(OUT, "hardness_by_level.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=LCOLS)
    w.writeheader()
    for r in lvl_rows:
        w.writerow(r)

# ---------------------------------------------------------------- summary stats for the check file
floor = [r for r in rows if r["label"] != "E0"]
summ = {
    "n_rows": len(rows),
    "order_ok_true": sum(r["order_ok"] == "true" for r in rows),
    "two_part_Z4": sum(r["two_part_structure"] == "Z/4" for r in rows),
    "transport_true_floor": sum(r["transport_to_E0_ok"] == "true" for r in floor),
    "ghs_m_values": sorted({r["ghs_magic_number"] for r in rows}),
    "class_sizes": sorted({r["aut_class_size"] for r in rows}),
    "effective_distinct_4dp": sorted({r["effective_hardness_log2"] for r in rows}),
    "intrinsic_distinct_4dp": sorted({r["intrinsic_rho_log2"] for r in rows}),
    "transport_cost_log2_range_floor": [min(float(r["transport_cost"]) for r in floor), max(float(r["transport_cost"]) for r in floor)],
    "ic_z16_floor_min_max": [min(float(r["ic_density_z_k16"]) for r in floor), max(float(r["ic_density_z_k16"]) for r in floor)],
    "ic_z16_E0": rows[0]["ic_density_z_k16"],
}
with open(os.path.join(OUT, "merge_check.json"), "w") as fh:
    json.dump({"missing_values": missing, "n_disagreements": len(disagree), "disagreements": disagree,
               "summary": summ, "recomputed_constants": recomputed,
               "inputs_sha256": {r: sha(r) for r in INPUTS}}, fh, indent=1)

print(json.dumps({"missing": missing, "n_disagreements": len(disagree), "summary": summ,
                  "recomputed": {k_: v for k_, v in recomputed.items() if k_ not in ("h",)}}, indent=1))
if disagree:
    print(json.dumps(disagree[:20], indent=1))
