# Red team 2, script 2: concrete parameters for Galbraith's Kani/MITM representation of the
# ascending p-isogeny E1 -> E0 (E1 on level p), Galbraith 2024 (eprint 2024/924) Thm 1/Thm 2 (h0=1).
# We do NOT build the isogeny; we check that the number-theoretic ingredients exist for this
# class and count the guesses / field degrees that drive the cost.
import json, itertools, math
q = 2^131
tk = [2, -1]
for k in range(2, 132): tk.append(-tk[-1] - 2*tk[-2])
t = tk[131]; N = (q + 1 - t)//4; f = isqrt((t^2 - 4*q)//(-7)); p = f//263
out = {'p': str(p)}
# Elkies primes: split in Q(sqrt(-7)), not dividing 2*7*263*p.
elk = []
for l in primes(3, 4000):
    if l in (7, 263) or kronecker(-7, l) != 1: continue
    R = PolynomialRing(GF(l), 'X'); X = R.gen()
    rts = [r for r, e in (X^2 - t*X + q).roots()]
    assert len(rts) == 2
    ks = [Mod(r, l).multiplicative_order() for r in rts]
    # x-coordinate field: smallest k with r^k = +-1
    kx = []
    for r in rts:
        o = Mod(r, l).multiplicative_order()
        kx.append(o//2 if (o % 2 == 0 and Mod(r, l)^(o//2) == -1) else o)
    elk.append((l, max(ks), max(kx), ks))
out['n_elkies_below_4000'] = len(elk)
out['elkies_first_40'] = [(int(l), int(k), int(kx)) for l, k, kx, _ in elk[:40]]
cheap = sorted(elk, key=lambda e: e[2])
out['elkies_smallest_x_degree_30'] = [(int(l), int(k), int(kx)) for l, k, kx, _ in cheap[:30]]
json.dump(out, open('/Volumes/SSD990/ecdlp-hardness-work/redteam-2/raw/rt2_elkies.json', 'w'), indent=1)
print('Elkies primes < 4000:', len(elk))
print('first 40 (l, eigen-field degree over F_q, x-field degree):', out['elkies_first_40'])
print('smallest x-degree:', out['elkies_smallest_x_degree_30'])
