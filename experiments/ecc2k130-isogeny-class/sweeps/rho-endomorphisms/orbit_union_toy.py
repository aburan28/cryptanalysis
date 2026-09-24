"""(4) Frobenius-orbit union: exact class counts on toy fields F_{2^n}, n prime.
U = disjoint union of E_{b^(2^i)}(F_{2^n}), i = 0..n-1, with sigma:(x,y)->(x^2,y^2) mapping E_{b^(2^i)} -> E_{b^(2^(i+1))}
and negation (x,y)->(x,x+y).  Count orbits of <sigma,-1> on U versus orbits of {+-1} on E_b alone, and compare
with the Koblitz curve E_1, where sigma maps the curve to itself.  Also run the same count on the full 131-curve
A orbit structure abstractly (proof in report)."""
import json, time
from sage.all import GF, EllipticCurve, PolynomialRing

def count(n):
    K = GF(2 ** n, "z")
    z = K.gen()
    res = {"n": n}
    # --- floor-like curve: b with F_2(b) = F_{2^n}
    b = z
    curves = [EllipticCurve(K, [1, 0, 0, 0, b ** (2 ** i)]) for i in range(n)]
    js = set(E.j_invariant() for E in curves)
    res["distinct_j_in_orbit"] = len(js)
    pts0 = [P for P in curves[0].points() if not P.is_zero()]
    # union-find over U \ {O_i}; node = (i, x, y)
    parent = {}
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    def union(a, c):
        ra, rc = find(a), find(c)
        if ra != rc:
            parent[ra] = rc
    nodes = []
    for i in range(n):
        for P in curves[i].points():
            if P.is_zero():
                continue
            node = (i, P[0], P[1])
            parent[node] = node
            nodes.append(node)
    for (i, x, y) in nodes:
        union((i, x, y), ((i + 1) % n, x ** 2, y ** 2))       # sigma
        union((i, x, y), (i, x, x + y))                      # negation
    roots = set(find(a) for a in nodes)
    # classes of E_b alone under +-1
    cls_Eb = set()
    for P in pts0:
        cls_Eb.add(min((P[0], P[1]), (P[0], P[0] + P[1])))
    res["#E_b(F_q)"] = int(curves[0].cardinality())
    res["#U_minus_identities"] = len(nodes)
    res["classes_in_U_under_<sigma,-1>"] = len(roots)
    res["classes_in_E_b_under_+-1"] = len(cls_Eb)
    res["equal"] = len(roots) == len(cls_Eb)
    # max orbit intersection with E_b
    inter = {}
    for (i, x, y) in nodes:
        if i == 0:
            r = find((i, x, y)); inter[r] = inter.get(r, 0) + 1
    res["max_points_of_E_b_in_one_U_class"] = max(inter.values())
    # --- Koblitz curve E_1 (sigma is an endomorphism)
    Ek = EllipticCurve(K, [1, 0, 0, 0, 1])
    parent.clear()
    kn = []
    for P in Ek.points():
        if P.is_zero():
            continue
        node = (P[0], P[1]); parent[node] = node; kn.append(node)
    for (x, y) in kn:
        union((x, y), (x ** 2, y ** 2)); union((x, y), (x, x + y))
    rk = set(find(a) for a in kn)
    res["#E_1(F_q)"] = int(Ek.cardinality())
    res["koblitz_classes_under_<sigma,-1>"] = len(rk)
    res["koblitz_(#E-1)/(2n)"] = (int(Ek.cardinality()) - 1) / (2 * n)
    return res

out = []
for n in (11, 13, 17):
    t0 = time.time()
    r = count(n); r["seconds"] = round(time.time() - t0, 1)
    print(r, flush=True); out.append(r)
json.dump(out, open("orbit_union_toy.json", "w"), indent=1, default=str)
