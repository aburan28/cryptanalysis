#!/usr/bin/env python3
"""Fit cpu(polmodular(L, 0, Mod(1,2))) ~ c * L^alpha on the measured points (L >= 150) and extrapolate (log2 seconds)."""
import json, math
d = json.load(open('/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/raw/levelcost.json'))
pts = [(math.log(x['L']), math.log(x['cpu_j1'])) for x in d['polmodular'] if x['L'] >= 150]
xs = [a for a, b in pts]; ys = [b for a, b in pts]; mx = sum(xs) / len(xs); my = sum(ys) / len(ys)
alpha = sum((a - mx) * (b - my) for a, b in pts) / sum((a - mx) ** 2 for a in xs); c = math.exp(my - alpha * mx)
out = dict(points=[(x['L'], x['cpu_j1']) for x in d['polmodular']], fit_from_L_ge_150=dict(alpha=alpha, c=c),
           log2_cpu_seconds_extrapolated={str(L): math.log2(c) + alpha * math.log2(L) for L in [1721, 77761, 146505763881528721, 513035439254495356843057]},
           note='PARI polmodular computes the full Phi_L (cubic-type growth); even an L^2 evaluation algorithm gives 2^114 operations at L = p')
json.dump(out, open('/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/raw/levelfit.json', 'w'), indent=1)
print(json.dumps(out, indent=1))
