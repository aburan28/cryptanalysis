"""Recompute all native residual certificates and roots from frozen originals."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from native import HERE
from reference import checker, direct_roots, truth_transform
from validate_native import cases, polynomials, read, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=HERE / 'build/correctness.json.gz')
    parser.add_argument('--receipt', type=Path, default=HERE / 'build/receipt.json')
    parser.add_argument('--output', type=Path, default=HERE / 'build/audit.json')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report, receipt = read(args.input), read(args.receipt)
    assert report['status'] == 'PASS'
    assert report['build_receipt_sha256'] == sha(args.receipt)
    assert report['plan_sha256'] == sha(HERE / 'plan.json')
    for filename, expected in receipt['sources'].items():
        assert sha(HERE / filename) == expected, filename
    for filename, expected in report['source_sha256'].items():
        assert sha(HERE / filename) == expected, filename
    for filename, expected in receipt['binaries'].items():
        assert sha(args.receipt.parent / filename) == expected, filename
    corpus = list(cases(read(HERE / 'plan.json')))
    assert report['corpus_sha256'] == hashlib.sha256(
        json.dumps(corpus, separators=(',', ':')).encode()).hexdigest()
    assert report['systems'] == len(corpus) == 17258
    assert report['runs'] == len(report['controls']) == 2 * len(corpus)
    expected = {}
    kinds = Counter()
    for name, y, equations, terms, kind in corpus:
        assert name not in expected
        rows = polynomials(y, equations, terms)
        roots = truth_transform(y, rows)
        if y <= 3:
            assert roots == direct_roots(y, rows)
        expected[name] = y, equations, kind, rows, roots
        kinds[kind] += 1
    seen, optimized = set(), {}
    for record in report['controls']:
        name, sanitizer = record['name'], record['sanitizer']
        assert type(sanitizer) is bool and (name, sanitizer) not in seen
        seen.add((name, sanitizer))
        y, equations, kind, rows, roots = expected[name]
        assert record['shape'] == [y, equations] and record['kind'] == kind
        produced, checked = record['producer'], record['checker']
        assert produced['code'] == 0 and produced['status'] == 'produced'
        assert checked['code'] == 0 and checked['status'] == 'verified'
        independent = checker(y, rows, produced['witnesses'])
        assert independent.roots == roots == tuple(checked['roots'])
        assert independent.rank == checked['stats']['rank']
        assert independent.inconsistent == bool(checked['stats']['inconsistent'])
        assert independent.candidates == checked['stats']['assignments']
        mathematical = {k: v for k, v in record.items() if k != 'sanitizer'}
        if sanitizer:
            assert mathematical == optimized[name]
        else:
            optimized[name] = mathematical
    assert seen == {(name, sanitizer) for name in expected for sanitizer in (False, True)}
    assert len(report['guards']) == 2
    assert [g['sanitizer'] for g in report['guards']] == [False, True]
    assert report['guards'][0]['records'] == report['guards'][1]['records']
    assert len(report['guards'][0]['records']) == 29
    assert all(r.get('status') == 'PASS' or r.get('code') == 3
               for group in report['guards'] for r in group['records'])
    assert report['candidate_id'] is report['online_speedup'] is None
    assert report['timing_eligible'] is False
    result = {'status': 'PASS', 'systems': len(corpus), 'runs': len(seen),
              'kinds': dict(kinds), 'guard_groups_per_build': 29,
              'report_sha256': sha(args.input), 'receipt_sha256': sha(args.receipt),
              'corpus_sha256': report['corpus_sha256'],
              'scope': 'Independent exact residual-root audit; no complete-query or performance claim.',
              'candidate_id': None, 'online_speedup': None}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
