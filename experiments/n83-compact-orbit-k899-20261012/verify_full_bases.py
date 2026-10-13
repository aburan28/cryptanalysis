#!/usr/bin/env python3
"""Replay every new K899 base point and label independently."""

import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CRYPTO = Path(os.environ.get('N83_CRYPTO_REPO',
    '/Volumes/SSD990/llm/tmp/n83-base-size-crypto-20261012'))
ARITHMETIC = CRYPTO / 'experiments/koblitz-single-target-n83-20261006/freeze_target.py'
LAMBDA = 2998004823950457


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pair(row):
    return tuple(map(int, row))


def main():
    spec = importlib.util.spec_from_file_location('n83_base_replay_arithmetic', ARITHMETIC)
    arithmetic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(arithmetic)
    assert sha(ARITHMETIC) == '6c457ea592875f1a9260a52c9eb900b0a722d4d0489b3f1cb3c8b0224f94f32f'
    assert arithmetic.scalar_mul(arithmetic.R, arithmetic.GENERATOR) is None
    assert arithmetic.scalar_mul(LAMBDA, arithmetic.GENERATOR) == tuple(
        arithmetic.gf_square(word) for word in arithmetic.GENERATOR)
    assert pow(LAMBDA, 83, arithmetic.R) == 1
    started = time.monotonic()
    records = []
    for k in (899,):
        path = HERE / 'runs' / f'K{k}' / 'base.jsonl'
        base = json.loads(path.read_text())
        reps = base['factor_base_representatives']
        points = base['factor_base_point_coordinates']
        labels = base['factor_base_point_labels']
        assert len(reps) == k and len(points) == len(labels) == 166 * k
        seen = set()
        for column, encoded_rep in enumerate(reps):
            rep = pair(encoded_rep)
            assert arithmetic.on_curve(rep)
            assert arithmetic.scalar_mul(arithmetic.R, rep) is None
            orbit = []
            current = rep
            coefficient = 1
            for power in range(83):
                negative = (current[0], current[0] ^ current[1])
                index = 166 * column + 2 * power
                assert pair(points[index]) == current
                assert pair(points[index + 1]) == negative
                assert list(map(int, labels[index])) == [column, coefficient]
                assert list(map(int, labels[index + 1])) == [column, (-coefficient) % arithmetic.R]
                assert arithmetic.on_curve(current) and arithmetic.on_curve(negative)
                orbit.extend((current, negative))
                current = (arithmetic.gf_square(current[0]), arithmetic.gf_square(current[1]))
                coefficient = coefficient * LAMBDA % arithmetic.R
            assert current == rep and coefficient == 1
            assert len(set(orbit)) == 166
            canonical = min(orbit)
            assert canonical not in seen
            seen.add(canonical)
        records.append({'K': k, 'base_sha256': sha(path), 'representatives_checked': k,
                        'point_and_label_rows_checked': 166 * k,
                        'distinct_signed_frobenius_orbits': len(seen)})
    receipt = {'status': 'PASS', 'scope': 'all dumped points, labels, subgroup reps, and orbit closure',
               'independent_arithmetic_sha256': sha(ARITHMETIC),
               'records': records, 'elapsed_s': time.monotonic() - started}
    with (HERE / 'full_base_replay.json').open('x') as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write('\n')
    print(json.dumps({'status': receipt['status'], 'records': records,
                      'elapsed_s': receipt['elapsed_s']}))


if __name__ == '__main__':
    main()
