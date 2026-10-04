"""Replay matrix proofs and row spaces, including word and budget boundaries."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reduced_space(rows):
    pivots = {}
    for row in rows:
        while row:
            pivot = row.bit_length()-1
            if pivot not in pivots:
                pivots[pivot] = row
                break
            row ^= pivots[pivot]
    for pivot in sorted(pivots):
        for higher in pivots:
            if higher > pivot and (pivots[higher] >> pivot) & 1:
                pivots[higher] ^= pivots[pivot]
    return sorted(pivots.values())


def replay(row):
    assert row['start'] <= row['work'] <= row['limit']
    assert len(row['nodes']) <= row['node_limit']
    support = {(1 << 63 if row['high'] else 0) | i: i for i in range(row['columns'])}
    original = []
    for terms in row['input']:
        assert terms == sorted(set(terms)) and set(terms) <= support.keys()
        original.append(set(terms))
    values = []
    for i, (op, a, b) in enumerate(row['nodes']):
        if op == 0:
            assert 0 <= a < len(original) and b == 0
            values.append(original[a])
        else:
            assert op == 2 and 0 <= a < i and 0 <= b < i
            values.append(values[a] ^ values[b])
    answer = []
    for proof, terms in row['output']:
        assert terms == sorted(set(terms)) and 0 <= proof < len(values)
        assert set(terms) == values[proof]
        answer.append(set(terms))
    if row['status'] == 'complete':
        assert row['reason'] == 'none'
        packed = lambda polys: [sum(1 << support[m] for m in poly) for poly in polys]
        assert reduced_space(packed(original)) == reduced_space(packed(answer))
    else:
        assert row['status'] == 'budget' and row['reason'] in ('work', 'nodes') and not answer


def audit(report):
    assert report['schema'] == 'packed-column-controls/1'
    seen = set()
    baseline = None
    packed_seen = fallback_seen = False
    for run in report['runs']:
        key = run['variant'], run['sanitizer']
        assert key not in seen
        seen.add(key)
        rows = run['rows']
        assert len(rows) == 728
        trace = [{k: v for k, v in row.items() if k != 'packed'} for row in rows]
        if baseline is None:
            assert key == ('baseline', False)
            baseline = trace
            for row in rows:
                replay(row)
        else:
            assert trace == baseline, key
        cap = {'baseline': 0, 'packed': 8388608, 'tiny': 4}[run['variant']]
        for row in rows:
            matrices, fallback, payload = row['packed']
            assert all(type(v) is int and v >= 0 for v in row['packed']) and payload <= cap
            if run['variant'] == 'baseline':
                assert matrices == fallback == payload == 0
            if run['variant'] == 'tiny':
                packed_seen |= matrices > 0
                fallback_seen |= fallback > 0
    assert seen == {(v, s) for v in ('baseline', 'packed', 'tiny') for s in (False, True)}
    assert packed_seen and fallback_seen
    return {'status': 'PASS', 'cases_per_variant': 728, 'variant_runs': len(seen),
            'records': len(seen)*728, 'matrix_proofs_and_row_spaces_replayed': True,
            'timing_eligible': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = {'schema': 'packed-column-controls/1', 'runs': []}
    for variant in ('baseline', 'packed', 'tiny'):
        for sanitizer in (False, True):
            binary = HERE/'build/engines'/variant/'build'/('matrix_controls'+('-ubsan' if sanitizer else '')+'.exe')
            result = subprocess.check_output([str(binary)], text=True)
            rows = [json.loads(line) for line in result.splitlines()]
            report['runs'].append({'variant': variant, 'sanitizer': sanitizer,
                                  'binary': str(binary.relative_to(ROOT)), 'binary_sha256': sha(binary), 'rows': rows})
    report['audit'] = audit(report)
    args.output.write_bytes(gzip.compress(json.dumps(report, separators=(',', ':')).encode(), mtime=0))
    print(json.dumps(report['audit'], indent=2))


if __name__ == '__main__':
    main()
