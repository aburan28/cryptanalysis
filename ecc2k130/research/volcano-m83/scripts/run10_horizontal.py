"""Run-10: separable horizontal-isogeny graph and atlas on the conductor-6473 floor.

  graph    For split primes l in {11, 23, 29, 37, 43, 53} (all prime to the
           conductor), the classical modular polynomial Phi_l (PARI
           polmodular, reduced mod 2 and hash-pinned) is specialised at every
           floor j.  Each vertex must have exactly two F_(2^83) roots, both in
           the floor inventory; the resulting 2-regular graph is compared with
           the order of the class of a prime above l in the cyclic class group
           Cl(O_6473) of order 6474.
  maps     Explicit degree-11 maps (Sage isogenies_prime_degree) from the
           shift-00 curve of every orbit in the 11-cycle through the reference
           descendant; Frobenius conjugates give every edge of that cycle.
  (the atlas transport over these maps is run10_atlas.py)

    sage -python run10_horizontal.py graph --shards 3 --shard-index I
    sage -python run10_horizontal.py graph-merge
    sage -python run10_horizontal.py maps
"""
import argparse
import glob
import hashlib
import json
import time
from collections import defaultdict

from sage.all import PolynomialRing, pari

import m83

OUT = m83.OUT / 'run10-horizontal'
PRIMES = [11, 23, 29, 37, 43, 53]
M = m83.M


def phi_mod2(l):
    """Support {(i, k)} of Phi_l(X, Y) mod 2 (coefficient of X^i Y^k odd)."""
    P = pari.polmodular(l)        # classical Phi_l in x (main variable) and y
    support = []
    for i, cy in enumerate(pari.Vecrev(P)):
        for k, c in enumerate(pari.Vecrev(cy)):
            if int(c) % 2:
                support.append((i, k))
    digest = hashlib.sha256(json.dumps(sorted(support)).encode()).hexdigest()
    return support, digest


def neighbours(j, support, l, R):
    """F_(2^83)-roots of Phi_l(X, j) with multiplicity: gcd(X^q - X, f), then its roots."""
    powers = [j ** 0]
    for _ in range(l + 1):
        powers.append(powers[-1] * j)
    coeffs = [m83.FIELD.zero()] * (l + 2)
    for i, k in support:
        coeffs[i] += powers[k]
    f = R(coeffs)
    X = R.gen()
    rational = f.gcd(pow(X, m83.Q, f) - X)
    roots = rational.roots(multiplicities=False)
    return [(r, _multiplicity(f, r)) for r in roots]


def _multiplicity(f, r):
    e = 0
    X = f.parent().gen()
    while f(r) == 0:
        f = f // (X - r)
        e += 1
    return e


def cmd_graph(args):
    R = PolynomialRing(m83.FIELD, 'X')
    inv = m83.load_inventory()
    floor = [c for c in inv if c['curve_id'] != 'E0']
    byj = {c['j']: c['curve_id'] for c in floor}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ('graph-%d.jsonl' % args.shard_index)
    if path.exists():
        raise ValueError('refusing to overwrite')
    supports = {l: phi_mod2(l) for l in PRIMES}
    # Phi_l has F_2 coefficients, so the neighbours of O<o>-<s> are the 2^s-th
    # powers of those of O<o>-00: compute every orbit representative exactly
    # and re-verify two further shifts per orbit directly.
    import random
    rng = random.Random(1010)
    jobs = []
    for o in range(m83.N_ORBITS):
        jobs.append('O%02d-00' % o)
        for s in rng.sample(range(1, M), 2):
            jobs.append('O%02d-%02d' % (o, s))
    byid = {c['curve_id']: c for c in floor}
    with path.open('w') as f:
        for n, cid in enumerate(jobs):
            if n % args.shards != args.shard_index:
                continue
            c = byid[cid]
            j = m83.dec(c['j'])
            row = {'curve_id': c['curve_id'], 'edges': {}}
            for l in PRIMES:
                roots = neighbours(j, supports[l][0], l, R)
                row['edges'][str(l)] = [[byj.get(str(m83.enc(r))), int(e)] for r, e in roots]
            f.write(json.dumps(row) + '\n')
            if n % 30 == 0:
                print(json.dumps({'vertex': n}), flush=True)


def cycles(adj):
    seen, comps = set(), []
    for v in adj:
        if v in seen:
            continue
        stack, comp = [v], 0
        seen.add(v)
        while stack:
            u = stack.pop()
            comp += 1
            for w in adj[u]:
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        comps.append(comp)
    return sorted(comps, reverse=True)


def parse(cid):
    o, s = cid[1:].split('-')
    return int(o), int(s)


def cmd_graph_merge(args):
    rows = {}
    for p in glob.glob(str(OUT / 'graph-*.jsonl')):
        for line in open(p):
            r = json.loads(line)
            rows[r['curve_id']] = r
    assert len(rows) == 3 * m83.N_ORBITS
    inv = json.loads((m83.OUT / 'inventory' / 'inventory.json').read_text())
    summary = {}
    adjacency = {}
    shifted = lambda cid, d: 'O%02d-%02d' % (parse(cid)[0], (parse(cid)[1] + d) % M)
    for l in PRIMES:
        adj = {}
        for o in range(m83.N_ORBITS):
            rep = rows['O%02d-00' % o]['edges'][str(l)]
            assert len(rep) == 2 and all(mult == 1 and nb is not None for nb, mult in rep), (o, l, rep)
            for s in range(M):
                adj['O%02d-%02d' % (o, s)] = [shifted(nb, s) for nb, _ in rep]
        sampled = 0
        for cid, r in rows.items():
            e = r['edges'][str(l)]
            assert len(e) == 2 and all(mult == 1 for _, mult in e)
            assert sorted(nb for nb, _ in e) == sorted(adj[cid]), (cid, l)
            sampled += 1
        for v, ws in adj.items():
            for w in ws:
                assert v in adj[w]
        comps = cycles(adj)
        # orbit-level action: O<o>-<s> -> O<o'>-<s + d>, independent of s
        action = defaultdict(set)
        for v, ws in adj.items():
            o, s = parse(v)
            for w in ws:
                o2, s2 = parse(w)
                action[o].add((o2, (s2 - s) % M))
        consistent = all(len(v) == 2 for v in action.values())
        summary[str(l)] = {'vertices': len(adj), 'edges': sum(len(v) for v in adj.values()) // 2,
                           'two_regular': True, 'components': len(comps), 'component_sizes': sorted(set(comps)),
                           'class_order': inv['ideal_class_orders'][str(l)],
                           'matches_class_order': set(comps) == {inv['ideal_class_orders'][str(l)]},
                           'orbit_action_shift_invariant': consistent,
                           'orbits_joined_per_component': inv['ideal_class_orders'][str(l)] // M,
                           'directly_specialised_vertices': sampled,
                           'phi_mod2_sha256': phi_mod2(l)[1]}
        adjacency[str(l)] = adj
        print(l, json.dumps(summary[str(l)]), flush=True)
    (OUT / 'horizontal-graph.json').write_text(json.dumps({'summary': summary}, indent=1) + '\n')
    (OUT / 'adjacency.json').write_text(json.dumps(adjacency) + '\n')


def reference_curve():
    sel = json.loads((m83.OUT / 'run04-explicit-descent' / 'selection.json').read_text())
    return sel['selected'][0]['curve_id']


def cycle_order(adj, start):
    """Vertices of start's cycle in walking order."""
    order = [start]
    prev, cur = None, start
    while True:
        nxt = [w for w in adj[cur] if w != prev][0]
        if nxt == start:
            break
        order.append(nxt)
        prev, cur = cur, nxt
    return order


def cmd_maps(args):
    adj = json.loads((OUT / 'adjacency.json').read_text())['11']
    ref = reference_curve()
    order = cycle_order(adj, ref)
    orbits = sorted({parse(v)[0] for v in order})
    inv = {c['curve_id']: c for c in m83.load_inventory()}
    seeds = {}
    for o in orbits:
        cid = 'O%02d-00' % o
        E = m83.curve(inv[cid]['b'])
        t0 = time.perf_counter()
        isos = E.isogenies_prime_degree(11)
        seconds = time.perf_counter() - t0
        assert len(isos) == 2
        maps = []
        for phi in isos:
            jt = str(m83.enc(phi.codomain().j_invariant()))
            target = [c for c, row in inv.items() if row['j'] == jt]
            assert len(target) == 1 and target[0] in adj[cid]
            tgt = m83.curve(inv[target[0]]['b'])
            psi = phi.codomain().isomorphism_to(tgt) * phi
            fx, fy = psi.rational_maps()
            maps.append({'target': target[0], 'kernel_degree': int(phi.kernel_polynomial().degree()),
                         'x_num': [str(m83.enc(c)) for c in fx.numerator().univariate_polynomial().list()],
                         'x_den': [str(m83.enc(c)) for c in fx.denominator().univariate_polynomial().list()],
                         'y_map': str(fy)})
        seeds[cid] = {'seconds': seconds, 'maps': maps}
        print(cid, [m['target'] for m in maps], round(seconds, 1), flush=True)
    (OUT / 'l11-seed-maps.json').write_text(json.dumps({'reference': ref, 'cycle_length': len(order),
                                                         'orbits': orbits, 'seeds': seeds}, indent=1) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['graph', 'graph-merge', 'maps'])
    ap.add_argument('--shards', type=int, default=1)
    ap.add_argument('--shard-index', type=int, default=0)
    args = ap.parse_args()
    {'graph': cmd_graph, 'graph-merge': cmd_graph_merge, 'maps': cmd_maps}[args.command](args)


if __name__ == '__main__':
    main()
