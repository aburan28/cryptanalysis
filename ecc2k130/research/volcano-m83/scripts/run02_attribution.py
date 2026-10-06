"""Run-02/03: pin down the run-01 differences on F_(2^83).

Subcommands (outputs under outputs/run02-attribution/):

  collisions   E0's Frobenius identity: verify tau^2 + tau + 2 = 0 on the
               canonical lifts of x = w, w^2, w^4, explain every duplicate
               target of the yield census, and scan every census row for
               non-injective images.
  rank         Coefficient rank modulo ELL of one witness per distinct target
               (k = 5, 6, 7 on E0), with and without the duplicate witnesses,
               and the rank of the duplicate differences.
  exhaust      Formal degree of regularity (raw and row-reduced) for every
               reachable target x of the selected k=4 polynomial curves.
  counterfactual --axis coefficient|target|membership
               E0-anchored one-axis substitutions: top homogeneous row-space
               fingerprint and formal regularity before and after row reduction.

Counterfactual systems need not be natural factor bases for the substituted
curve; they isolate presentation terms and are never yield measurements.
"""
import argparse
from collections import Counter, defaultdict
import glob
import hashlib
import json
import random
from pathlib import Path

from sage.all import GF, matrix
from cysignals.alarm import AlarmInterrupt

import f83lib
import m83
from m83 import alarm, cancel_alarm
import run01_comparison as r1

OUT = m83.OUT / 'run02-attribution'


def load_census(pattern='yield-census-*.jsonl'):
    rows = {}
    for path in glob.glob(str(m83.OUT / 'run01-comparison' / pattern)):
        for line in open(path):
            row = json.loads(line)
            rows[(row['curve_id'], row['k'], row['profile'])] = row
    return rows


def load_solver_census():
    rows = {}
    for path in glob.glob(str(m83.OUT / 'run01-comparison' / 'census-*.jsonl')):
        for line in open(path):
            row = json.loads(line)
            if row['k'] == 4 and row['profile'] == 'polynomial':
                rows[row['curve_id']] = row
    return rows


# ---------------------------------------------------------------- collisions
def cmd_collisions(args):
    E0 = m83.curve(1)
    W = m83.W
    lifts = {}
    for mask, x in ((2, W), (4, W ** 2), (16, W ** 4)):
        pts = E0.lift_x(x, all=True)
        lifts[mask] = min(pts, key=lambda p: m83.enc(p[1]))
    P2, P4, P16 = lifts[2], lifts[4], lifts[16]
    frob = lambda P: E0(P[0] ** 2, P[1] ** 2)
    tau_signs = {'tau(P_w)': '+P_(w^2)' if frob(P2) == P4 else '-P_(w^2)',
                 'tau^2(P_w)': '+P_(w^4)' if frob(frob(P2)) == P16 else '-P_(w^4)'}
    assert (frob(frob(P2)) + frob(P2) + 2 * P2).is_zero()
    identity = (2 * P2 + P4 - P16).is_zero()
    assert identity
    census = load_census()
    noninjective = []
    rows_checked = 0
    formula_rows = 0
    for key, row in census.items():
        rows_checked += 1
        formula_rows += row['eligible_formula'] == row['eligible_signed_tuples']
        if row['eligible_duplicate_excess'] or row['eligible_infinity']:
            noninjective.append(key)
    explained = {}
    vec = {2: 2, 4: 1, 16: -1}
    for key in sorted(noninjective):
        row = census[key]
        groups = defaultdict(list)
        for d in row['duplicate_witnesses']:
            groups[d['group']].append(d['witness'])
        common = set()
        diffs = Counter()
        for ws in groups.values():
            assert len(ws) == 2
            c = Counter()
            for mask, sign in ws[0]:
                c[mask] += 1 if sign == 0 else -1
            for mask, sign in ws[1]:
                c[mask] -= 1 if sign == 0 else -1
            d = {m: v for m, v in c.items() if v}
            proj = d == vec or d == {m: -v for m, v in vec.items()}
            diffs['+-(2e_w + e_w2 - e_w4)' if proj else json.dumps(sorted(d.items()))] += 1
            shared = set(m for m, _ in ws[0]) & set(m for m, _ in ws[1])
            common.update(shared - {2})
        explained['%s k=%d %s' % key] = {
            'eligible': row['eligible_signed_tuples'], 'distinct': row['prime_subgroup_distinct_targets'],
            'excess': row['eligible_duplicate_excess'], 'groups': len(groups),
            'multiplicities': dict(Counter(len(v) for v in groups.values())),
            'difference_classes': dict(diffs), 'common_masks': sorted(common),
            'excess_equals_4_times_common': row['eligible_duplicate_excess'] == 4 * len(common)}
    result = {'frobenius_chain_masks': [2, 4, 16], 'chain_x': ['w', 'w^2', 'w^4'],
              'tau_action_on_canonical_lifts': tau_signs,
              'identity': '2 P_w + P_(w^2) - P_(w^4) = O (canonical signs)', 'identity_verified': identity,
              'census_rows_checked': rows_checked, 'formula_matches': formula_rows,
              'noninjective_rows': ['%s k=%d %s' % k for k in sorted(noninjective)],
              'explanations': explained}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'frobenius-collisions.json').write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'explanations'}, indent=1))


# ---------------------------------------------------------------- rank
def rank_mod_ell(rows, ncols):
    """Rank over GF(ELL) by streaming elimination; rows are dicts col -> int."""
    ell = m83.ELL
    pivots = {}
    for row in rows:
        v = [0] * ncols
        for c, x in row.items():
            v[c] = x % ell
        for c in range(ncols):
            if not v[c]:
                continue
            if c in pivots:
                p = pivots[c]
                f = v[c]
                v = [(a - f * b) % ell for a, b in zip(v, p)]
            else:
                inv = pow(v[c], -1, ell)
                pivots[c] = [(a * inv) % ell for a in v]
                break
        if len(pivots) == ncols:
            break
    return len(pivots)


def cmd_rank(args):
    out = {}
    for k in (5, 6, 7):
        basis = [m83.enc(u) for u in r1.coordinate_basis(k, 'polynomial')]
        table = f83lib.ratx(1, basis)
        masks = [m for m in range(1 << k) if table[m]]
        col = {m: i for i, m in enumerate(masks)}
        xs = []
        for m in masks:
            v = 0
            for i in range(k):
                if m >> i & 1:
                    v ^= basis[i]
            xs.append(v)
        ys, tags = f83lib.points(1, xs)
        st = f83lib.image(1, xs, ys, tags, 3, dup_cap=4096, targets_cap=1 << 22)

        def vec(wid):
            d = Counter()
            for i, s in f83lib.unpack_id(wid, 3):
                d[i] += 1 if s == 0 else -1
            return dict(d)
        rows = [vec(w) for w in st['target_witnesses']]
        rng = random.Random(k)
        rng.shuffle(rows)
        base_rank = rank_mod_ell(rows, len(masks))
        dup_rows = [vec(w) for _, w in st['duplicates']]
        with_dups = rank_mod_ell(rows + dup_rows, len(masks))
        groups = defaultdict(list)
        for g, w in st['duplicates']:
            groups[g].append(vec(w))
        diffs = []
        for ws in groups.values():
            d = Counter(ws[0])
            d.subtract(ws[1])
            diffs.append({c: v for c, v in d.items() if v})
        diff_rank = rank_mod_ell(diffs, len(masks))
        ident = {col[2]: 2, col[4]: 1, col[16]: -1}
        projective = all(d == ident or d == {c: -v for c, v in ident.items()} for d in diffs)
        out[str(k)] = {'x_columns': len(masks), 'distinct_targets': st['prime_subgroup_distinct_targets'],
                       'rank_one_witness_per_target': base_rank, 'rank_with_all_duplicates': with_dups,
                       'duplicate_rows': len(dup_rows), 'duplicate_difference_rank': diff_rank,
                       'differences_projectively_equal_identity': projective}
        print(k, out[str(k)], flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'frobenius-duplicate-rank.json').write_text(json.dumps(out, indent=1) + '\n')


# ---------------------------------------------------------------- regularity helpers
def top_components(S, eqs):
    return [S({e: c for e, c in f.dict().items() if sum(e) == f.degree()}) for f in eqs]


def top_fingerprint(S, eqs):
    """Canonical GF(2) row space of the top homogeneous components: (rank, sha256)."""
    tops = top_components(S, eqs)
    mons = sorted(set().union(*(set(t.dict()) for t in tops)), key=lambda e: (sum(e), e))
    index = {mono: i for i, mono in enumerate(mons)}
    pivots = {}
    for t in tops:
        row = sum(1 << index[mono] for mono in t.dict())
        while row:
            p = row.bit_length() - 1
            if p not in pivots:
                pivots[p] = row
                break
            row ^= pivots[p]
    for p in sorted(pivots):
        for q in sorted(pivots):
            if q > p and (pivots[q] >> p) & 1:
                pivots[q] ^= pivots[p]
    canon = sorted(tuple(sorted(tuple(int(e) for e in mons[i]) for i in range(row.bit_length()) if row >> i & 1))
                   for row in pivots.values())
    return len(pivots), hashlib.sha256(json.dumps(canon).encode()).hexdigest()


def formal_regularity(S, eqs, cap):
    if any(f == 1 for f in eqs):
        return {'degree_of_regularity': 0, 'top_quotient_dimension': 0, 'unit': True}
    H = S.ideal(top_components(S, eqs))
    try:
        alarm(cap)
        G = H.groebner_basis(algorithm='libsingular:std')
        H.groebner_basis.set_cache(G)
        nb = H.normal_basis()
        return {'degree_of_regularity': 0 if not nb else 1 + max(int(mono.degree()) for mono in nb),
                'top_quotient_dimension': len(nb), 'unit': False}
    except AlarmInterrupt:
        return {'degree_of_regularity': None, 'censored': True, 'cap_cpu_seconds': cap}
    finally:
        cancel_alarm()


def fake_domain(basis, allowed):
    return {'basis': basis, 'lifts': {int(mask): () for mask in allowed}}


def anf_degree(allowed, k):
    table = [int(mask not in allowed) for mask in range(1 << k)]
    for i in range(k):
        for mask in range(1 << k):
            if mask >> i & 1:
                table[mask] ^= table[mask ^ (1 << i)]
    return max((bin(mask).count('1') for mask, c in enumerate(table) if c), default=0)


def system_stats(b, target_x, basis, allowed, k, cap):
    S, raw, _ = r1.make_equations(b, target_x, fake_domain(basis, allowed), k)
    reduced, _ = r1.row_reduce(S, raw)
    rank, fp = top_fingerprint(S, raw)
    raw_reg = formal_regularity(S, raw, cap)
    red_reg = formal_regularity(S, reduced, cap)
    return {'raw_top_rank': rank, 'raw_top_sha256': fp,
            'raw_degree_of_regularity': raw_reg['degree_of_regularity'],
            'raw_top_quotient_dimension': raw_reg.get('top_quotient_dimension'),
            'row_reduced_degree_of_regularity': red_reg['degree_of_regularity'],
            'row_reduced_top_quotient_dimension': red_reg.get('top_quotient_dimension'),
            'row_reduced_has_unit': red_reg.get('unit', False),
            'censored': bool(raw_reg.get('censored') or red_reg.get('censored'))}


# ---------------------------------------------------------------- exhaust
def select_curves():
    """E0 plus five descendants chosen from the census by fixed rules."""
    solver = load_solver_census()
    census = load_census()
    e0 = census[('E0', 4, 'polynomial')]
    desc = [row for (c, k, p), row in census.items() if k == 4 and p == 'polynomial' and c != 'E0']
    same = [r for r in desc if r['x_count'] == e0['x_count']]
    key = lambda r: (r['prime_subgroup_distinct_targets'], r['curve_id'])
    picks = {'E0': 'original'}
    picks[max(same, key=key)['curve_id']] = 'same rational-x count as E0, maximum coverage'
    picks[min(same, key=key)['curve_id']] = 'same rational-x count as E0, minimum nonzero coverage' \
        if min(same, key=key)['prime_subgroup_distinct_targets'] else 'same rational-x count as E0, minimum coverage'
    picks.setdefault(max(desc, key=key)['curve_id'], 'largest k=4 polynomial coverage')

    def sampled(cid):
        ds = [c.get('degree_of_regularity') for c in solver[cid]['cells']
              if c['kind'] == 'satisfiable' and c.get('degree_of_regularity') is not None]
        return max(ds) if ds else None
    low = sorted((r for r in desc if sampled(r['curve_id']) == 3), key=key)
    if low:
        picks.setdefault(low[-1]['curve_id'], 'sampled dreg-3 representative with the most targets')
    picks.setdefault('O00-00', 'orbit O00 representative')
    return picks


def cmd_exhaust(args):
    picks = select_curves()
    inventory = {c['curve_id']: c for c in m83.load_inventory()}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ('target-exhaustion-%d.jsonl' % args.shard_index)
    if path.exists():
        raise ValueError('refusing to overwrite')
    jobs = 0
    with path.open('w') as f:
        for cid, reason in picks.items():
            curve = inventory[cid]
            b = m83.dec(curve['b'])
            E = m83.curve(b)
            domain = r1.factor_domain(E, 4, 'polynomial')
            image = r1.enumerate_image(domain)
            by_x = defaultdict(list)
            for x, y in image['image']:
                by_x[x].append(y)
            for tx in sorted(by_x):
                jobs += 1
                if jobs % args.shards != args.shard_index:
                    continue
                st = system_stats(b, m83.dec(tx), domain['basis'], set(domain['lifts']), 4, args.cap)
                f.write(json.dumps({'curve_id': cid, 'selection_reason': reason, 'target_x': str(tx),
                                    'points_with_this_x': len(by_x[tx]),
                                    'x_count': len(domain['lifts']), 'distinct_targets': len(image['image']),
                                    'distinct_target_x': len(by_x), **st}) + '\n')
                f.flush()
    print(json.dumps({'picks': picks, 'jobs': jobs}))


# ---------------------------------------------------------------- counterfactual
def cmd_counterfactual(args):
    solver = load_solver_census()
    anchor = solver['E0']
    k = 4
    basis = [m83.dec(x) for x in anchor['basis_integer_encodings']]
    allowed = frozenset(anchor['allowed_x_indices'])
    anchor_target = m83.dec(next(c['target_x'] for c in anchor['cells'] if c['kind'] == 'satisfiable'))
    inventory = m83.load_inventory()
    jobs = []
    if args.axis == 'coefficient':
        for c in inventory:
            jobs.append((c['curve_id'], m83.dec(c['b']), anchor_target, allowed, [c['curve_id']]))
    elif args.axis == 'membership':
        patterns = defaultdict(list)
        for cid, row in solver.items():
            patterns[tuple(row['allowed_x_indices'])].append(cid)
        for i, (pat, owners) in enumerate(sorted(patterns.items())):
            jobs.append(('M%04d' % i, m83.dec(1), anchor_target, frozenset(pat), owners))
    else:
        targets = defaultdict(list)
        for cid, row in solver.items():
            for cell in row['cells']:
                if cell['kind'] == 'satisfiable' and cell.get('target_x'):
                    targets[cell['target_x']].append(cid)
        for i, (tx, owners) in enumerate(sorted(targets.items(), key=lambda t: int(t[0]))):
            jobs.append(('T%05d' % i, m83.dec(1), m83.dec(tx), allowed, owners))
        if args.sample and len(jobs) > args.sample:
            jobs = sorted(random.Random(20260925).sample(jobs, args.sample), key=lambda j: j[0])
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ('counterfactual-%s-%d.jsonl' % (args.axis, args.shard_index))
    if path.exists():
        raise ValueError('refusing to overwrite')
    with path.open('w') as f:
        for i, (label, b, tx, allow, owners) in enumerate(jobs):
            if i % args.shards != args.shard_index:
                continue
            st = system_stats(b, tx, basis, allow, k, args.cap)
            f.write(json.dumps({'axis': args.axis, 'label': label, 'b': str(m83.enc(b)),
                                'target_x': str(m83.enc(tx)), 'allowed_x_count': len(allow),
                                'allowed_x_indices': sorted(allow), 'membership_anf_degree': anf_degree(allow, k),
                                'owners': owners[:8], 'owner_count': len(owners), 'counterfactual': True,
                                **st}) + '\n')
            f.flush()
    print(json.dumps({'axis': args.axis, 'jobs': len(jobs)}))


# ---------------------------------------------------------------- scaling (run-03)
def cmd_scaling(args):
    """One deterministic satisfiable target per selected curve at k = 5, 6, 7:
    raw and row-reduced formal regularity with CPU caps (censored cells stay null)."""
    picks = select_curves()
    inventory = {c['curve_id']: c for c in m83.load_inventory()}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ('selected-scaling-%d.jsonl' % args.shard_index)
    if path.exists():
        raise ValueError('refusing to overwrite')
    jobs = [(cid, k) for k in (5, 6, 7) for cid in picks]
    with path.open('w') as f:
        for i, (cid, k) in enumerate(jobs):
            if i % args.shards != args.shard_index:
                continue
            b = m83.dec(inventory[cid]['b'])
            E = m83.curve(b)
            domain = r1.factor_domain(E, k, 'polynomial')
            image = r1.enumerate_image(domain)
            if not image['image']:
                continue
            tx = min(image['image'])[0]
            st = system_stats(b, m83.dec(tx), domain['basis'], set(domain['lifts']), k, args.cap)
            f.write(json.dumps({'curve_id': cid, 'selection_reason': picks[cid], 'k': k, 'target_x': str(tx),
                                'x_count': len(domain['lifts']), 'distinct_targets': len(image['image']),
                                'cap_cpu_seconds': args.cap, **st}) + '\n')
            f.flush()
            print(json.dumps({'curve': cid, 'k': k, 'raw': st['raw_degree_of_regularity'],
                              'reduced': st['row_reduced_degree_of_regularity'], 'censored': st['censored']}),
                  flush=True)


# ---------------------------------------------------------------- k = 5 attribution of E0's low regularity
def cmd_k5attr(args):
    """E0 is the only k=5 panel curve below its membership-ANF stratum (degree 5 -> 11).
    Swap one factor at a time around E0's first satisfiable panel cell:
      coefficient: E0 membership and target, b from 24 deterministic floor curves;
      membership:  E0 b and target, the membership pattern of 24 degree-5 panel curves."""
    panel = {}
    for path in glob.glob(str(m83.OUT / 'run01-comparison' / 'panel-*.jsonl')):
        for line in open(path):
            r = json.loads(line)
            if r['k'] == 5:
                panel[r['curve_id']] = r
    e0 = panel['E0']
    k = 5
    basis = [m83.dec(x) for x in e0['basis_integer_encodings']]
    allowed = frozenset(e0['allowed_x_indices'])
    target = m83.dec(next(c['target_x'] for c in e0['cells'] if c['kind'] == 'satisfiable'))
    rng = random.Random(55)
    inventory = [c for c in m83.load_inventory() if c['curve_id'] != 'E0']
    jobs = [('E0-anchor', m83.dec(1), allowed, 'E0')]
    for c in rng.sample(inventory, 24):
        jobs.append(('coef:' + c['curve_id'], m83.dec(c['b']), allowed, c['curve_id']))
    deg5 = sorted(cid for cid, r in panel.items() if cid != 'E0' and anf_degree(set(r['allowed_x_indices']), k) == 5)
    for cid in rng.sample(deg5, min(24, len(deg5))):
        jobs.append(('memb:' + cid, m83.dec(1), frozenset(panel[cid]['allowed_x_indices']), cid))
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ('k5-attribution-%d.jsonl' % args.shard_index)
    with path.open('w') as f:
        for i, (label, b, allow, owner) in enumerate(jobs):
            if i % args.shards != args.shard_index:
                continue
            st = system_stats(b, target, basis, allow, k, args.cap)
            f.write(json.dumps({'label': label, 'owner': owner, 'b': str(m83.enc(b)), 'allowed_x_count': len(allow),
                                'membership_anf_degree': anf_degree(allow, k), **st}) + '\n')
            f.flush()
            print(label, st['raw_degree_of_regularity'], st['row_reduced_degree_of_regularity'], flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['collisions', 'rank', 'exhaust', 'counterfactual', 'select', 'scaling', 'k5attr'])
    ap.add_argument('--axis', choices=['coefficient', 'target', 'membership'])
    ap.add_argument('--shards', type=int, default=1)
    ap.add_argument('--shard-index', type=int, default=0)
    ap.add_argument('--cap', type=float, default=30)
    ap.add_argument('--sample', type=int, default=0)
    args = ap.parse_args()
    if args.command == 'select':
        print(json.dumps(select_curves(), indent=1))
        return
    {'collisions': cmd_collisions, 'rank': cmd_rank, 'exhaust': cmd_exhaust,
     'counterfactual': cmd_counterfactual, 'scaling': cmd_scaling,
     'k5attr': cmd_k5attr}[args.command](args)


if __name__ == '__main__':
    main()
