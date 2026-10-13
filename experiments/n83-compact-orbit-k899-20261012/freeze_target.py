#!/usr/bin/env python3
"""Freeze a fresh public point for the nested N83 compact-orbit base screen."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
CRYPTO = Path(os.environ.get('N83_CRYPTO_REPO',
    '/Volumes/SSD990/llm/tmp/n83-base-size-crypto-20261012'))
ARITHMETIC = CRYPTO / 'experiments/koblitz-single-target-n83-20261006/freeze_target.py'
EXPECTED_SOURCE = '6c457ea592875f1a9260a52c9eb900b0a722d4d0489b3f1cb3c8b0224f94f32f'
SEED = b'n83-compact-orbit-k899-third-public-point-20261012-v1'


def create_once(path, data):
    with path.open('xb') as stream:
        stream.write(data)


def main():
    source = ARITHMETIC.read_bytes()
    source_hash = hashlib.sha256(source).hexdigest()
    assert source_hash == EXPECTED_SOURCE, source_hash
    spec = importlib.util.spec_from_file_location('n83_independent_arithmetic', ARITHMETIC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    scalar = int.from_bytes(hashlib.sha256(SEED).digest(), 'big') % (module.R - 1) + 1
    point = module.scalar_mul(scalar, module.GENERATOR)
    assert point is not None and module.on_curve(point)
    assert module.scalar_mul(module.R, point) is None
    target = (json.dumps([str(point[0]), str(point[1])], separators=(',', ':')) + '\n').encode()
    sidecar = (json.dumps({
        'kind': 'n83_a1_validation_only_sidecar',
        'scalar': str(scalar),
        'point': [str(point[0]), str(point[1])],
        'seed_sha256': hashlib.sha256(SEED).hexdigest(),
        'arithmetic_source_sha256': source_hash,
    }, sort_keys=True, separators=(',', ':')) + '\n').encode()
    create_once(HERE / 'target.jsonl', target)
    create_once(HERE / 'validation_sidecar.json', sidecar)
    print(json.dumps({'target_sha256': hashlib.sha256(target).hexdigest(),
                      'sidecar_sha256': hashlib.sha256(sidecar).hexdigest()}))


if __name__ == '__main__':
    main()
