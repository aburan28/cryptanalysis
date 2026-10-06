"""Receipt audit for the F_(2^83) volcano study, and a SHA-256 manifest of outputs/.

Re-derives the headline claims from the saved receipts with independent code
paths where possible (Sage point arithmetic rather than the native library):

    sage -python audit.py   ->  outputs/audit.json, outputs/SHA256SUMS
"""
import glob
import hashlib
import json
import subprocess
import sys

import m83

OUT = m83.OUT
checks = []


def check(name, ok, detail=None):
    checks.append({'check': name, 'passed': bool(ok), 'detail': detail})
    print(('PASS ' if ok else 'FAIL ') + name + ('' if detail is None else ' :: ' + str(detail)), flush=True)


def jsonl(pattern):
    for path in sorted(glob.glob(str(OUT / pattern))):
        for line in open(path):
            yield json.loads(line)


def main():
    # s00: rerun the stdlib verifier and compare
    fresh = json.loads(subprocess.run([sys.executable, str(m83.HERE / 's00_ring_invariants.py')],
                                      capture_output=True, text=True, check=True).stdout)
    saved = json.loads((OUT / 's00-ring-invariants.json').read_text())
    check('s00 invariants reproduce', fresh == saved)
    # inventory
    inv = json.loads((OUT / 'inventory' / 'inventory.json').read_text())
    curves = m83.load_inventory()
    js = {c['j'] for c in curves if c['curve_id'] != 'E0'}
    check('inventory: 78 orbits x 83 = 6474 distinct j', len(inv['orbits']) == 78 and len(js) == 6474)
    h = hashlib.sha256((OUT / 'inventory' / 'H83-mod2-ascending.txt').read_bytes()).hexdigest()
    check('class polynomial mod 2 hash', h == inv['class_polynomial_mod2_sha256'])
    E = m83.curve(curves[1234]['b'])
    check('sample floor curve order 4 ELL (Sage)', E.cardinality(algorithm='pari') == m83.N)
    # lines
    lines = json.loads((OUT / 'run04-explicit-descent' / 'line-codomains.json').read_text())
    lj = [l['j'] for l in lines['lines']]
    check('6474 kernel lines, distinct codomains equal to the inventory', len(lj) == 6474 and set(lj) == js)
    ok = True
    for l in lines['lines'][:200]:
        v = m83.dec(int(l['trace'], 16))
        ok &= m83.enc(1 / (1 + v + v * v)) == int(l['j'])
    check('Velu j = 1/(1+v+v^2) recomputed for 200 lines', ok)
    # explicit maps
    P, Q = m83.public_points()
    for path in sorted(glob.glob(str(OUT / 'run04-explicit-descent' / '*-explicit-map.json'))):
        mp = json.loads(open(path).read())
        T = m83.curve(int(mp['target_b']))
        mP = T(m83.dec(mp['mapped_P']['x']), m83.dec(mp['mapped_P']['y']))
        mQ = T(m83.dec(mp['mapped_Q']['x']), m83.dec(mp['mapped_Q']['y']))
        coeffs = mp['kernel_polynomial_coefficients']
        hk = hashlib.sha256(json.dumps(coeffs, separators=(',', ':')).encode()).hexdigest()
        inventory_b = {c['curve_id']: c['b'] for c in curves}[mp['curve_id']]
        check('map %s: images on the target, nonzero, killed by ELL; kernel hash; b matches inventory' % mp['curve_id'],
              (m83.ELL * mP).is_zero() and (m83.ELL * mQ).is_zero() and not mP.is_zero() and not mQ.is_zero()
              and hk == mp['kernel_polynomial_sha256'] and int(inventory_b) == int(mp['target_b'])
              and len(coeffs) == 3237)
    # census
    rows = list(jsonl('run01-comparison/yield-census-*.jsonl'))
    check('census rows = 6475 x 5', len({(r['curve_id'], r['k'], r['profile']) for r in rows}) == 6475 * 5)
    check('eligibility formula on every census row', all(r['eligible_formula'] == r['eligible_signed_tuples'] for r in rows))
    nonin = sorted({(r['curve_id'], r['k']) for r in rows if r['eligible_duplicate_excess'] or r['eligible_infinity']})
    check('only E0 at k=5,6,7 is non-injective', nonin == [('E0', 5), ('E0', 6), ('E0', 7)], nonin)
    # sample a census row against Sage point arithmetic
    import run01_comparison as r1
    c = curves[4321]
    dom = r1.factor_domain(m83.curve(c['b']), 5, 'polynomial')
    img = r1.enumerate_image(dom)
    row = [r for r in rows if r['curve_id'] == c['curve_id'] and r['k'] == 5 and r['profile'] == 'polynomial'][0]
    check('census row %s k=5 reproduced in Sage' % c['curve_id'],
          row['prime_subgroup_distinct_targets'] == len(img['image']) and row['x_count'] == len(dom['lifts']))
    solver = [r for r in jsonl('run01-comparison/census-*.jsonl') if r['k'] == 4 and r['profile'] == 'polynomial']
    check('k=4 solver census: 6475 curves, no errors', len({r['curve_id'] for r in solver}) == 6475
          and not any(c['status'] == 'error' for r in solver for c in r['cells']))
    # torsion
    e0 = json.loads((OUT / 'run04-explicit-descent' / 'E0-torsion.json').read_text())
    fl = json.loads((OUT / 'run04-explicit-descent' / 'O00-00-torsion.json').read_text())
    fr = json.loads((OUT / 'run04-explicit-descent' / 'E0-frobcheck.json').read_text())
    check('E0 twist point of order 6473; floor twist point of order 6473^2; pi = 2514',
          e0['order_is_ell'] and fl['order_is_ell_squared'] and fr['frobenius_matches'] and fr['tau_sum_has_order_ell'])
    # graph
    g = json.loads((OUT / 'run10-horizontal' / 'horizontal-graph.json').read_text())['summary']
    check('horizontal graphs 2-regular with cycle length = class order',
          all(v['two_regular'] and v['matches_class_order'] for v in g.values()))
    # probes
    pr = json.loads((OUT / 'run06-four-summand' / 'public-probes.json').read_text())
    check('Run-06: zero natural rows, all planted controls recovered',
          all(v['natural_rows'] == 0 and v['planted_recovered'] == v['planted_controls'] for v in pr.values()))
    p9 = OUT / 'run09-frobenius-atlas' / 'public-probes.json'
    if p9.exists():
        check('Run-09: zero natural rows', all(v['natural_rows'] == 0 for v in json.loads(p9.read_text()).values()))
    # run08
    a8 = json.loads((OUT / 'run08-subspaces' / 'analysis.json').read_text())
    check('Run-08: no gate passer at k >= 11; screen covers 6475 x 64 x 3 cells',
          a8['scaled_curves_passing_gate_k_ge_11'] == [] and a8['screen_cells'] == 6475 * 64 * 3)
    # manifest
    lines_out = []
    for path in sorted(p for p in glob.glob(str(OUT / '**' / '*'), recursive=True)):
        pth = m83.Path(path)
        if pth.is_file() and pth.name not in ('SHA256SUMS', 'audit.json'):
            lines_out.append('%s  %s' % (hashlib.sha256(pth.read_bytes()).hexdigest(), pth.relative_to(OUT)))
    (OUT / 'SHA256SUMS').write_text('\n'.join(lines_out) + '\n')
    result = {'checks': checks, 'passed': sum(c['passed'] for c in checks), 'total': len(checks),
              'manifest_files': len(lines_out)}
    (OUT / 'audit.json').write_text(json.dumps(result, indent=1) + '\n')
    print('%d/%d checks passed; %d files hashed' % (result['passed'], result['total'], len(lines_out)))


if __name__ == '__main__':
    main()
