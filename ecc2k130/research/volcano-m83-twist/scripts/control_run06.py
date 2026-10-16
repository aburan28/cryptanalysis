"""Positive control: f83x must reproduce ../volcano-m83 run06 yields.json exactly
(a2 = 0, Z/4 tags, polynomial basis, k = 8, 9, 10, natural and equal-cardinality)."""
import json
import twist

y = json.loads((twist.PARENT / 'outputs' / 'run06-four-summand' / 'yields.json').read_text())
inv = {r['curve_id']: r for r in twist.load_inventory()}
out, ok = {}, True
for k, d in y['k'].items():
    k = int(k); size = d['equal_cardinality']['size']; out[k] = {}
    for cid in y['curves']:
        rows, _ = twist.tags(0, inv[cid]['b'], twist.polynomial_basis(k))
        tag = dict(rows)
        nat = twist.count(0, [t for _, t in rows])
        mat = twist.count(0, [tag[m] for m in twist.sha_order(list(tag))[:size]])
        exp_n, exp_nat = d['natural'][cid]['x_count'], d['natural'][cid]['eligible']
        exp_mat = d['equal_cardinality']['eligible'][cid]
        match = (len(rows), nat, mat) == (exp_n, exp_nat, exp_mat)
        ok &= match
        out[k][cid] = dict(x_count=len(rows), eligible=nat, matched=mat, expected=[exp_n, exp_nat, exp_mat], match=match)
        print(k, cid, out[k][cid], flush=True)
twist.OUT.mkdir(exist_ok=True)
(twist.OUT / 'control-run06.json').write_text(json.dumps({'all_match': ok, 'rows': out}, indent=1) + '\n')
print('ALL MATCH' if ok else 'MISMATCH')
raise SystemExit(0 if ok else 1)
