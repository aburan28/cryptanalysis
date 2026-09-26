"""Exact three-summand relation images for every curve, via native/libf83.

For E0 and all 6474 conductor-6473 curves, and each profile (k, basis):
rational x count, Z/4 tag types (n0, n2, no), all/eligible signed triples,
infinity sums, distinct targets, duplicate excess and every duplicate witness,
and the closed eligibility formula of ECC2K-130 run-02,

    eligible = 8 (C(n0,3) + n0 C(n2,2)) + 4 (n0 + n2) C(no,2).

Profiles 4:polynomial, 4:random and 5:polynomial are run-01's; 6 and 7 are the
run-03 census (ECC2K-130 ran k=7 only on six selected curves).  The solver
cells of run-01 are in census-*.jsonl / panel-*.jsonl.

    sage -python run01_yield_census.py --shards 4 --shard-index I
"""
import argparse
import json
import math
import time
from pathlib import Path

import f83lib
import m83
from run01_comparison import coordinate_basis

PROFILES = [(4, 'polynomial'), (4, 'random'), (5, 'polynomial'), (6, 'polynomial'), (7, 'polynomial')]


def formula(n0, n2, no):
    c2 = lambda n: n * (n - 1) // 2
    c3 = lambda n: n * (n - 1) * (n - 2) // 6
    return 8 * (c3(n0) + n0 * c2(n2)) + 4 * (n0 + n2) * c2(no)


def census_row(curve, k, profile):
    basis = [m83.enc(u) for u in coordinate_basis(k, profile)]
    b = int(curve['b'])
    table = f83lib.ratx(b, basis)
    masks = [m for m in range(1 << k) if table[m]]
    xs = []
    for m in masks:
        v = 0
        for i in range(k):
            if m >> i & 1:
                v ^= basis[i]
        xs.append(v)
    ys, tags = f83lib.points(b, xs)
    types = {'n0': sum(t == 0 for t in tags), 'n2': sum(t == 2 for t in tags),
             'no': sum(t in (1, 3) for t in tags)}
    st = f83lib.image(b, xs, ys, tags, 3, dup_cap=4096)
    pred = formula(types['n0'], types['n2'], types['no'])
    assert pred == st['eligible_signed_tuples'], (curve['curve_id'], k, profile)
    assert st['all_signed_tuples'] == 8 * math.comb(len(xs), 3)
    dups = [{'group': g, 'witness': [[masks[i], s] for i, s in f83lib.unpack_id(w, 3)]}
            for g, w in st['duplicates']]
    return {'curve_id': curve['curve_id'], 'orbit': curve['orbit'], 'shift': curve['shift'],
            'k': k, 'profile': profile, 'x_count': len(xs), 'allowed_x_masks': masks,
            'tag_types': types, 'eligible_formula': pred,
            **{key: st[key] for key in ('all_signed_tuples', 'infinity_tuples', 'full_distinct_targets',
                                        'eligible_signed_tuples', 'eligible_infinity',
                                        'prime_subgroup_distinct_targets', 'eligible_duplicate_excess')},
            'duplicate_witnesses': dups,
            'log2_prime_subgroup_coverage': (math.log2(st['prime_subgroup_distinct_targets']) - math.log2(m83.ELL - 1)
                                             if st['prime_subgroup_distinct_targets'] else None)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shards', type=int, default=1)
    ap.add_argument('--shard-index', type=int, default=0)
    ap.add_argument('--output-dir', default=str(m83.OUT / 'run01-comparison'))
    ap.add_argument('--resume', action='store_true')
    args = ap.parse_args()
    curves = [c for i, c in enumerate(m83.load_inventory()) if i % args.shards == args.shard_index]
    path = Path(args.output_dir) / ('yield-census-%d.jsonl' % args.shard_index)
    done = set()
    if path.exists():
        if not args.resume:
            raise ValueError('refusing to overwrite')
        good = []
        for line in path.read_text().splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                break          # a torn final line from an interrupted run
            good.append(line)
            done.add((row['curve_id'], row['k'], row['profile']))
        path.write_text(''.join(l + '\n' for l in good))
    started = time.perf_counter()
    with path.open('a') as f:
        for n, curve in enumerate(curves):
            for k, profile in PROFILES:
                if (curve['curve_id'], k, profile) in done:
                    continue
                f.write(json.dumps(census_row(curve, k, profile)) + '\n')
            if n % 200 == 0:
                print(json.dumps({'curves': n, 'seconds': round(time.perf_counter() - started, 1)}), flush=True)
    print(json.dumps({'done': len(curves), 'seconds': round(time.perf_counter() - started, 1)}), flush=True)


if __name__ == '__main__':
    main()
