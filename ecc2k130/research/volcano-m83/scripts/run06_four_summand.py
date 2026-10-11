"""Run-06: matched four-summand yield, natural public-target probes and cost gates.

For E0 and the Run-04 descendants (explicit degree-6473 maps), at k = 8, 9, 10
with the polynomial subspace:

  yields   exact eligible signed four-tuples by a Z/4 dynamic program over the
           factor base (unordered distinct x, both signs, tag sum 0 mod 4);
           natural bases, an equal-cardinality panel (SHA-256-ordered subsets
           of the smallest natural size) and a common-x panel (masks rational
           on every compared curve).  Target counts for ceil(1.1 b) rows are
           collision-free lower bounds: (ceil(1.1 b)) (ELL - 1) / eligible.
  probes   the complete k=10 pair table matched against deterministic public
           targets Q' + [a_i] P', a_i = SHA256("m83-run06-natural-target:" i)
           mod ELL, on each curve (P', Q' are the Run-04 images of the header
           points; E0 uses P, Q), plus planted controls that must be recovered.
           Planted rows never enter yield or rank.

No discrete logarithm is computed.
"""
import argparse
import hashlib
import json
import math
import random
import time

import f83lib
import m83
from run01_comparison import coordinate_basis

OUT = m83.OUT / 'run06-four-summand'


def factor_base(b, k, masks_only=False):
    basis = [m83.enc(u) for u in coordinate_basis(k, 'polynomial')]
    table = f83lib.ratx(b, basis)
    masks = [m for m in range(1 << k) if table[m]]
    if masks_only:
        return masks, basis
    xs = []
    for m in masks:
        v = 0
        for i in range(k):
            if m >> i & 1:
                v ^= basis[i]
        xs.append(v)
    ys, tags = f83lib.points(b, xs)
    return masks, xs, ys, tags


def eligible4(tags):
    """Unordered 4-subsets of distinct x with sign choices and tag sum = 0 mod 4."""
    dp = [[0] * 4 for _ in range(5)]
    dp[0][0] = 1
    for t in tags:
        for c in range(4, 0, -1):
            for r in range(4):
                dp[c][r] += dp[c - 1][(r - t) % 4] + dp[c - 1][(r + t) % 4]
    return dp[4][0]


def rows_needed(b):
    return math.ceil(1.1 * b)


def target_bound(b, eligible):
    return rows_needed(b) * (m83.ELL - 1) / eligible


def selected_curves():
    sel = json.loads((m83.OUT / 'run04-explicit-descent' / 'selection.json').read_text())
    return ['E0'] + [p['curve_id'] for p in sel['selected']]


def cmd_yields(args):
    inventory = {c['curve_id']: c for c in m83.load_inventory()}
    ids = selected_curves()
    out = {'curves': ids, 'k': {}}
    for k in (8, 9, 10):
        data = {}
        for cid in ids:
            b = int(inventory[cid]['b'])
            masks, xs, ys, tags = factor_base(b, k)
            data[cid] = {'masks': masks, 'xs': xs, 'tags': dict(zip(masks, tags))}
        e0 = data['E0']
        natural = {}
        for cid in ids:
            d = data[cid]
            n = len(d['masks'])
            el = eligible4(list(d['tags'].values()))
            natural[cid] = {'x_count': n, 'eligible': el,
                            'log2_coverage_upper_bound': math.log2(el) - math.log2(m83.ELL - 1),
                            'log2_targets_for_rows': math.log2(target_bound(n, el))}
        base = natural['E0']
        for cid in ids:
            r = natural[cid]
            r['raw_yield_vs_E0'] = r['eligible'] / base['eligible']
            r['attempt_ratio_vs_E0'] = target_bound(r['x_count'], r['eligible']) / target_bound(base['x_count'], base['eligible'])
            r['optimistic_attempt_reduction'] = 1 - r['attempt_ratio_vs_E0']
        size = min(len(data[c]['masks']) for c in ids)
        matched = {}
        for cid in ids:
            d = data[cid]
            order = sorted(d['masks'], key=lambda m: hashlib.sha256(b'%d' % m).digest())[:size]
            matched[cid] = eligible4([d['tags'][m] for m in order])
        common = set(data['E0']['masks'])
        for cid in ids:
            common &= set(data[cid]['masks'])
        common_el = {cid: eligible4([data[cid]['tags'][m] for m in sorted(common)]) for cid in ids}
        out['k'][str(k)] = {
            'natural': natural,
            'equal_cardinality': {'size': size, 'eligible': matched,
                                  'deviation_vs_E0': {c: matched[c] / matched['E0'] - 1 for c in ids}},
            'common_x': {'size': len(common), 'eligible': common_el,
                         'deviation_vs_E0': {c: common_el[c] / common_el['E0'] - 1 for c in ids}},
        }
        print(k, json.dumps({c: (natural[c]['x_count'], round(natural[c]['raw_yield_vs_E0'], 4),
                                 round(out['k'][str(k)]['equal_cardinality']['deviation_vs_E0'][c], 6))
                             for c in ids}), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'yields.json').write_text(json.dumps(out, indent=1) + '\n')


def public_on(cid):
    """(P, Q) on the curve: header points on E0, Run-04 images on descendants."""
    if cid == 'E0':
        P, Q = m83.public_points()
        return (m83.enc(P[0]), m83.enc(P[1])), (m83.enc(Q[0]), m83.enc(Q[1]))
    row = json.loads((m83.OUT / 'run04-explicit-descent' / ('%s-explicit-map.json' % cid)).read_text())
    return ((int(row['mapped_P']['x']), int(row['mapped_P']['y'])),
            (int(row['mapped_Q']['x']), int(row['mapped_Q']['y'])))


def cmd_probes(args):
    inventory = {c['curve_id']: c for c in m83.load_inventory()}
    results = {}
    for cid in selected_curves():
        curve = inventory[cid]
        b = int(curve['b'])
        E = m83.curve(b)
        Pc, Qc = public_on(cid)
        P = E(m83.dec(Pc[0]), m83.dec(Pc[1]))
        Q = E(m83.dec(Qc[0]), m83.dec(Qc[1]))
        natural = []
        for i in range(args.targets):
            a = int.from_bytes(hashlib.sha256(b'm83-run06-natural-target:%d' % i).digest(), 'big') % m83.ELL
            T = Q + a * P
            natural.append((m83.enc(T[0]), m83.enc(T[1])))
        masks, xs, ys, tags = factor_base(b, 10)
        rng = random.Random(hashlib.sha256(cid.encode()).digest())
        planted, plan = [], []
        while len(planted) < args.planted:
            quad = sorted(rng.sample(range(len(xs)), 4))
            signs = [rng.randrange(2) for _ in quad]
            if sum((tags[i] if s == 0 else -tags[i]) for i, s in zip(quad, signs)) % 4:
                continue
            S = E(0)
            for i, s in zip(quad, signs):
                pt = E(m83.dec(xs[i]), m83.dec(ys[i]))
                S += pt if s == 0 else -pt
            if S.is_zero():
                continue
            planted.append((m83.enc(S[0]), m83.enc(S[1])))
            plan.append([[masks[i], s] for i, s in zip(quad, signs)])
        t0 = time.perf_counter()
        pr = f83lib.pair_probe(b, xs, ys, natural + planted)
        seconds = time.perf_counter() - t0
        nat_counts = pr['counts'][:len(natural)]
        pl_counts = pr['counts'][len(natural):]
        assert all(c >= 1 for c in pl_counts), 'planted control not recovered'
        # replay every planted witness through Sage
        replayed = 0
        for t, ab, cd in pr['witnesses']:
            if t < len(natural):
                continue
            S = E(0)
            for i, s in ab + cd:
                pt = E(m83.dec(xs[i]), m83.dec(ys[i]))
                S += pt if s == 0 else -pt
            tgt = planted[t - len(natural)]
            assert (m83.enc(S[0]), m83.enc(S[1])) == tgt
            replayed += 1
        results[cid] = {'k': 10, 'x_count': len(xs), 'pair_entries': pr['pair_entries'],
                        'distinct_pair_sums': pr['distinct_pair_sums'],
                        'pair_collision_excess': pr['pair_collision_excess'],
                        'public_targets': len(natural), 'natural_rows': sum(nat_counts),
                        'natural_counts': nat_counts, 'planted_controls': len(planted),
                        'planted_recovered': sum(c >= 1 for c in pl_counts),
                        'planted_witnesses_replayed': replayed, 'planted_plan': plan,
                        'probe_seconds': seconds, 'eligible4': eligible4(tags),
                        'log2_coverage_upper_bound': math.log2(eligible4(tags)) - math.log2(m83.ELL - 1)}
        print(cid, json.dumps({k: v for k, v in results[cid].items() if k != 'planted_plan'}), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'public-probes.json').write_text(json.dumps(results, indent=1) + '\n')


def cmd_rho(args):
    inv = json.loads((m83.OUT / 's00-ring-invariants.json').read_text())
    rho = inv['rho_baselines']
    y = json.loads((OUT / 'yields.json').read_text())
    finite = {k: {c: v['log2_targets_for_rows'] for c, v in d['natural'].items()} for k, d in y['k'].items()}
    # ideal half-density, uniform-tag, collision-free extrapolation
    model = {}
    for k in range(8, 41):
        b = 2 ** (k - 1)
        el = 4 * math.comb(b, 4)
        model[k] = math.log2(target_bound(b, el))
    cross = min(k for k, v in model.items() if v <= rho['signed_frobenius_log2'])
    out = {'rho': rho, 'finite_log2_targets': finite, 'ideal_model_log2_targets': model,
           'crossover_k': cross, 'crossover_columns_log2': cross - 1,
           'pair_table_log2_at_crossover': math.log2(math.comb(2 ** (cross - 1), 2)),
           'direct_S5_boolean_variables_at_crossover': 4 * cross}
    (OUT / 'rho-comparison.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'ideal_model_log2_targets'}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['yields', 'probes', 'rho'])
    ap.add_argument('--targets', type=int, default=4)
    ap.add_argument('--planted', type=int, default=2)
    args = ap.parse_args()
    {'yields': cmd_yields, 'probes': cmd_probes, 'rho': cmd_rho}[args.command](args)


if __name__ == '__main__':
    main()
