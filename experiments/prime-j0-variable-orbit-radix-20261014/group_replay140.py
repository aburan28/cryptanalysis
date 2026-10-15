#!/usr/bin/env python3
"""Independent affine secp256k1 replay of the 17-position 140-tau format."""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('radix_140_screen', HERE / 'screen140.py')
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)
reference = screen.nearest.model.reference
canonical, encode = screen.orbit.canonical, screen.orbit.encode


def main():
    digits = screen.digits()
    seeds = sorted({canonical(pair) for pair in digits})
    seeds.remove((0, 0))
    seeds.insert(0, (0, 0))
    seed_index = {pair: index for index, pair in enumerate(seeds)}
    codes = [(seed_index[canonical(pair)], *encode(pair, canonical(pair)))
             for pair in digits]
    source = screen.EXPERIMENTS / 'prime-j0-mixed640-materialized-tree-20261013' / 'selective-holdout.json'
    cases = json.loads(source.read_text())['cases']
    order = screen.nearest.model.mixed.screen.ORDER
    fresh_seed = b'nearest-orbit-19183-fresh-v1'
    fresh = [int.from_bytes(sha256(fresh_seed+i.to_bytes(4, 'big')).digest(),
                            'big') % order for i in range(256)]
    fresh += [0, 1, order-1, 1 << 255]
    scalars = [int(case['scalar_hex'], 16) % order for case in cases] + fresh

    bases = []
    base = reference.G
    for _ in range(screen.STEPS):
        bases.append((base, reference.tau_point(base)))
        base = reference.add(reference.multiply(screen.T, base),
                             reference.negate(reference.tau_point(base)))
    terminal_base = (base, reference.tau_point(base))
    point_cache = {}
    terminal_cache = {}
    digest = sha256()
    nonzero = 0
    unit_calls = 0

    def seed_point(window, index):
        if index == 0:
            return None
        key = window, index
        if key not in point_cache:
            a, b = seeds[index]
            window_base, tau_base = bases[window]
            point_cache[key] = reference.add(reference.multiply(a, window_base),
                                              reference.multiply(b, tau_base))
        return point_cache[key]

    for scalar in scalars:
        state = screen.nearest.model.mixed.screen.representative(scalar)
        total = None
        for window in range(screen.STEPS):
            state, digit = screen.step(state, digits)
            residue = (digit[0]+screen.T*digit[1]) % screen.Q
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
        assert total == reference.multiply(scalar, reference.G)
        if total is None:
            digest.update(bytes(64))
        else:
            digest.update(total[0].to_bytes(32, 'big'))
            digest.update(total[1].to_bytes(32, 'big'))

    return {
        'schema': 1,
        'radix': [screen.T, -1], 'positions': screen.STEPS,
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
