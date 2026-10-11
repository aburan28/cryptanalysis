"""Run-10 atlas: chart factor bases carried along the reference's degree-11 cycle.

On F_(2^83) the class of a prime above 11 has order 1079 = 13 * 83 in
Cl(O_6473), so the 11-cycle through the reference descendant contains 13 whole
Frobenius orbits (1079 charts), unlike ECC2K-130 where each 11-cycle was a
single orbit.  Every chart's Run-08 k = 5 factor base is moved to the
reference along the shorter cycle direction.  An edge O<o>-<s> -> O<o'>-<d+s>
is the 2^s-Frobenius conjugate of the seed map O<o>-00 -> O<o'>-<d>, so a
point is pulled back by sigma^-s, mapped by the seed, and pushed by sigma^s.

Only x-coordinates are transported: an isogeny maps +-P to +-phi(P), so the
signed four-summand image of a transported base is exactly the image of the
transported relations.  Reported: path lengths, x-map evaluations and time,
pulled column union/overlap, the exact k = 5 image union on the reference,
cross-chart target overlap, and total solver work versus the best chart.

    sage -python run10_atlas.py
"""
import json
import time

import f83lib
import m83
import run08_subspaces as r8
from run09_frobenius_atlas import chart_base, components
from run10_horizontal import OUT, cycle_order, parse

M = m83.M


def horner(coeffs, x):
    acc = 0
    for c in reversed(coeffs):
        acc = f83lib.mul(acc, x) ^ c
    return acc


def main():
    adj = json.loads((OUT / 'adjacency.json').read_text())['11']
    seeds = json.loads((OUT / 'l11-seed-maps.json').read_text())
    ref = seeds['reference']
    order = cycle_order(adj, ref)
    L = len(order)
    pos = {v: i for i, v in enumerate(order)}
    inv = {c['curve_id']: c for c in m83.load_inventory()}
    choice = json.loads((m83.OUT / 'run08-subspaces' / 'analysis.json').read_text())['choice']
    cands = r8.candidates()
    # seed x-maps keyed by (source orbit, target orbit, target shift offset)
    xmaps = {}
    for cid, seed in seeds['seeds'].items():
        o, _ = parse(cid)
        for mp in seed['maps']:
            o2, d = parse(mp['target'])
            xmaps[(o, o2, d)] = ([int(c) for c in mp['x_num']], [int(c) for c in mp['x_den']])

    def step(xs, src, dst):
        o, s = parse(src)
        o2, s2 = parse(dst)
        num, den = xmaps[(o, o2, (s2 - s) % M)]
        pulled = f83lib.frobn(xs, -s)
        mapped = [f83lib.mul(horner(num, x), f83lib.inv(horner(den, x))) for x in pulled]
        return f83lib.frobn(mapped, s)

    started = time.perf_counter()
    evaluations = 0
    path_lengths = []
    sets, per_chart_targets, atlas = [], [], {}
    ref_b = int(inv[ref]['b'])
    for v in order:
        i = pos[v]
        forward = (L - i) % L          # steps walking order[i] -> order[i+1] -> ... -> ref
        backward = i                   # steps walking order[i] -> order[i-1] -> ... -> ref
        xs = chart_base(int(inv[v]['b']), cands[choice[v]], 5)
        cur = v
        if forward <= backward:
            walk = [order[(i + t) % L] for t in range(1, forward + 1)]
        else:
            walk = [order[i - t] for t in range(1, backward + 1)]
        for nxt in walk:
            xs = step(xs, cur, nxt)
            evaluations += len(xs)
            cur = nxt
        assert cur == ref
        path_lengths.append(len(walk))
        assert all(f83lib.ratx(ref_b, [x])[1] for x in xs)
        sets.append(set(xs))
        ys, tags = f83lib.points(ref_b, xs)
        st = f83lib.image(ref_b, xs, ys, tags, 4, targets_cap=1 << 20)
        per_chart_targets.append(st['prime_subgroup_distinct_targets'])
        for t in st['targets']:
            atlas[t] = atlas.get(t, 0) + 1
    seconds = time.perf_counter() - started
    total = sum(len(s) for s in sets)
    union = set().union(*sets)
    best_idx = max(range(L), key=lambda i: (per_chart_targets[i], -len(sets[i])))
    best = per_chart_targets[best_idx]
    best_cols = len(sets[best_idx])
    cross = sum(v - 1 for v in atlas.values())
    # random-target work model of Run-09/10: charts x (targets needed for union rows)
    out = {'reference': ref, 'cycle_length': L, 'orbits_in_cycle': len({parse(v)[0] for v in order}),
           'average_path_length': sum(path_lengths) / L, 'max_path_length': max(path_lengths),
           'x_map_evaluations': evaluations, 'transport_seconds': seconds,
           'column_incidences': total, 'column_union': len(union), 'column_overlap_excess': total - len(union),
           'union_over_largest_chart': len(union) / max(len(s) for s in sets), 'overlap_components': len(components(sets)),
           'atlas_targets': len(atlas), 'cross_chart_overlap': cross, 'best_single_chart_targets': best,
           'coverage_gain': len(atlas) / best,
           'best_chart': order[best_idx], 'best_chart_columns': best_cols,
           'target_factor': (len(union) / len(atlas)) / (best_cols / best),
           'total_solver_work_vs_best': L * (len(union) / len(atlas)) / (best_cols / best)}
    (OUT / 'horizontal-atlas.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
