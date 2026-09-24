# Independent horizontal l-isogeny graphs on the 262 floor curves for l in {11,23,29,37,43,53}:
#   (1) modular polynomial route: for each floor j, roots of Phi_l(j, Y) mod 2 in F_q -> neighbour labels
#   (2) class-group route: dlog of the l-prime form w.r.t. the 2-prime form in Cl(-7*263^2)
# Output raw/c03_horizontal_graph.json; comparison with Codex's run-10 horizontal-graph.json is in c04.
import json, time
from pathlib import Path
from sage.all import GF, PolynomialRing, Integer, ZZ, pari, kronecker, BinaryQF, gcd

W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
GT = json.loads(Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json").read_text())
R = PolynomialRing(GF(2), "z"); z = R.gen()
K = GF(2**131, name="z", modulus=z**131 + z**13 + z**2 + z + 1)
lab_of = {}; j_of = {}
for c in GT["curves"]:
    j = K.from_integer(int(c["j_int"])); lab_of[j] = c["label"]; j_of[c["label"]] = j
floor = [c["label"] for c in GT["curves"] if c["label"] != "E0"]
out = {"script": "c03_horizontal_graph.py", "ells": {}, "classgroup": {}}
D = -7 * 263**2
PK = PolynomialRing(K, "Y")
for l in [11, 23, 29, 37, 43, 53]:
    t0 = time.time()
    assert kronecker(D, l) == 1
    Phi = pari(f"polmodular({l})")           # integer Phi_l(x, y), variables x, y
    # reduce mod 2 -> dict of (i,j) -> 1
    coeffs = {}
    polx = Phi  # polynomial in x with coefficients polynomials in y
    degx = int(pari.poldegree(polx, "x"))
    for i in range(degx + 1):
        cy = pari.polcoef(polx, i, "x")
        degy = int(pari.poldegree(cy, "y")) if cy != 0 else -1
        for jj in range(degy + 1):
            c = Integer(pari.polcoef(cy, jj, "y"))
            if c % 2: coeffs[(i, jj)] = 1
    nbrs = {}; nroots = {}
    for lab in floor + ["E0"]:
        j1 = j_of[lab]
        pw = [K(1)]
        for _ in range(degx): pw.append(pw[-1] * j1)
        cy = [K(0)] * (l + 2)
        for (i, jj) in coeffs: cy[jj] += pw[i]
        f = PK(cy)
        rts = f.roots()
        nroots[lab] = [(lab_of.get(r, "NOT_IN_CLASS:" + str(r.to_integer())), int(m)) for r, m in rts]
    out["ells"][str(l)] = {"neighbours": nroots, "seconds": time.time() - t0}
    degs = {}
    for lab in floor:
        d = sum(m for _, m in nroots[lab]); degs[d] = degs.get(d, 0) + 1
    print(l, "roots-with-multiplicity histogram over floor:", degs, "E0:", nroots["E0"], f"{time.time()-t0:.1f}s")

# class group route
Q2 = BinaryQF([2, 1, (1 - D) // 8])
assert Q2.discriminant() == D
def prime_form(l):
    for b in range(-l + 1, l + 1):
        if (b * b - D) % (4 * l) == 0:
            return BinaryQF([l, b, (b * b - D) // (4 * l)])
powers = [BinaryQF([1, 1, (1 - D) // 4])]
for k in range(1, 263):
    powers.append((powers[-1] * Q2).reduced_form())
ord2 = next(k for k in range(1, 263) if powers[k] == powers[0])
out["classgroup"]["h"] = int(pari(f"qfbclassno({D})"))
out["classgroup"]["order_of_prime_form_2"] = ord2
out["classgroup"]["class_group_structure_pari"] = str(pari(f"quadclassunit({D}).cyc"))
for l in [11, 23, 29, 37, 43, 53]:
    F = prime_form(l).reduced_form()
    Finv = BinaryQF([F[0], -F[1], F[2]]).reduced_form()
    e = [k for k in range(ord2) if powers[k] == F]
    einv = [k for k in range(ord2) if powers[k] == Finv]
    # order of F
    G = F; o = 1
    while G != powers[0]:
        G = (G * F).reduced_form(); o += 1
    out["classgroup"][str(l)] = {"prime_form": str(list(F)), "order": o,
                                 "dlog_base_2form": e, "dlog_inverse": einv,
                                 "in_subgroup_generated_by_2form": bool(e)}
    print("l", l, "order", o, "dlog", e, einv)
(W / "raw" / "c03_horizontal_graph.json").write_text(json.dumps(out, indent=1))
