"""Run-08: descendant-adapted factor bases across the complete conductor-6473 floor.

Every curve (E0 and all 6474 descendants) is screened on the same 64 nested
coordinate-subspace candidates:

  polynomial      w^0, w^1, ...
  scale-01..31    c_j w^0, c_j w^1, ...   (c_j deterministic nonzero scalars)
  random-00..31   deterministic random F_2-independent vectors

At k = 8, 9, 10 each cell records the exact rational x count b (Tr(x + b/x^2)
= 0), the direct membership-indicator ANF degree and term count, and the
uniform-tag four-summand model: targets for ceil(1.1 b) rows =
ceil(1.1 b) (ELL - 1) / (4 C(b, 4)).  One persistent candidate per curve
minimizes the sum of the three log target counts.  Exact Z/4 tags are then
charged on the closest finalists, and every curve's candidate is extended to
k = 16.  The gate is a >= 20% attempt reduction against optimized E0 in two
adjacent dimensions with membership degree no worse than E0's.

    sage -python run08_subspaces.py screen --shards 4 --shard-index I
    sage -python run08_subspaces.py analyze
"""
import argparse
import glob
import json
import math
import random

import numpy as np

import f83lib
import m83
from run06_four_summand import eligible4

OUT = m83.OUT / 'run08-subspaces'
KMAX = 16


def candidates():
    """name -> list of KMAX field-element integers (nested bases)."""
    W = m83.W
    poly = [m83.enc(W ** i) for i in range(KMAX)]
    out = {'polynomial': poly}
    rng = random.Random(20260924)
    for j in range(1, 32):
        c = m83.dec(rng.getrandbits(m83.M) or 1)
        out['scale-%02d' % j] = [m83.enc(c * W ** i) for i in range(KMAX)]
    for j in range(32):
        r = random.Random(1000 + j)
        basis, pivots = [], {}
        while len(basis) < KMAX:
            u = r.getrandbits(m83.M)
            v = u
            while v and v.bit_length() - 1 in pivots:
                v ^= pivots[v.bit_length() - 1]
            if v:
                pivots[v.bit_length() - 1] = v
                basis.append(u)
        out['random-%02d' % j] = basis
    return out


def anf_degree_terms(indicator, k):
    a = indicator[: 1 << k].astype(np.uint8).copy()
    for i in range(k):
        step = 1 << i
        a = a.reshape(-1, 2 * step)
        a[:, step:] ^= a[:, :step]
        a = a.reshape(-1)
    idx = np.nonzero(a)[0]
    if len(idx) == 0:
        return 0, 0
    return int(max(bin(int(i)).count('1') for i in idx)), int(len(idx))


def log2_targets(b):
    if b < 4:
        return None
    return math.log2(math.ceil(1.1 * b)) + math.log2(m83.ELL - 1) - math.log2(4 * math.comb(b, 4))


def cells_for(b_coef, basis, ks):
    table = f83lib.ratx(b_coef, basis[:max(ks)])
    rows = {}
    for k in ks:
        sub = table[: 1 << k]
        count = int(sub.sum())
        invalid = (1 - sub).astype(np.uint8)
        deg, terms = anf_degree_terms(invalid, k)
        rows[k] = {'x': count, 'anf_degree': deg, 'anf_terms': terms, 'log2_targets': log2_targets(count)}
    return rows


def cmd_screen(args):
    cands = candidates()
    curves = [c for i, c in enumerate(m83.load_inventory()) if i % args.shards == args.shard_index]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ('screen-%d.jsonl' % args.shard_index)
    if path.exists():
        raise ValueError('refusing to overwrite')
    with path.open('w') as f:
        for n, curve in enumerate(curves):
            b = int(curve['b'])
            row = {'curve_id': curve['curve_id'], 'cells': {}}
            for name, basis in cands.items():
                c = cells_for(b, basis, (8, 9, 10))
                row['cells'][name] = [[c[k]['x'], c[k]['anf_degree'], c[k]['anf_terms']] for k in (8, 9, 10)]
            f.write(json.dumps(row) + '\n')
            if n % 250 == 0:
                print(json.dumps({'curves': n}), flush=True)


def load_screen():
    """curve -> candidate -> {'8': cell, '9': cell, '10': cell}."""
    rows = {}
    for path in glob.glob(str(OUT / 'screen-*.jsonl')):
        for line in open(path):
            r = json.loads(line)
            rows[r['curve_id']] = {
                name: {str(k): {'x': x, 'anf_degree': d, 'anf_terms': t, 'log2_targets': log2_targets(x)}
                       for k, (x, d, t) in zip((8, 9, 10), vals)}
                for name, vals in r['cells'].items()}
    return rows


def persistent(cells):
    def score(name):
        vals = [cells[name][str(k)]['log2_targets'] for k in (8, 9, 10)]
        return float('inf') if None in vals else sum(vals)
    best = min(cells, key=lambda n: (score(n), n))
    return best, score(best)


def exact_tag_targets(b_coef, basis, k):
    table = f83lib.ratx(b_coef, basis[:k])
    masks = [m for m in range(1 << k) if table[m]]
    xs = []
    for m in masks:
        v = 0
        for i in range(k):
            if m >> i & 1:
                v ^= basis[i]
        xs.append(v)
    ys, tags = f83lib.points(b_coef, xs)
    el = eligible4(tags)
    n = len(xs)
    return n, el, math.log2(math.ceil(1.1 * n)) + math.log2(m83.ELL - 1) - math.log2(el)


def cmd_analyze(args):
    screen = load_screen()
    assert len(screen) == m83.FLOOR_SIZE + 1
    cands = candidates()
    inventory = {c['curve_id']: c for c in m83.load_inventory()}
    choice = {cid: persistent(cells) for cid, cells in screen.items()}
    e0_name = choice['E0'][0]
    e0 = screen['E0'][e0_name]
    ratio = lambda cells, k: 2 ** (cells[str(k)]['log2_targets'] - e0[str(k)]['log2_targets'])
    # single-cell outliers (any candidate) at k = 8, 9, 10
    best_cells = {}
    for k in (8, 9, 10):
        best = min(((ratio(cells[n], k), cid, n) for cid, cells in screen.items() if cid != 'E0'
                    for n in cells if cells[n][str(k)]['log2_targets'] is not None))
        best_cells[k] = {'ratio': best[0], 'curve_id': best[1], 'candidate': best[2]}
    # persistent finalists: smallest worst-case ratio over k = 8..10
    pers = []
    for cid, (name, _) in choice.items():
        if cid == 'E0':
            continue
        cells = screen[cid][name]
        rs = [ratio(cells, k) for k in (8, 9, 10)]
        pers.append((max(rs), cid, name, rs))
    pers.sort()
    finalists = []
    e0_exact = {k: exact_tag_targets(1, cands[e0_name], k) for k in (8, 9, 10)}
    for worst, cid, name, rs in pers[: args.finalists]:
        b = int(inventory[cid]['b'])
        ex = {k: exact_tag_targets(b, cands[name], k) for k in (8, 9, 10)}
        exr = {k: 2 ** (ex[k][2] - e0_exact[k][2]) for k in (8, 9, 10)}
        model_r = {k: ratio(screen[cid][name], k) for k in (8, 9, 10)}
        deg_ok = {k: screen[cid][name][str(k)]['anf_degree'] <= e0[str(k)]['anf_degree'] for k in (8, 9, 10)}
        passes = any(exr[k] <= 0.8 and exr[k + 1] <= 0.8 and deg_ok[k] and deg_ok[k + 1] for k in (8, 9))
        finalists.append({'curve_id': cid, 'candidate': name, 'exact_ratio': exr, 'model_ratio': model_r,
                          'max_tag_correction': max(abs(exr[k] / model_r[k] - 1) for k in (8, 9, 10)),
                          'membership_degree_no_worse': deg_ok, 'passes_adjacent_gate': passes})
    # scaling every curve's persistent candidate through k = 16; the adjacent
    # gate is evaluated for every curve and every adjacent pair (not only the
    # finalists), first in the uniform-tag model, then with exact tags.
    scale = {}
    ks = list(range(8, KMAX + 1))
    e0_scale = cells_for(1, cands[e0_name], ks)
    per_k = {k: [] for k in ks}
    model_passers = []
    for cid, (name, _) in choice.items():
        if cid == 'E0':
            continue
        cells = cells_for(int(inventory[cid]['b']), cands[name], ks)
        rs = {k: 2 ** (cells[k]['log2_targets'] - e0_scale[k]['log2_targets']) for k in ks}
        for k in ks:
            per_k[k].append((rs[k], cid))
        ok = {k: rs[k] <= 0.8 and cells[k]['anf_degree'] <= e0_scale[k]['anf_degree'] for k in ks}
        pairs = [k for k in ks[:-1] if ok[k] and ok[k + 1]]
        if pairs:
            model_passers.append((cid, name, pairs))
        scale[cid] = {'candidate': name, 'ratios': rs, 'x': {k: cells[k]['x'] for k in ks},
                      'anf_degree': {k: cells[k]['anf_degree'] for k in ks}}
    exact_passers = []
    for cid, name, pairs in model_passers:
        b = int(inventory[cid]['b'])
        exact = {}
        for k in sorted({k for p in pairs for k in (p, p + 1)}):
            ex = exact_tag_targets(b, cands[name], k)
            e0x = exact_tag_targets(1, cands[e0_name], k)
            exact[k] = 2 ** (ex[2] - e0x[2])
        confirmed = [k for k in pairs if exact[k] <= 0.8 and exact[k + 1] <= 0.8]
        exact_passers.append({'curve_id': cid, 'candidate': name, 'model_pairs': pairs, 'exact_ratios': exact,
                              'exact_pairs': confirmed, 'ratios_k8_16': scale[cid]['ratios']})
    passes_scaled = [p['curve_id'] for p in exact_passers if any(k >= 11 for k in p['exact_pairs'])]
    dist = {}
    for k in ks:
        vals = sorted(v for v, _ in per_k[k])
        dist[k] = {'best': vals[0], 'best_curve': min(per_k[k])[1], 'median': float(np.median(vals)),
                   'p05': float(np.percentile(vals, 5)), 'p95': float(np.percentile(vals, 95))}
    out = {'candidates': len(cands), 'screen_cells': len(screen) * len(cands) * 3,
           'scaling_cells': len(scale) * len(ks), 'optimized_E0': {'candidate': e0_name,
                                                                   'x': {k: e0[str(k)]['x'] for k in (8, 9, 10)}},
           'best_single_cells': best_cells, 'finalists': finalists,
           'finalists_passing_gate': [f['curve_id'] for f in finalists if f['passes_adjacent_gate']],
           'scaling_distribution': dist, 'scaled_curves_passing_gate_k_ge_11': passes_scaled,
           'e0_membership_degree': {k: e0_scale[k]['anf_degree'] for k in ks},
           'all_curve_gate_passers': exact_passers,
           'choice': {cid: v[0] for cid, v in choice.items()}}
    (OUT / 'analysis.json').write_text(json.dumps(out, indent=1) + '\n')
    (OUT / 'scaling.json').write_text(json.dumps(scale) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k not in ('choice',)}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['screen', 'analyze'])
    ap.add_argument('--shards', type=int, default=1)
    ap.add_argument('--shard-index', type=int, default=0)
    ap.add_argument('--finalists', type=int, default=8)
    args = ap.parse_args()
    {'screen': cmd_screen, 'analyze': cmd_analyze}[args.command](args)


if __name__ == '__main__':
    main()
