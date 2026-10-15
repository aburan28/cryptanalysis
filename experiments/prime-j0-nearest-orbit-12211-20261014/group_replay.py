#!/usr/bin/env python3
"""Independent affine secp256k1 replay of the norm-12211 orbit table."""
import importlib.util
import json
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'prime-j0-nearest-digit-12211-20261014'
SPEC = importlib.util.spec_from_file_location('nearest_12211_screen', PARENT/'screen.py')
nearest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nearest)
reference = nearest.model.reference
ORBIT_SPEC = importlib.util.spec_from_file_location('orbit_12211_screen', HERE/'screen.py')
orbit_screen = importlib.util.module_from_spec(ORBIT_SPEC)
ORBIT_SPEC.loader.exec_module(orbit_screen)
canonical, encode = orbit_screen.canonical, orbit_screen.encode


def main():
    digits = nearest.digits()
    seeds = sorted({canonical(pair) for pair in digits})
    seeds.remove((0, 0)); seeds.insert(0, (0, 0))
    seed_index = {pair: index for index, pair in enumerate(seeds)}
    codes = [(seed_index[canonical(pair)], *encode(pair, canonical(pair)))
             for pair in digits]
    source = nearest.FIXTURE
    cases = json.loads(source.read_text())['cases']
    order = nearest.model.mixed.screen.ORDER
    fresh_seed = b'nearest-orbit-12211-fresh-v1'
    fresh = [int.from_bytes(sha256(fresh_seed+i.to_bytes(4, 'big')).digest(),
                            'big') % order for i in range(256)]
    fresh += [0, 1, order-1, 1 << 255]
    scalars = [int(case['scalar_hex'], 16) % order for case in cases] + fresh
    bases = []
    base = reference.G
    for _ in range(18):
        bases.append((base, reference.tau_point(base)))
        base = reference.add(reference.multiply(112, base),
                             reference.negate(reference.tau_point(base)))
    terminal_base = (base, reference.tau_point(base))
    point_cache = {}
    digest = sha256()
    unit_calls = 0
    nonzero = 0

    def seed_point(window, index):
        if index == 0:
            return None
        key = window, index
        if key not in point_cache:
            a, b = seeds[index]
            base, tau = bases[window]
            point_cache[key] = reference.add(reference.multiply(a, base),
                                              reference.multiply(b, tau))
        return point_cache[key]

    terminal_seeds = sorted({canonical((a, b)) for a in range(-67, 68)
                             for b in range(-67, 68)
                             if nearest.norm(a, b) < 34*34})
    terminal_seeds.remove((0, 0)); terminal_seeds.insert(0, (0, 0))
    terminal_cache = {}
    for scalar in scalars:
        state = nearest.model.mixed.screen.representative(scalar)
        total = None
        for window in range(18):
            state, digit = nearest.step(state, digits)
            residue = (digit[0]+112*digit[1]) % 12211
            index, power, sign = codes[residue]
            assert digit == digits[residue]
            point = seed_point(window, index)
            total = reference.add(total, reference.unit_point(point, 2*power+sign))
            unit_calls += int(index != 0 and power != 0)
            nonzero += int(index != 0)
        terminal_seed = canonical(state)
        power, sign = encode(state, terminal_seed)
        if terminal_seed != (0, 0):
            if terminal_seed not in terminal_cache:
                a, b = terminal_seed
                terminal_cache[terminal_seed] = reference.add(
                    reference.multiply(a, terminal_base[0]),
                    reference.multiply(b, terminal_base[1]))
            total = reference.add(total, reference.unit_point(
                terminal_cache[terminal_seed], 2*power+sign))
        expected = reference.multiply(scalar, reference.G)
        assert total == expected
        if total is None:
            digest.update(bytes(64))
        else:
            digest.update(total[0].to_bytes(32, 'big'))
            digest.update(total[1].to_bytes(32, 'big'))
    return {
        'schema': 1,
        'fixture_sha256': sha256(source.read_bytes()).hexdigest(),
        'frozen_case_count': len(cases),
        'fresh_seed': fresh_seed.decode(),
        'fresh_case_count': len(fresh),
        'independent_scalar_replays': len(scalars),
        'nonzero_digit_addends': nonzero,
        'nontrivial_digit_unit_actions': unit_calls,
        'touched_digit_seed_points': len(point_cache),
        'touched_terminal_seed_points': len(terminal_cache),
        'output_point_sha256': digest.hexdigest(),
        'source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
    }


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True, indent=2))
