#!/usr/bin/env python3
"""Prepare independently replayable cases for the exact fused Metal benchmark."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from artifact_reference import decode, table
from fused_reference import exactPair, inputDigest, resultBytes
import run_walk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import table_store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--artifact-dir', type=Path, required=True)
    parser.add_argument('--branches', type=int, choices=(128,), default=128)
    parser.add_argument('--cases', type=int, default=4096)
    parser.add_argument('--seed', type=int, default=20260921)
    parser.add_argument('--repeats', type=int, default=7)
    parser.add_argument('--warmups', type=int, default=2)
    parser.add_argument('--inner-iterations', type=int, default=64)
    args = parser.parse_args()
    if (not 1 <= args.cases <= 262144 or not 1 <= args.repeats <= 100 or
            not 0 <= args.warmups <= 20 or not 1 <= args.inner_iterations <= 1024):
        parser.error('invalid benchmark bounds')

    catalog, base = table_store.load_catalog(None)
    entry = next(item for item in catalog['artifacts'] if item['branches'] == args.branches)
    config = {'lanes': args.cases, 'cycles': 1, 'launches': 1,
              'branches': args.branches, 'dpCap': 1, 'batch': 16,
              'dpWeight': -1, 'seed': args.seed, 'progressEvery': 1}
    reference = run_walk.prepare(args.out, entry, catalog, base,
                                 args.artifact_dir, config)

    pairPath = args.artifact_dir / 'pairs.bin'
    pairItem = next(item for item in entry['files'] if item['name'] == 'pairs.bin')
    if not pairPath.is_file() or pairPath.stat().st_size != pairItem['bytes']:
        raise ValueError('pair payload size differs from the catalog')
    pairFile = pairPath.open('rb')
    states, expected, indices = [], [], []
    sampleHash = hashlib.sha256()
    rejected = 0
    candidate = 0
    try:
        while len(states) < args.cases:
            seed = args.seed + candidate
            candidate += 1
            state = reference.initial(seed)
            reference.cycle(state, 0, 1, -1)
            for _ in range(table.mix64(seed ^ 0x66757365642d7631) & 3):
                reference.cycle(state, 0, 1, -1)
                if state['mode'] != 0:
                    break
            if state['mode'] != 0:
                rejected += 1
                continue
            raw = reference.serialize(state)
            outcome = exactPair(
                reference, raw,
                lambda u, v: reference.curve.add(reference.points[u], reference.points[v]))
            if not outcome['fused']:
                rejected += 1
                continue
            index = outcome['pairIndex']
            packed = os.pread(pairFile.fileno(), 36, 36 * index)
            if len(packed) != 36:
                raise ValueError('short pair-table sample')
            if decode(packed) != reference.curve.add(
                    reference.points[outcome['first']], reference.points[outcome['second']]):
                raise ValueError('pair-table sample differs from independent directions')
            sampleHash.update(index.to_bytes(8, 'little'))
            sampleHash.update(packed)
            final = reference.deserialize(outcome['state'])
            states.append(raw)
            expected.append(resultBytes(reference, final, outcome['first'], outcome['second']))
            indices.append(index)
    finally:
        pairFile.close()

    (args.out / 'fused-input.bin').write_bytes(b''.join(states))
    (args.out / 'fused-expected.bin').write_bytes(b''.join(expected))
    result = {
        'schema': 'ecc2k130-fused-benchmark-input-v1',
        'scope': 'public synthetic exact two-step benchmark',
        'cases': args.cases, 'branches': args.branches, 'seed': args.seed,
        'repeats': args.repeats, 'warmups': args.warmups,
        'innerIterations': args.inner_iterations,
        'logicalUpdatesPerCase': 2, 'runtimeAdditionsPerCase': 2,
        'pairLookupsPerCase': 1, 'rejectedCandidates': rejected,
        'maximumStateWarmupUpdates': 3,
        'inputSha256': inputDigest(states),
        'expectedSha256': hashlib.sha256(b''.join(expected)).hexdigest(),
        'pairSampleSha256': sampleHash.hexdigest(),
        'pairIndexMin': min(indices), 'pairIndexMax': max(indices),
        'uniquePairIndices': len(set(indices)),
        'pairPayloadBytes': pairItem['bytes'],
        'pairPayloadSha256': pairItem['sha256'],
        'directionsSha256': table_store.digest(args.out / 'directions.bin')}
    (args.out / 'fused-config.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
