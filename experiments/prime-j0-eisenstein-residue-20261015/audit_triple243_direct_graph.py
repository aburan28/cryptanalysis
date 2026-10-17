#!/usr/bin/env python3
"""Reconstruct first radix-243 Q graph and tally direct point additions."""
from hashlib import sha256
import json
from pathlib import Path

from check_secp256k1_tau_generator import N, LAMBDA

HERE = Path(__file__).resolve().parent
RADIX = 58807


def digest(data):
    return sha256(data).hexdigest()


def norm(pair):
    a, b = pair
    return a*a + 3*a*b + 3*b*b


def dot2(left, right):
    a, b = left
    c, d = right
    return 2*a*c + 3*(a*d+b*c) + 6*b*d


def nearest(numerator, denominator):
    whole, remainder = divmod(abs(numerator), denominator)
    value = whole + (2*remainder > denominator)
    return value if numerator >= 0 else -value


def lattice_basis():
    first, second = (N, 0), (-LAMBDA, 1)
    while True:
        if norm(second) < norm(first):
            first, second = second, first
        coefficient = nearest(dot2(first, second), 2*norm(first))
        if coefficient == 0:
            return first, second
        second = (second[0]-coefficient*first[0],
                  second[1]-coefficient*first[1])


def split_scalar(scalar):
    first, second = lattice_basis()
    determinant = first[0]*second[1] - first[1]*second[0]
    sign = 1 if determinant > 0 else -1
    center_a = sign*nearest(scalar*second[1], abs(determinant))
    center_b = -sign*nearest(scalar*first[1], abs(determinant))
    candidates = []
    for i in range(center_a-3, center_a+4):
        for j in range(center_b-3, center_b+4):
            a = scalar-i*first[0]-j*second[0]
            b = -i*first[1]-j*second[1]
            candidates.append((norm((a, b)), a, b))
    _, a, b = min(candidates)
    assert (a + LAMBDA*b - scalar) % N == 0
    assert norm((a, b)) <= 7*2**260
    return a, b


def omega(pair):
    a, b = pair
    return a+3*b, -a-2*b


def orbit(pair):
    variants = []
    for _ in range(3):
        variants.extend((pair, (-pair[0], -pair[1])))
        pair = omega(pair)
    return variants


def nearest_digit(residue):
    if residue > RADIX//2:
        residue -= RADIX
    candidates = []
    for lift_number in range(-2, 3):
        lift = residue+lift_number*RADIX
        center = 485*lift//(2*RADIX)
        for b in range(center-2, center+3):
            a = lift-244*b
            candidates.append((norm((a, b)), abs(b), abs(a), a, b))
    _, _, _, a, b = min(candidates)
    assert norm((a, b)) < RADIX
    return a, b


def recode(scalar):
    a, b = split_scalar(scalar)
    digits = []
    for _ in range(16):
        da, db = nearest_digit((a+244*b) % RADIX)
        digits.append((da, db))
        shifted_a, shifted_b = a-da, b-db
        next_a = 241*shifted_a-3*shifted_b
        next_b = shifted_a+244*shifted_b
        assert next_a % RADIX == next_b % RADIX == 0
        a, b = next_a//RADIX, next_b//RADIX
    assert norm((a, b)) < 5000
    return digits + [(a, b)]


def bits(pair):
    return sum(bin(abs(value)).count('1') for value in pair)


def graph_rows(seeds):
    seen = set()
    rows = []
    for seed in seeds:
        operation = 'direct'
        unit_deltas = [(1, 0), (0, 1), (-1, 0), (0, -1)]
        power_deltas = [delta for bit in range(9)
                        for base in ((1 << bit, 0), (0, 1 << bit))
                        for delta in orbit(base)]
        if any((seed[0]-delta[0], seed[1]-delta[1]) in seen
               for delta in unit_deltas + power_deltas):
            operation = 'step'
        elif any((seed[0]-p[0], seed[1]-p[1]) in seen
                 for p in seen):
            operation = 'sum'
        canonical = min(orbit(seed))
        canonical_adds = 0 if canonical == (-2, 1) else bits(canonical)-1
        orbit_adds = bits(seed)-1
        rows.append({'seed': seed, 'operation': operation,
                     'canonical_seed': canonical,
                     'canonical_direct_adds': canonical_adds,
                     'orbit_direct_adds': orbit_adds})
        seen.update(orbit(seed))
    return rows


def policy(digit_rows, low_weight_nodes):
    def key(digit):
        variants = orbit(digit)
        return min(variants, key=lambda item: (bits(item), item)) \
            if low_weight_nodes else min(variants)
    seeds = sorted({key(digit) for row in digit_rows for digit in row
                    if digit != (0, 0)})
    rows = graph_rows(seeds)
    direct = [row for row in rows if row['operation'] == 'direct']
    edges = len(rows)-len(direct)
    direct_adds = sum(min(bits(value) for value in orbit(tuple(row['seed'])))-1
                      for row in direct)
    rotations = 0 if low_weight_nodes else sum(
        tuple(row['seed']) != min(orbit(tuple(row['seed'])),
                                  key=lambda item: (bits(item), item))
        for row in direct)
    return {'rows': rows, 'nodes': len(rows), 'graph_edges': edges,
            'direct_seeds': len(direct), 'direct_adds': direct_adds,
            'modeled_graph_adds': edges+direct_adds,
            'modeled_direct_rotations': rotations}


def main():
    fixture_path = HERE / 'rho-restart-first128-fixture.json'
    replay_path = HERE / 'triple243-local-replay.json'
    fixture = json.loads(fixture_path.read_bytes())
    replay = json.loads(replay_path.read_bytes())
    scalar = int(fixture['cases'][0]['b_hex'], 16)
    digits = recode(scalar)
    one = {'canonical': policy([digits], False),
           'low_weight': policy([digits], True)}
    batch_digits = [recode(int(row['b_hex'], 16))
                    for row in fixture['cases'][:128]]
    batch = {'canonical': policy(batch_digits, False),
             'low_weight': policy(batch_digits, True)}
    for options, count in ((one, 1), (batch, 128)):
        selected = min(options, key=lambda name: (
            options[name]['modeled_graph_adds'],
            options[name]['modeled_direct_rotations']))
        options['selected'] = selected
        native = next(row for row in replay['results']
                      if row['fixture'] == 'frozen' and row['count'] == count)
        chosen = options[selected]
        assert (chosen['nodes'], chosen['graph_edges'], chosen['direct_seeds']) == (
            native['constructed_q_points'], native['graph_edges'],
            native['direct_seeds'])
    assert one['selected'] == 'low_weight'
    assert batch['selected'] == 'canonical'
    rows = one['low_weight']['rows']
    old = sum(row['canonical_direct_adds'] for row in rows
              if row['operation'] == 'direct')
    new = sum(row['orbit_direct_adds'] for row in rows
              if row['operation'] == 'direct')
    first = replay['results'][0]
    assert first['fixture'] == 'frozen' and first['count'] == 1
    assert (len(rows), sum(r['operation'] != 'direct' for r in rows),
            sum(r['operation'] == 'direct' for r in rows)) == (17, 1, 16)
    assert (len(rows), first['graph_edges'], first['direct_seeds']) == (17, 1, 16)
    assert (old, new) == (112, 64)
    receipt = {
        'schema': 1, 'status': 'source_formula_audit',
        'fixture_sha256': digest(fixture_path.read_bytes()),
        'native_replay_sha256': digest(replay_path.read_bytes()),
        'source_sha256': {name: digest((HERE / name).read_bytes()) for name in
                          ('joint_norm58807.rs', 'check_secp256k1_tau_generator.py')},
        'scalar_b_hex': fixture['cases'][0]['b_hex'],
        'digits': digits, 'graph_rows': rows,
        'policy_options': {label: {name: {
            key: value for key, value in option.items() if key != 'rows'}
            if name != 'selected' else option
            for name, option in options.items()}
            for label, options in (('one', one), ('batch128', batch))},
        'canonical_direct_adds': old, 'orbit_direct_adds': new,
        'graph_edges': 1, 'direct_seeds': 16,
        'cost_boundary': 'group additions to construct direct Q seeds; excludes '
                         'rotations, power doublings, batch normalization and lookup',
    }
    output = HERE / 'triple243-direct-graph-audit.json'
    output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'ok': True, 'canonical_direct_adds': old,
                      'orbit_direct_adds': new}, sort_keys=True))


if __name__ == '__main__':
    main()
