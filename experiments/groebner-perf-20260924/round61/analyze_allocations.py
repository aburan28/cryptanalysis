"""Audit matrix-local reserve requests; these are not wall-time speedups."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(path):
    report = json.loads(gzip.decompress(path.read_bytes()))
    assert report['status'] == 'PASS'
    records = {}
    for row in report['rows']:
        key = row['name'], row['arm'], row['sanitizer']
        assert key not in records
        records[key] = row['measurement']['result']
    rows = []
    for case in report['inputs']:
        name = case['name']
        counts = {}
        for arm, cap in (('baseline', 0), ('scratch', 32768)):
            result = records[name, arm, False]
            stats = result['scratch_stats']
            assert stats == records[name, arm, True]['scratch_stats']
            assert all(type(v) is int and v >= 0 for v in stats.values())
            assert stats['xors'] == stats['fresh_vectors'] + stats['growths'] + stats['reused']
            assert stats['peak_capacity_words'] <= cap
            if arm == 'baseline':
                assert stats['growths'] == stats['reused'] == stats['trimmed_pivots'] == 0
            counts[arm] = sum(stats[k] for k in ('fresh_vectors', 'growths', 'trimmed_pivots'))
        baseline, candidate = records[name, 'baseline', False], records[name, 'scratch', False]
        assert baseline['scratch_stats']['xors'] == candidate['scratch_stats']['xors']
        assert (baseline['status'], baseline['verified']) == (candidate['status'], candidate['verified'])
        rows.append({'name': name, 'status': candidate['status'], 'verified': candidate['verified'],
                     'baseline_reserve_requests': counts['baseline'],
                     'scratch_reserve_requests_including_compaction': counts['scratch'],
                     'request_reduction_fraction': 1-counts['scratch']/counts['baseline'] if counts['baseline'] else None,
                     'scratch_stats': candidate['scratch_stats']})
    assert len(records) == 4*len(rows) == 92
    return {'status': 'PASS', 'preflight_sha256': sha(path), 'analyzer_sha256': sha(Path(__file__)),
            'scope': 'Column-matrix XOR vector reserve requests, including pivot compaction; not whole-query allocations.',
            'rows': rows, 'complete_query_speedup': None, 'online_speedup': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preflight', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = analyze(args.preflight)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print('ALLOCATION_ACCOUNTING_PASS', len(result['rows']))
