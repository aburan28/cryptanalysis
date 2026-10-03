# Check Codex's S_3 claims: (1) S_3(x1,x2,x3) = (x1x2+x1x3+x2x3)^2 + x1x2x3 + b vanishes on P1+P2+P3=O
# for all 263 ECC2K-130-class curves (random points), (2) Codex's F_8 control counts: 56 models, 56 triples,
# 3136 combos, 416 zeros, 208 with rational collinear lift, 208 without.
import json, itertools
from pathlib import Path
from sage.all import GF, PolynomialRing, EllipticCurve, set_random_seed
set_random_seed(7)
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
GT = json.loads(Path("/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json").read_text())
R = PolynomialRing(GF(2), "z"); z = R.gen()
K = GF(2**131, name="z", modulus=z**131 + z**13 + z**2 + z + 1)
res = {"s3_on_all_263": {}}
okall = True
for c in GT["curves"]:
    b = K.from_integer(int(c["b_int"])); E = EllipticCurve(K, [1, int(c["a2"]), 0, 0, b])
    ok = True
    for _ in range(3):
        P1 = E.random_point(); P2 = E.random_point(); P3 = -(P1 + P2)
        if P1.is_zero() or P2.is_zero() or P3.is_zero(): continue
        x1, x2, x3 = P1[0], P2[0], P3[0]
        ok &= ((x1*x2 + x1*x3 + x2*x3)**2 + x1*x2*x3 + b == 0)
    res["s3_on_all_263"][c["label"]] = bool(ok); okall &= ok
res["s3_all_ok"] = bool(okall)
# F_8 control
F8 = GF(8, "g")
els = list(F8)
models = [(a, b) for a in els for b in els if b != 0]
triples = list(itertools.combinations(els, 3))
zeros = lift = nolift = agree = 0
for a, b in models:
    E = EllipticCurve(F8, [1, a, 0, 0, b])
    pts = [P for P in E.points() if not P.is_zero()]
    for (x1, x2, x3) in triples:
        s = (x1*x2 + x1*x3 + x2*x3)**2 + x1*x2*x3 + b
        if s != 0: continue
        zeros += 1
        # rational collinear lift: exist affine points P1,P2,P3 with these x, P1+P2+P3 = O
        P1s = [P for P in pts if P[0] == x1]; P2s = [P for P in pts if P[0] == x2]; P3s = [P for P in pts if P[0] == x3]
        L = any((P1 + P2 + P3).is_zero() for P1 in P1s for P2 in P2s for P3 in P3s)
        # trace criterion: Tr(a + s1) == 0
        s1 = x1 + x2 + x3
        crit = ((a + s1).trace() == 0)
        agree += (L == crit)
        if L: lift += 1
        else: nolift += 1
res["F8"] = {"models": len(models), "triples_per_model": len(triples), "combos": len(models)*len(triples),
             "zeros": zeros, "with_rational_lift": lift, "without": nolift, "trace_criterion_agrees": agree,
             "codex": {"models": 56, "triples": 56, "combos": 3136, "zeros": 416, "lift": 208, "nolift": 208}}
print(json.dumps(res["F8"], indent=1), "S3 all ok:", okall)
(W / "raw" / "c06_s3_identity.json").write_text(json.dumps(res, indent=1))
