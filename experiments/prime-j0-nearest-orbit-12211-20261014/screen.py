#!/usr/bin/env python3
"""Exact six-unit quotient of the norm-12211 nearest-digit point tables."""
import importlib.util
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'prime-j0-nearest-digit-12211-20261014'
SPEC = importlib.util.spec_from_file_location('nearest_12211_screen', PARENT / 'screen.py')
nearest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nearest)


def omega(pair):
    a, b = pair
    return a + 3*b, -a - 2*b


def images(pair):
    value = pair
    for power in range(3):
        yield value, power, 0
        yield (-value[0], -value[1]), power, 1
        value = omega(value)


def canonical(pair):
    return min(value for value, _, _ in images(pair))


def encode(pair, seed):
    for value, power, sign in images(seed):
        if value == pair:
            return power, sign
    raise AssertionError((pair, seed))


def digest_pairs(pairs):
    h = sha256()
    for a, b in pairs:
        h.update(a.to_bytes(2, 'big', signed=True))
        h.update(b.to_bytes(2, 'big', signed=True))
    return h.hexdigest()


def run():
    digits = nearest.digits()
    assert len(digits) == 12211
    assert all(digits[(12100*r) % 12211] == omega(digits[r])
               for r in range(12211))
    digit_seeds = sorted({canonical(pair) for pair in digits})
    digit_seeds.remove((0, 0))
    digit_seeds.insert(0, (0, 0))
    digit_index = {pair: index for index, pair in enumerate(digit_seeds)}
    digit_codes = [(digit_index[canonical(pair)], *encode(pair, canonical(pair)))
                   for pair in digits]
    assert all(tuple(images(digit_seeds[index]))[2*power+sign][0] == digits[r]
               for r, (index, power, sign) in enumerate(digit_codes))
    assert all(nearest.norm(*pair) <= 3997 for pair in digits)
    terminal = [(a, b) for a in range(-67, 68) for b in range(-67, 68)
                if nearest.norm(a, b) < 34*34]
    terminal_seeds = sorted({canonical(pair) for pair in terminal})
    terminal_seeds.remove((0, 0))
    terminal_seeds.insert(0, (0, 0))
    assert all(any(value == pair for value, _, _ in images(canonical(pair)))
               for pair in terminal)
    assert Counter(Counter(canonical(pair) for pair in digits).values()) == {6: 2035, 1: 1}
    assert len(digit_seeds) == 2036 and len(terminal_seeds) == 699
    assert len(terminal) == 4189
    # Stored points alone. Native metadata must be charged in a later overlay.
    point_payload = (18*len(digit_seeds)+len(terminal_seeds))*64
    h = sha256()
    for index, power, sign in digit_codes:
        h.update(index.to_bytes(2, 'big'))
        h.update(bytes([2*power+sign]))
    return {
        'schema': 1,
        'radix': [112, -1], 'radix_norm': 12211, 'positions': 18,
        'omega_coefficients': [[1, 3], [-1, -2]],
        'digit_residue_count': len(digits),
        'digit_orbit_count': len(digit_seeds),
        'digit_orbit_multiplicities': {'six': 2035, 'one': 1},
        'terminal_radius': 34, 'terminal_full_count': len(terminal),
        'terminal_orbit_count': len(terminal_seeds),
        'point_payload_bytes': point_payload,
        'point_payload_saved_vs_nearest_sign_table':
            7168192-point_payload,
        'digit_map_bytes_if_u16_seed_u8_unit': 3*12211,
        'digit_seed_sha256': digest_pairs(digit_seeds),
        'terminal_seed_sha256': digest_pairs(terminal_seeds),
        'digit_code_sha256': h.hexdigest(),
        'parent_screen_sha256': sha256((PARENT/'screen.py').read_bytes()).hexdigest(),
        'source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'checks': ['all_residue_orbit_covariance', 'all_residue_code_replay',
                   'all_terminal_orbit_coverage', 'exact_orbit_multiplicities'],
    }


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True, indent=2))
