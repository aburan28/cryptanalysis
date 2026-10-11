"""Independent (Sage) check of every log the C solver returned: k_found * P == Q on the curve
where the instance was planted (for transported instances: on the floor curve, with the
original floor points), and k_found == planted k.

usage: sage -python verify.py <family>
Writes raw/<family>/verify.json
"""
import sys, json, os, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from toylib import *
from sage.all import EllipticCurve, Integer

fam = sys.argv[1]
F = load_family(fam)
meta = F['meta']
K, tail = make_field(meta['n'], meta['modulus_tail'])
N = Integer(meta['N'])
inst = json.load(open(os.path.join(WORK, 'raw', fam, 'instances.json')))
curves = {}


def curve(lab):
    if lab not in curves:
        c = F['curves'][lab]
        curves[lab] = EllipticCurve(K, [1, c['a2'], 0, 0, int2fe(K, c['b_int'])])
    return curves[lab]


outd = os.path.join(WORK, 'raw', fam, 'out')
res = {}
tot = dict(rows=0, sage_verified=0, matches_planted=0, c_verified_flag=0)
for fn in sorted(os.listdir(outd)):
    if not fn.endswith('.tsv'):
        continue
    cfg = fn[:-4]
    r = dict(rows=0, sage_verified=0, matches_planted=0, c_verified_flag=0, failures=[])
    with open(os.path.join(outd, fn)) as fh:
        for row in csv.DictReader(fh, delimiter='\t'):
            iid = row['id']
            base = iid[:-3] if iid.endswith(':tr') else iid
            rec = inst[base]
            E = curve(rec['curve'])
            P = E(int2fe(K, rec['P'][0]), int2fe(K, rec['P'][1]))
            Q = E(int2fe(K, rec['Q'][0]), int2fe(K, rec['Q'][1]))
            kf = Integer(row['k_found'])
            ok = (kf * P == Q)
            m = (kf == Integer(rec['k']) % N)
            r['rows'] += 1
            r['sage_verified'] += ok
            r['matches_planted'] += m
            r['c_verified_flag'] += int(row['verified'])
            if not (ok and m):
                r['failures'].append(iid)
    res[cfg] = r
    for kk in tot:
        tot[kk] += r[kk]
    print(fam, cfg, {k: v for k, v in r.items() if k != 'failures'}, 'failures:', r['failures'][:5], flush=True)
json.dump(dict(family=fam, total=tot, per_config=res), open(os.path.join(WORK, 'raw', fam, 'verify.json'), 'w'), indent=1)
print('TOTAL', fam, tot)
