# Geometric re-verification of Codex's explicit isogeny artifacts:
#  A. run-04 velu-line-enumeration.json codomain inventory (264 lines) vs ground truth j's
#  B. run-04 {A090,B021,B067}-explicit-map.json: kernel polynomial vs an INDEPENDENT enumeration of the
#     264 263-lines (from E0'(F_q)[263] on the quadratic twist; x-coordinates are shared with E0),
#     Sage isogeny from the kernel polynomial, codomain j, transport of the public challenge P,Q
#  C. run-10 l11-generator-maps.json: degree-5 kernel polynomials vs factors of the 11-division polynomial,
#     transported points, and the run-11 CM scalars beta/gamma evaluated geometrically on a point of order N
#  D. 11-torsion field degree (Codex: F_(2^1310)) and v_11(#E(F_(q^10))) (Codex: 2)
import json, time, sys, hashlib
from pathlib import Path
from sage.all import (GF, PolynomialRing, EllipticCurve, Integer, ZZ, set_random_seed, prod, Mod, lcm)

set_random_seed(424242)
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
CI = W / "codex_inputs/curve-comparison"
GT = json.loads(Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json").read_text())
gt = {c["label"]: c for c in GT["curves"]}
R = PolynomialRing(GF(2), "z"); z = R.gen()
K = GF(2**131, name="z", modulus=z**131 + z**13 + z**2 + z + 1)
KX = PolynomialRing(K, "X"); X = KX.gen()
q = Integer(2)**131
t1 = -1; s = [Integer(2), Integer(t1)]
for i in range(2, 132): s.append(t1*s[-1] - 2*s[-2])
t = s[131]; N = (q + 1 - t) // 4
dec = lambda n: K.from_integer(int(n))
enc = lambda u: str(u.to_integer())
def curve(lab):
    return EllipticCurve(K, [1, int(gt[lab]["a2"]), 0, 0, dec(gt[lab]["b_int"])])
out = {"script": "c07_explicit_maps.py", "A_codomain_inventory": {}, "B_degree263": {}, "C_degree11": {}, "D_l11_field": {}}
def log(*a):
    print(*a, flush=True)

# public challenge points (repo suite/docs/ic/params/ecc2k130-fixed.json, polynomial basis)
E0 = curve("E0")
P0 = E0(dec(0x051C99BFA6F18DE467C80C23B98C7994AA), dec(0x042EA2D112ECEC71FCF7E000D7EFC978BD))
Q0 = E0(dec(0x06C997F3E7F2C66A4A5D2FDA13756A37B1), dec(0x04A38D11829D32D347BD0C0F584D546E9A))
assert (N*P0).is_zero() and (N*Q0).is_zero() and not P0.is_zero() and not Q0.is_zero()

# ---------------- A. codomain inventory
vl = json.loads((CI / "run-04-isogeny/velu-line-enumeration.json").read_text())
inv = vl["codomain_inventory"]
labs = [r["curve_id"] for r in inv]
nE0 = sum(1 for r in inv if r["j_integer"] == "1")
floor_rows = [r for r in inv if r["j_integer"] != "1"]
jmatch = sum(1 for r in floor_rows if r["curve_id"] in gt and gt[r["curve_id"]]["j_int"] == r["j_integer"])
out["A_codomain_inventory"] = {
    "lines": len(inv), "rows_with_j_1": nE0, "labels_of_j1_rows": [r["curve_id"] for r in inv if r["j_integer"] == "1"],
    "floor_rows": len(floor_rows), "distinct_floor_labels": len(set(r["curve_id"] for r in floor_rows)),
    "floor_rows_label_and_j_match_gt": jmatch,
    "all_262_gt_floor_labels_present": set(r["curve_id"] for r in floor_rows) == set(l for l in gt if l != "E0")}
log("A:", out["A_codomain_inventory"])

# ---------------- B. independent 264-line enumeration on the twist
t0 = time.time()
E0t = EllipticCurve(K, [1, 1, 0, 0, 1])
cof = (q + 1 + t) // 263**2
assert cof * 263**2 == q + 1 + t
def rand263():
    while True:
        P = cof * E0t.random_point()
        if not P.is_zero():
            assert (263*P).is_zero()
            return P
P1 = rand263()
mult1 = [P1.parent()(0)]
for i in range(262): mult1.append(mult1[-1] + P1)
xs1 = set(Pt[0] for Pt in mult1[1:])
while True:
    P2 = rand263()
    if P2[0] not in xs1: break
def kernel_poly(G):
    xs = []; Pt = G
    for k in range(131):
        xs.append(Pt[0]); Pt = Pt + G
    assert len(set(xs)) == 131
    return prod(X - x for x in xs)
lines = {"inf": kernel_poly(P1)}
Gi = P2
for i in range(263):
    lines[str(i)] = kernel_poly(Gi); Gi = Gi + P1
assert len(set(tuple(h.list()) for h in lines.values())) == 264
out["B_degree263"]["enumeration_seconds"] = time.time() - t0
log("B: 264 lines enumerated", time.time() - t0)
by_coeffs = {tuple(enc(c) for c in h.list()): lid for lid, h in lines.items()}
for lab in ["A090", "B021", "B067"]:
    t0 = time.time()
    m = json.loads((CI / f"run-04-isogeny/{lab}-explicit-map.json").read_text())
    hc = [dec(c) for c in m["kernel_polynomial_coefficients"]]
    h = KX(hc)
    rec = {"codex_line_id": m["line_id"], "codex_kernel_degree": m["kernel_polynomial_degree"],
           "codex_kernel_sha256": m["kernel_polynomial_sha256"],
           "codex_target_j_equals_gt": m["target_j_integer"] == gt[lab]["j_int"],
           "codex_target_b_equals_gt": m["target_b_integer"] == gt[lab]["b_int"]}
    rec["kernel_poly_matches_independent_line"] = by_coeffs.get(tuple(m["kernel_polynomial_coefficients"]))
    # sha256 guesses for the kernel poly serialisation (informational)
    ser = json.dumps(m["kernel_polynomial_coefficients"]).encode()
    rec["sha256_of_json_coeff_list"] = hashlib.sha256(ser).hexdigest()
    rec["sha256_newline_joined"] = hashlib.sha256("\n".join(m["kernel_polynomial_coefficients"]).encode()).hexdigest()
    phi = E0.isogeny(h)
    rec["isogeny_degree"] = int(phi.degree())
    Ec = phi.codomain()
    rec["codomain_j_equals_gt"] = enc(Ec.j_invariant()) == gt[lab]["j_int"]
    Et = curve(lab)
    isos = Ec.isomorphisms(Et)
    rec["n_isomorphisms_to_gt_model"] = len(isos)
    ok = {}
    for nm, P, key in [("P", P0, "mapped_P"), ("Q", Q0, "mapped_Q")]:
        cx, cy = dec(m[key]["x"]), dec(m[key]["y"])
        Cpt = Et(cx, cy)
        imgs = [iso(phi(P)) for iso in isos]
        ok[nm] = {"codex_point_on_gt_curve": True, "codex_point_killed_by_N": bool((N*Cpt).is_zero()),
                  "x_matches": any(I[0] == cx for I in imgs), "point_matches_some_iso": any(I == Cpt for I in imgs)}
    rec["transport"] = ok
    rec["seconds"] = time.time() - t0
    out["B_degree263"][lab] = rec
    log("B:", lab, rec)

# ---------------- C. degree-11 generators, beta/gamma
l11 = json.loads((CI / "run-10-horizontal-isogenies/l11-generator-maps.json").read_text())
cm = json.loads((CI / "run-11-horizontal-core-fringe/cm-alignment.json").read_text())
beta = Integer(cm["orbits"][0]["beta_plus_scalar_mod_N"]); gamma = Integer(cm["orbits"][0]["gamma_minus_scalar_mod_N"])
th = Integer(cm["orbits"][0]["unique_calibrated_match"]["omega_root"]); thc = (1 - th) % N
inv216 = Integer(Mod(2**16, N)**-1)
cands = {"beta": beta, "-beta": (-beta) % N, "gamma": gamma, "-gamma": (-gamma) % N,
         "conj_beta=(774+theta)/2^16": (774 + th) * inv216 % N, "-conj_beta": (-(774 + th) * inv216) % N}
def frob(Pt, e, Etgt):
    return Etgt(Pt[0]**(2**e), Pt[1]**(2**e))
src_of = {"A": ("A000", "A090", 41), "B": ("B000", "B021", 110)}
for o in l11["orbits"]:
    O = o["orbit"]; src, via, e = src_of[O]
    t0 = time.time()
    Es = curve(src)
    # P, Q on the source chart derived from the run-04 A090 / B021 images by relative Frobenius (via -> src)
    m = json.loads((CI / f"run-04-isogeny/{via}-explicit-map.json").read_text())
    Ps = frob(curve(via)(dec(m["mapped_P"]["x"]), dec(m["mapped_P"]["y"])), e, Es)
    Qs = frob(curve(via)(dec(m["mapped_Q"]["x"]), dec(m["mapped_Q"]["y"])), e, Es)
    # independent kernel polynomials: degree-5 factors of the 11-division polynomial
    psi = Es.division_polynomial(11)
    t1_ = time.time()
    fac = psi.factor()
    degs = sorted(int(g.degree()) for g, _ in fac)
    deg5 = [g for g, _ in fac if g.degree() == 5]
    crec = {"division_poly_degree": int(psi.degree()), "factor_degrees": degs, "factor_seconds": time.time() - t1_}
    maps = {}
    for g in o["generator_maps"]:
        tgt = g["target_curve"]; shift = g["target_shift"]
        hc = psi.parent()([dec(c) for c in g["kernel_polynomial_coefficients"]])
        r = {"codex_kernel_is_monic_deg5": hc.degree() == 5 and hc.is_monic(),
             "codex_kernel_equals_a_division_poly_factor": any(hc == f for f in deg5),
             "codex_kernel_divides_psi11": (psi % hc) == 0}
        phi = Es.isogeny(hc)
        Ec = phi.codomain(); Et = curve(tgt)
        r["codomain_j_equals_gt_" + tgt] = Ec.j_invariant() == Et.j_invariant()
        isos = Ec.isomorphisms(Et)
        for nm, P, key in [("P", Ps, "mapped_P"), ("Q", Qs, "mapped_Q")]:
            Cpt = Et(dec(g[key]["x"]), dec(g[key]["y"]))
            imgs = [iso(phi(P)) for iso in isos]
            r[f"{nm}_x_matches"] = any(I[0] == Cpt[0] for I in imgs)
            r[f"{nm}_point_matches_some_iso"] = any(I == Cpt for I in imgs)
            r[f"{nm}_codex_killed_by_N"] = bool((N*Cpt).is_zero())
        # CM scalar: back to the source chart by relative Frobenius (tgt -> src : exponent 131 - shift)
        Rr = None
        while Rr is None or Rr.is_zero():
            Rr = 4 * Es.random_point()
        assert (N*Rr).is_zero()
        found = {}
        for k_iso, iso in enumerate(isos):
            img = frob(iso(phi(Rr)), (131 - shift) % 131, Es)
            found[f"iso{k_iso}"] = [nm for nm, c in cands.items() if img == c * Rr]
        r["scalar_on_random_order_N_point_by_iso"] = found
        # same with Codex's own transported P: which candidate matches the Codex-normalised image?
        Cpt = Et(dec(g["mapped_P"]["x"]), dec(g["mapped_P"]["y"]))
        imgP = frob(Cpt, (131 - shift) % 131, Es)
        r["scalar_on_codex_normalised_P"] = [nm for nm, c in cands.items() if imgP == c * Ps]
        maps[tgt] = r
        log("C:", O, tgt, r)
    # two rational lines only?
    crec["n_degree5_factors"] = len(deg5)
    ncod = []
    for f5 in deg5:
        try:
            jj = Es.isogeny(f5).codomain().j_invariant()
            ncod.append(next((l for l in gt if gt[l]["j_int"] == enc(jj)), "not-in-class"))
        except Exception as ex:
            ncod.append("not-kernel:" + type(ex).__name__)
    crec["degree5_factor_codomains"] = ncod
    crec["maps"] = maps; crec["seconds"] = time.time() - t0
    out["C_degree11"][O] = crec
    log("C:", O, {k: v for k, v in crec.items() if k != "maps"})

# ---------------- D. 11-torsion field
tt = [Integer(2), t]            # traces of pi^k
for k in range(2, 11): tt.append(t*tt[-1] - q*tt[-2])
card10 = q**10 + 1 - tt[10]
F11 = GF(11); Rx = PolynomialRing(F11, "x")
cp = Rx([q % 11, -(t % 11), 1])
rts = cp.roots(multiplicities=False)
out["D_l11_field"] = {"charpoly_pi_mod_11": str(cp.factor()), "eigenvalue_orders": [int(Mod(r, 11).multiplicative_order()) for r in rts],
                      "E11_field_degree_over_Fq": int(lcm([Mod(r, 11).multiplicative_order() for r in rts])) if len(rts) == 2 else None,
                      "v11_card_Fq10": int(ZZ(card10).valuation(11)),
                      "codex_torsion_field_degree_over_F2": l11["torsion_field_degree_over_F2"],
                      "codex_v11": l11["extension_group_order_11_valuation"]}
log("D:", out["D_l11_field"])
(W / "raw" / "c07_explicit_maps.json").write_text(json.dumps(out, indent=1, default=str))
log("done")
