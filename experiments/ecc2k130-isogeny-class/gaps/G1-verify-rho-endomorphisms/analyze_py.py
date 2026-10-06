import json, math
from gmpy2 import mpz, powmod
d = json.load(open('sweep_py.json'))
N = mpz(d['N'])
tot = {'O263': 0, 'OK': 0}
best = {}
rows = []
for dd, e in d['per_d'].items():
    D = int(dd)
    for m in ('O263', 'OK'):
        tot[m] += e[m]['count']
        if D >= 3:
            if m not in best or int(e[m]['min']) < int(best[m][1]['min']):
                best[m] = (D, e[m])
    rows.append((D, e['O263']['log2_min'], e['OK']['log2_min'], e['OK']['log2_nontau_min'], e['O263']['count']))
print('counts', tot)
for m in best:
    D, e = best[m]
    print(m, 'global min over d>=3: d=', D, 'log2=', e['log2_min'], 'arg', e['argmin_xy'], 'k', e['argmin_k'], 'ties', e['ties_at_min'])
# second-best d for O263
ls = sorted((e['O263']['log2_min'], int(dd)) for dd, e in d['per_d'].items() if int(dd) >= 3)
print('O263 5 smallest per-d minima', ls[:5])
lk = sorted((e['OK']['log2_nontau_min'], int(dd), e['OK']['nontau_argmin_xy']) for dd, e in d['per_d'].items())
print('OK nontau 5 smallest per-d', lk[:5])
below = []
for dd, e in d['per_d'].items():
    for k, x, y, v in e['OK']['below2_100']:
        below.append((int(dd), k, int(x), int(y), int(v)))
print('OK elements below 2^100 (coset minima):', len(below))
# check they are +-tau^j
a, b = 1, 0
tp = {}
for j in range(0, 200):
    tp[(a, b)] = j; tp[(-a, -b)] = -j - 1000
    a, b = -2*b, a - b
js = sorted(tp.get((x, y), None) for (_, _, x, y, _) in below)
print('all tau powers?', all(j is not None for j in js))
pos = sorted(j for j in js if j is not None and j >= 0); neg = sorted(-(j+1000) for j in js if j is not None and j < 0)
print('+tau^j j:', pos[0], '..', pos[-1], len(pos), ' -tau^j j:', neg[0], '..', neg[-1], len(neg))
print('orders of below:', sorted(set(x[0] for x in below)))
