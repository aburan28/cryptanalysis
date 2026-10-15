#!/usr/bin/env python3
"""Recompute exact digit geometry for the norm-110557 radix."""

from hashlib import sha256
from math import isqrt
from pathlib import Path
import json

TAU_RESIDUE = 334
NORM = TAU_RESIDUE * TAU_RESIDUE - 3 * TAU_RESIDUE + 3
LIMIT = (NORM - 1) // 2
TERMINAL_COORD_LIMIT = 100
TERMINAL_NORM_LIMIT = 5000


def norm(a: int, b: int) -> int:
    return a*a + 3*a*b + 3*b*b


def omega(pair):
    a, b = pair
    return a + 3*b, -a - 2*b


def canonical(pair):
    values = []
    for _ in range(3):
        values.extend((pair, (-pair[0], -pair[1])))
        pair = omega(pair)
    return min(values)


def digit(residue: int):
    if residue == 0:
        return 0, 0
    best = None
    for lift in (residue, residue - NORM):
        center = ((2*TAU_RESIDUE - 3) * lift + NORM) // (2*NORM)
        for b in (center-1, center, center+1):
            a = lift - TAU_RESIDUE*b
            score = (norm(a,b), abs(b), abs(a), a, b)
            if best is None or score < best:
                best = score
    return best[3], best[4]


def main(output: Path):
    assert NORM == 110557
    assert all(NORM % d for d in range(2, isqrt(NORM)+1))
    digits = [digit(residue) for residue in range(LIMIT+1)]
    assert all((a + TAU_RESIDUE*b - residue) % NORM == 0
               for residue,(a,b) in enumerate(digits))
    assert all(norm(*omega(pair)) == norm(*pair) for pair in digits)
    digit_seeds = sorted({canonical(pair) for pair in digits})
    terminal = [(a,b) for a in range(-TERMINAL_COORD_LIMIT, TERMINAL_COORD_LIMIT+1)
                for b in range(-TERMINAL_COORD_LIMIT, TERMINAL_COORD_LIMIT+1)
                if norm(a,b) < TERMINAL_NORM_LIMIT]
    terminal_seeds = sorted({canonical(pair) for pair in terminal})
    result = {
        'schema': 1, 'tau_residue': TAU_RESIDUE, 'digit_prime_norm': NORM,
        'digit_steps': 15, 'digit_residue_count': len(digits),
        'digit_seed_count_including_zero': len(digit_seeds),
        'digit_max_norm': max(norm(*pair) for pair in digits),
        'terminal_coordinate_limit': TERMINAL_COORD_LIMIT,
        'terminal_norm_limit': TERMINAL_NORM_LIMIT,
        'terminal_point_count': len(terminal),
        'terminal_seed_count_including_zero': len(terminal_seeds),
        'terminal_max_norm': max(norm(*pair) for pair in terminal),
        'digit_seed_sha256': sha256(json.dumps(digit_seeds,separators=(',',':')).encode()).hexdigest(),
        'terminal_seed_sha256': sha256(json.dumps(terminal_seeds,separators=(',',':')).encode()).hexdigest(),
    }
    output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__ == '__main__':
    main(Path(__file__).resolve().parent/'alt-digit-geometry.json')
