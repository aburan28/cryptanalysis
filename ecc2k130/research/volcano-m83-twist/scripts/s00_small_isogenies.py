"""Exact rational l-isogenies of the two Koblitz curves over GF(2^83), l in {3,5,7,11,13}."""
import json, random, sys, time
from gf2m import *
CURVES = {
  "a0_81bit": dict(a2=0, mod=(1<<83)|(1<<45)|(1<<2)|(1<<1)|1, n_sub=2417851639230796216685689, h=4),
  "a1_53bit": dict(a2=1, mod=9671406556917033397649557,   n_sub=8569786107849059,          h=1128547018),
}
rng = random.Random(83)
def doubling_image(F, a6, g, gp):
    """is x(2P) a root of gp whenever x(P) is a root of g?  x(2P) = x^2 + a6/x^2"""
    # gp(x^2 + a6 x^-2) * x^(2 deg) evaluated mod g
    x2 = psqrmod(F, [0, 1], g); ix2 = None
    # compute x^-2 mod g via extended power: x^-1 = x^(2^(n deg)-2) is costly; use gcd-free trick:
    # homogenise: sum c_k (x^4 + a6)^k x^(2(D-k))
    D = len(gp) - 1; num = [a6, 0, 0, 0, 1]; acc = []
    pw = [[1]]
    for k in range(1, D + 1): pw.append(pmod(F, pmul(F, pw[-1], num), g))
    x2p = [[1]]
    for k in range(1, D + 1): x2p.append(pmod(F, pmul(F, x2p[-1], x2), g))
    for k, c in enumerate(gp):
        if c: acc = padd(acc, pscale(F, pmod(F, pmul(F, pw[k], x2p[D - k]), g), c))
    return not acc
out = {}
for name, P in CURVES.items():
    F = Field(83, P["mod"]); E = Curve(F, P["a2"], 1)
    N = P["n_sub"] * P["h"]
    R = E.rand_point(rng); assert E.mul(N, R) is None
    res = {}
    for l in (3, 5, 7, 11, 13):
        t0 = time.time()
        psi = pmonic(F, division_poly(F, 1, l)); assert len(psi) - 1 == (l * l - 1) // 2
        dd, rest = distinct_degree(F, psi, (l - 1) // 2)
        facs = []
        for d, g in dd.items(): facs += equal_degree(F, g, d, rng)
        # group factors into doubling-closed sets of total degree (l-1)/2
        kern = []
        used = set()
        for i, g in enumerate(facs):
            if i in used: continue
            orbit = [i]; cur = i
            while True:
                nxt = next((k for k, gp in enumerate(facs) if len(gp) == len(facs[cur]) and doubling_image(F, 1, facs[cur], gp)), None)
                if nxt is None or nxt in orbit: break
                orbit.append(nxt); cur = nxt
            deg = sum(len(facs[k]) - 1 for k in orbit)
            if deg == (l - 1) // 2 and nxt == i:
                h = [1]
                for k in orbit: h = pmul(F, h, facs[k])
                kern.append(h); used |= set(orbit)
        cods = []
        for h in kern:
            a6p = velu_codomain(F, 1, h); Ep = Curve(F, P["a2"], a6p)
            Rp = Ep.rand_point(rng); okN = Ep.mul(N, Rp) is None
            # image of R lies on codomain?
            X = velu_x(F, h, R[0]); onc = Ep.lift_x(X) is not None
            cods.append(dict(a6_codomain=hex(a6p), j_codomain_is_1=(a6p == 1), order_N_checked=okN, image_x_on_codomain=onc))
        res[l] = dict(rational_factor_degrees=sorted(len(g) - 1 for g in facs), n_kernels=len(kern), codomains=cods, secs=round(time.time() - t0, 1))
        print(name, l, res[l], flush=True)
    out[name] = res
from pathlib import Path
OUT = Path(__file__).resolve().parents[1] / "outputs"; OUT.mkdir(exist_ok=True)
json.dump(out, open(OUT / "s00-small-isogenies.json", "w"), indent=1)
