"""Run-09: Frobenius-conjugate descendant atlases on F_(2^83).

Each strict descendant orbit O<o> has 83 conjugate charts O<o>-<s> linked by
the relative Frobenius (x, y) -> (x^2, y^2): E_b -> E_(b^2).  A chart's points
pull back to the reference O<o>-00 by x -> x^(2^(83 - s)).  For every orbit:

  columns   union and overlap of the pulled-back chart-specific factor bases
            (each chart's Run-08 persistent candidate) at k = 5, 8, 10;
  images    exact k = 5 signed four-summand prime-subgroup images of every
            chart, pulled back: atlas union, within- and cross-chart overlap,
            best single chart, coverage gain versus 83 chart solves;
  common    control: the reference basis transported to every chart gives
            identical pulled-back columns and targets (one-fold coverage for
            83-fold work);
  probes    for orbits holding a Run-04 descendant, the public targets
            Q' + [a_i]P' transported to every chart and matched against each
            chart's pair table (k = 9 by default; --k).

    sage -python run09_frobenius_atlas.py orbits --shards 4 --shard-index I
    sage -python run09_frobenius_atlas.py probes
    sage -python run09_frobenius_atlas.py analyze
"""
import argparse
import glob
import hashlib
import json

import f83lib
import m83
import run08_subspaces as r8

OUT = m83.OUT / 'run09-frobenius-atlas'
M = m83.M


def frob(v, n):
    """v^(2^n) in F_(2^83), n taken mod 83."""
    return f83lib.frobn([v], n)[0]


def frob_set(values, n):
    return set(f83lib.frobn(list(values), n))


def frob_points(points, n):
    pts = list(points)
    xs = f83lib.frobn([p[0] for p in pts], n)
    ys = f83lib.frobn([p[1] for p in pts], n)
    return set(zip(xs, ys))


def chart_base(b, basis, k):
    table = f83lib.ratx(b, basis[:k])
    masks = [m for m in range(1 << k) if table[m]]
    xs = []
    for m in masks:
        v = 0
        for i in range(k):
            if m >> i & 1:
                v ^= basis[i]
        xs.append(v)
    return xs


def components(sets):
    """Connected components of charts sharing a column."""
    parent = list(range(len(sets)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    owner = {}
    for i, s in enumerate(sets):
        for x in s:
            if x in owner:
                parent[find(i)] = find(owner[x])
            else:
                owner[x] = i
    sizes = {}
    for i in range(len(sets)):
        r = find(i)
        sizes[r] = sizes.get(r, 0) + 1
    return sorted(sizes.values(), reverse=True)


def orbit_atlas(orbit, curves, choice, cands):
    charts = [c for c in curves if c['orbit'] == orbit]
    charts.sort(key=lambda c: c['shift'])
    assert len(charts) == M
    row = {'orbit': orbit, 'reference': charts[0]['curve_id'], 'columns': {}}
    for k in (5, 8, 10):
        sets = []
        for c in charts:
            xs = chart_base(int(c['b']), cands[choice[c['curve_id']]], k)
            sets.append(frob_set(xs, M - c['shift']))
        total = sum(len(s) for s in sets)
        union = set().union(*sets)
        row['columns'][str(k)] = {'incidences': total, 'union': len(union), 'overlap_excess': total - len(union),
                                  'largest_chart': max(len(s) for s in sets),
                                  'union_over_largest': len(union) / max(len(s) for s in sets),
                                  'overlap_components': components(sets)[:5],
                                  'component_count': len(components(sets))}
    # exact k = 5 four-summand images
    atlas = {}
    per_chart = []
    cols5 = []
    within = 0
    for c in charts:
        b = int(c['b'])
        xs = chart_base(b, cands[choice[c['curve_id']]], 5)
        ys, tags = f83lib.points(b, xs)
        st = f83lib.image(b, xs, ys, tags, 4, targets_cap=1 << 20)
        within += st['eligible_duplicate_excess']
        pulled = frob_points(st['targets'], M - c['shift'])
        per_chart.append(len(pulled))
        cols5.append(len(xs))
        for t in pulled:
            atlas[t] = atlas.get(t, 0) + 1
    cross = sum(v - 1 for v in atlas.values())
    bi = max(range(M), key=lambda i: (per_chart[i], -cols5[i]))
    best = per_chart[bi]
    union5 = row['columns']['5']['union']
    target_factor = (union5 / len(atlas)) / (cols5[bi] / best)
    row['images_k5'] = {'sum_chart_eligible_targets': sum(per_chart), 'atlas_union': len(atlas),
                        'within_chart_excess': within, 'cross_chart_overlap': cross,
                        'best_single_chart': best, 'best_chart': charts[bi]['curve_id'],
                        'best_chart_columns': cols5[bi], 'coverage_gain': len(atlas) / best,
                        'chart_solver_multiplier': M, 'gain_per_chart_solve': len(atlas) / best / M,
                        'target_factor': target_factor, 'total_solver_work_vs_best': M * target_factor}
    # common-basis control: the reference basis transported by Frobenius to every chart
    ref_basis = cands[choice[charts[0]['curve_id']]]
    common_cols, common_targets = set(), None
    identical = True
    for c in charts:
        basis = f83lib.frobn(ref_basis, c['shift'])
        b = int(c['b'])
        xs = chart_base(b, basis, 5)
        ys, tags = f83lib.points(b, xs)
        st = f83lib.image(b, xs, ys, tags, 4, targets_cap=1 << 20)
        cols = frob_set(xs, M - c['shift'])
        tg = frob_points(st['targets'], M - c['shift'])
        if common_targets is None:
            common_cols, common_targets = cols, tg
        identical &= cols == common_cols and tg == common_targets
    row['common_basis_control'] = {'identical_columns_and_targets': identical,
                                   'union_columns': len(common_cols), 'union_targets': len(common_targets)}
    return row


def cmd_orbits(args):
    curves = m83.load_inventory()
    analysis = json.loads((m83.OUT / 'run08-subspaces' / 'analysis.json').read_text())
    choice = analysis['choice']
    cands = r8.candidates()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ('orbits-%d.jsonl' % args.shard_index)
    done = set()
    if path.exists():
        done = {json.loads(l)['orbit'] for l in open(path)}
    with path.open('a') as f:
        for orbit in range(m83.N_ORBITS):
            if orbit % args.shards != args.shard_index or orbit in done:
                continue
            row = orbit_atlas(orbit, curves, choice, cands)
            f.write(json.dumps(row) + '\n')
            f.flush()
            print(json.dumps({'orbit': orbit, 'union10': row['columns']['10']['union'],
                              'gain': round(row['images_k5']['coverage_gain'], 3)}), flush=True)


def cmd_probes(args):
    """Public targets transported to every chart of each mapped orbit, k = 10 pair tables."""
    from run06_four_summand import public_on
    curves = m83.load_inventory()
    byid = {c['curve_id']: c for c in curves}
    analysis = json.loads((m83.OUT / 'run08-subspaces' / 'analysis.json').read_text())
    choice = analysis['choice']
    cands = r8.candidates()
    sel = json.loads((m83.OUT / 'run04-explicit-descent' / 'selection.json').read_text())
    out = {}
    for pick in sel['selected']:
        ref = byid[pick['curve_id']]
        E = m83.curve(ref['b'])
        Pc, Qc = public_on(ref['curve_id'])
        P = E(m83.dec(Pc[0]), m83.dec(Pc[1]))
        Q = E(m83.dec(Qc[0]), m83.dec(Qc[1]))
        targets = []
        for i in range(args.targets):
            a = int.from_bytes(hashlib.sha256(b'm83-run09-public-target:%d' % i).digest(), 'big') % m83.ELL
            T = Q + a * P
            targets.append((m83.enc(T[0]), m83.enc(T[1])))
        rows = 0
        cells = 0
        for c in curves:
            if c['orbit'] != ref['orbit']:
                continue
            d = (c['shift'] - ref['shift']) % M
            tt = list(zip(f83lib.frobn([t[0] for t in targets], d), f83lib.frobn([t[1] for t in targets], d)))
            b = int(c['b'])
            xs = chart_base(b, cands[choice[c['curve_id']]], args.k)
            ys, _ = f83lib.points(b, xs)
            pr = f83lib.pair_probe(b, xs, ys, tt, wcap=16)
            rows += sum(pr['counts'])
            cells += len(tt)
        out[ref['curve_id']] = {'orbit': ref['orbit'], 'charts': M, 'public_targets': args.targets, 'k': args.k,
                                'chart_target_cells': cells, 'natural_rows': rows}
        print(json.dumps(out[ref['curve_id']]), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'public-probes.json').write_text(json.dumps(out, indent=1) + '\n')


def cmd_analyze(args):
    rows = [json.loads(l) for p in glob.glob(str(OUT / 'orbits-*.jsonl')) for l in open(p)]
    rows.sort(key=lambda r: r['orbit'])
    assert len(rows) == m83.N_ORBITS
    gains = [r['images_k5']['coverage_gain'] for r in rows]
    summary = {'orbits': len(rows),
               'k10_union_range': [min(r['columns']['10']['union'] for r in rows),
                                   max(r['columns']['10']['union'] for r in rows)],
               'k10_union_over_largest_range': [min(r['columns']['10']['union_over_largest'] for r in rows),
                                                max(r['columns']['10']['union_over_largest'] for r in rows)],
               'k10_overlap_excess_total': sum(r['columns']['10']['overlap_excess'] for r in rows),
               'k5_cross_chart_overlap_total': sum(r['images_k5']['cross_chart_overlap'] for r in rows),
               'k5_within_chart_excess_total': sum(r['images_k5']['within_chart_excess'] for r in rows),
               'coverage_gain_range': [min(gains), max(gains)],
               'total_solver_work_range': [min(r['images_k5']['total_solver_work_vs_best'] for r in rows),
                                           max(r['images_k5']['total_solver_work_vs_best'] for r in rows)],
               'gain_per_chart_solve_range': [min(g / M for g in gains), max(g / M for g in gains)],
               'common_basis_identical_all': all(r['common_basis_control']['identical_columns_and_targets']
                                                 for r in rows)}
    (OUT / 'analysis.json').write_text(json.dumps({'summary': summary, 'orbits': rows}, indent=1) + '\n')
    print(json.dumps(summary, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['orbits', 'probes', 'analyze'])
    ap.add_argument('--shards', type=int, default=1)
    ap.add_argument('--shard-index', type=int, default=0)
    ap.add_argument('--targets', type=int, default=16)
    ap.add_argument('--k', type=int, default=9)
    args = ap.parse_args()
    {'orbits': cmd_orbits, 'probes': cmd_probes, 'analyze': cmd_analyze}[args.command](args)


if __name__ == '__main__':
    main()
