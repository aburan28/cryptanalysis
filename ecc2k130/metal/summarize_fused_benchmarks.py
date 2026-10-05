#!/usr/bin/env python3
"""Combine exact fused-selector receipts without overstating two case seeds."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('receipts', type=Path, nargs='+')
    args = parser.parse_args()
    if len(args.receipts) < 2:
        parser.error('at least two independent case seeds are required')
    reports = [json.loads(path.read_text()) for path in args.receipts]
    binary = reports[0]['identity']['binarySha256']
    payload = reports[0]['input']['pairPayloadSha256']
    if any(report.get('status') != 'passed' or
           report['identity']['binarySha256'] != binary or
           report['input']['pairPayloadSha256'] != payload or
           report['runtimeAdditionsPerCase'] != 2 or
           report['pairLookupsPerCase'] != 1 for report in reports):
        raise ValueError('receipts do not share one passed benchmark identity')
    ratios = [value for report in reports for value in report['rawFusedToBaselineRatios']]
    seeds = [report['input']['seed'] for report in reports]
    if len(set(seeds)) != len(seeds):
        raise ValueError('case seeds must be independent')
    cases = sum(report['cases'] for report in reports)
    logical = sum(report['cases'] * report['logicalUpdatesPerCase'] *
                  report['innerIterationsPerSample'] * len(report['rawBaselineSeconds'])
                  for report in reports)
    result = {
        'schema': 'ecc2k130-fused-selector-benchmark-summary-v1',
        'scope': 'public synthetic exact-selector pair-table microbenchmark',
        'decision': 'REJECT_PAIR_PATH',
        'collectionEnabled': False,
        'reason': ('The exact selector still charges two runtime additions and every paired '
                   'warm sample was slower with the 20.24 GB pair lookup.'),
        'caseSeeds': seeds, 'independentCaseSets': len(reports),
        'correctCases': cases, 'pairedTimingSamples': len(ratios),
        'timedLogicalUpdates': logical,
        'runtimeAdditionsPerTwoUpdates': 2,
        'pairLookupsPerTwoUpdates': 1,
        'fusedToBaselineRatio': {
            'median': statistics.median(ratios),
            'mean': statistics.mean(ratios),
            'minimum': min(ratios), 'maximum': max(ratios),
            'allSamplesSlower': all(value > 1 for value in ratios)},
        'perSeedMedianRatios': [report['fusedToBaselineTimeRatio'] for report in reports],
        'pairPayloadSha256': payload,
        'pairPayloadBytes': reports[0]['pairTableBytes'],
        'binarySha256': binary,
        'receipts': [{'name': path.name, 'sha256': digest(path),
                      'seed': report['input']['seed'],
                      'inputSha256': report['input']['inputSha256'],
                      'expectedSha256': report['input']['expectedSha256']}
                     for path, report in zip(args.receipts, reports)],
        'claimBoundary': ('Two independent input seeds and matched warm microbenchmarks; '
                          'not a complete DP collection walk or asymptotic result.')}
    identity = hashlib.sha256(json.dumps(result, sort_keys=True,
                                         separators=(',', ':')).encode()).hexdigest()
    result['benchmarkIdentity'] = identity
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
