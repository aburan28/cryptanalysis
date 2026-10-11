"""Fix every control object once (deterministic seeds) and write controls.json.

  * 10 dense random b with Tr(b) = 1         (random.Random(20260924).getrandbits(131))
  * 10 sparse b with Tr(b) = 1 from a fixed candidate list (Hamming weight <= 3)
  * the review's b = z (Tr(b) = 0, 2-part of order 4096; kept as a flagged extra)
  * 5 random 6-dim bases (seed 20260924); V_k^(s) = span of the first k vectors
  * 3 dense scale constants c (seed 20260924+2):  c * V_k
  * 3 dense w for E0 power-basis subspaces span{1, w, .., w^(k-1)}  (seed 20260924+3)
All random curves are point-counted (PARI SEA), and checked to lie outside the ECC2K-130
isogeny class (order != 4N and != q+1+t) and not to have a class j-invariant.
"""
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import g5lib as L  # noqa: E402

E = L.ecc2k
class_j = {int(r["j_int"]) for r in E.RECORDS.values()}
z = L.ZGEN


def curve_rec(label, b, kind, note=""):
    C = L.CurveCtx(label, b)
    j = L.enc(1 / b)
    rec = {"label": label, "kind": kind, "b_int": str(L.enc(b)), "trace_b": L.ftrace(b),
           "hamming_weight_b": bin(L.enc(b)).count("1"), "order": str(C.order),
           "order_mod_8": C.order % 8, "odd_part_is_odd": C.two_part_is_z4,
           "in_class_by_order": C.order in (E.CARD, E.TWIST_CARD), "j_in_class": j in class_j,
           "note": note}
    # sanity: random point has order dividing the order
    P = C.E.random_point()
    assert (C.order * P).is_zero()
    return rec


t0 = time.time()
out = {"seed": 20260924, "curves": [], "random_bases": [], "scale_constants": [], "power_w": []}
rng = random.Random(20260924)
dense = []
while len(dense) < 10:
    u = L.dec(rng.getrandbits(131))
    if u != 0 and L.ftrace(u) == 1 and bin(L.enc(u)).count("1") > 40:
        dense.append(u)
for i, b in enumerate(dense):
    out["curves"].append(curve_rec(f"RD{i:02d}", b, "dense"))

cands = [("1+z", 1 + z), ("1+z^2", 1 + z**2), ("1+z^13", 1 + z**13), ("1+z^3", 1 + z**3),
         ("1+z^5", 1 + z**5), ("z^129", z**129), ("z^129+z", z**129 + z),
         ("z^129+z^2", z**129 + z**2), ("z^129+z^13", z**129 + z**13), ("z^129+z^3", z**129 + z**3),
         ("z", z), ("z^2", z**2), ("z^13", z**13), ("z^3", z**3)]
# (Tr(z^i) = 1 only for i in {0, 129} among 0 <= i < 131, so a sparse b with Tr(b) = 1 either
#  contains the constant 1 or the monomial z^129; five of each are used.)
cand_info = [{"name": n, "b_int": str(L.enc(b)), "trace": L.ftrace(b)} for n, b in cands]
out["sparse_candidates"] = cand_info
sparse = [(n, b) for n, b in cands if L.ftrace(b) == 1 and b != 1][:10]
assert [n for n, _ in sparse] == [n for n, _ in cands[:10]]
assert len(sparse) == 10
for i, (n, b) in enumerate(sparse):
    out["curves"].append(curve_rec(f"RS{i:02d}", b, "sparse", note=f"b = {n}"))
for n, b, lab in (("z", z, "RZz"),):
    if not any(c["b_int"] == str(L.enc(b)) for c in out["curves"]):
        out["curves"].append(curve_rec(lab, b, "review_check", note=f"b = {n} (review's example)"))
    else:
        out.setdefault("review_check_already_included", []).append(n)

for s in range(5):
    B = L.random_basis(6, rng)
    assert L.is_independent(B)
    out["random_bases"].append([str(L.enc(u)) for u in B])
rng2 = random.Random(20260924 + 2)
while len(out["scale_constants"]) < 3:
    c = rng2.getrandbits(131)
    if bin(c).count("1") > 40:
        out["scale_constants"].append(str(c))
rng3 = random.Random(20260924 + 3)
while len(out["power_w"]) < 3:
    w = L.dec(rng3.getrandbits(131))
    if bin(L.enc(w)).count("1") > 40 and L.is_independent([w**j for j in range(6)]):
        out["power_w"].append(str(L.enc(w)))
out["seconds"] = time.time() - t0
(HERE.parent / "controls.json").write_text(json.dumps(out, indent=1))
for c in out["curves"]:
    print(c["label"], c["kind"], c["note"], "Tr", c["trace_b"], "wt", c["hamming_weight_b"],
          "ord%8", c["order_mod_8"], "inclass", c["in_class_by_order"], c["j_in_class"])
print("sparse candidates:", [(c["name"], c["trace"]) for c in cand_info])
