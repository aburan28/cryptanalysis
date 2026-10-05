import sys; sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import Integer
K, cs = ecc2k.load()
assert len(cs) == 263
# PARI point count on a sample + Frobenius labelling checks
for lab in ["E0", "A000", "A090", "B021", "B067", "B130"]:
    E = cs[lab]
    assert E.cardinality(algorithm="pari") == ecc2k.CARD, lab
    nxt = cs[ecc2k.frobenius_next(lab)]
    assert nxt.j_invariant() == E.j_invariant()**2, lab
# all floor j distinct, not in F_2, and minimal polynomial degree 131
js = [E.j_invariant() for lab, E in cs.items() if lab != "E0"]
assert len(set(js)) == 262
assert all(j.minimal_polynomial().degree() == 131 for j in js[:5] + js[-5:])
# orbit A vs B: A000's minpoly differs from B000's
assert cs["A000"].j_invariant().minimal_polynomial() != cs["B000"].j_invariant().minimal_polynomial()
assert cs["A000"].j_invariant().minimal_polynomial() == cs["A077"].j_invariant().minimal_polynomial()
# tau eigenvalue on E0
E0 = cs["E0"]
P = 4 * E0.random_point()
tauP = E0(P[0]**2, P[1]**2)
assert tauP == ecc2k.TAU_EIGEN * P
print("loader tests OK")
