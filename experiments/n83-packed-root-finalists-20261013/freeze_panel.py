#!/usr/bin/env python3
"""Freeze 256 new public N83 points for a paired finalist study."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
CRYPTO = Path(os.environ.get('N83_CRYPTO_REPO',
    '/Volumes/SSD990/llm/tmp/n83-packed-root-crypto-20261013'))
ARITHMETIC = CRYPTO / 'experiments/koblitz-single-target-n83-20261006/freeze_target.py'
EXPECTED_SOURCE = '6c457ea592875f1a9260a52c9eb900b0a722d4d0489b3f1cb3c8b0224f94f32f'
SEED = b'n83-packed-root-finalists-256-points-20261013-v1'
COUNT = 256


def main():
    source_hash = hashlib.sha256(ARITHMETIC.read_bytes()).hexdigest()
    assert source_hash == EXPECTED_SOURCE
    spec = importlib.util.spec_from_file_location('n83_panel_arithmetic', ARITHMETIC)
    arithmetic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(arithmetic)
    previous = set()
    experiments = HERE.parent
    for folder in ('n83-compact-orbit-size-sweep-20261012',
                   'n83-compact-orbit-k900-20261012',
                   'n83-compact-orbit-k899-20261012',
                   'n83-packed-root-k900-20261013',
                   'n83-packed-root-capacity-20261013'):
        target_file = experiments / folder / 'target.jsonl'
        if target_file.exists():
            previous.add(tuple(map(int, json.loads(target_file.read_text()))))
    first_panel = experiments / 'n83-packed-root-panel-20261013/targets.jsonl'
    previous.update(tuple(map(int, json.loads(line)))
                    for line in first_panel.read_text().splitlines())
    second_panel = experiments / 'n83-packed-root-panel-16g-20261013/targets.jsonl'
    previous.update(tuple(map(int, json.loads(line)))
                    for line in second_panel.read_text().splitlines())
    rows = []
    seen = set()
    for index in range(COUNT):
        scalar_seed = hashlib.sha256(SEED + index.to_bytes(4, 'big')).digest()
        scalar = int.from_bytes(scalar_seed, 'big') % (arithmetic.R - 1) + 1
        point = arithmetic.scalar_mul(scalar, arithmetic.GENERATOR)
        assert point is not None and arithmetic.on_curve(point)
        assert arithmetic.scalar_mul(arithmetic.R, point) is None
        assert point not in previous and point not in seen
        seen.add(point)
        rows.append({'index': index, 'point': [str(point[0]), str(point[1])],
                     'scalar': str(scalar),
                     'scalar_seed_sha256': scalar_seed.hex()})
    public = ''.join(json.dumps(row['point'], separators=(',', ':')) + '\n' for row in rows)
    sidecar = {'kind': 'n83_a1_validation_only_panel_sidecar',
               'count': COUNT, 'seed_sha256': hashlib.sha256(SEED).hexdigest(),
               'arithmetic_source_sha256': source_hash, 'rows': rows}
    with (HERE / 'targets.jsonl').open('x') as out:
        out.write(public)
    with (HERE / 'validation_sidecar.json').open('x') as out:
        json.dump(sidecar, out, sort_keys=True, separators=(',', ':'))
        out.write('\n')
    print(json.dumps({'count': COUNT,
        'targets_sha256': hashlib.sha256(public.encode()).hexdigest(),
        'sidecar_sha256': hashlib.sha256((HERE / 'validation_sidecar.json').read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
