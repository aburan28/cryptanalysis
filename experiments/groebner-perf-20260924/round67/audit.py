"""Read-only audit of source/native bindings, controls and every retained panel row."""
import argparse
import csv
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import statistics
import struct
import subprocess

HERE = Path(__file__).resolve().parent
PREFIX = 'experiments/groebner-perf-20260924/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(out):
    report = json.loads((out / 'report.json').read_text())
    receipt = json.loads((out / 'build/receipt.json').read_text())
    assert report['status'] == 'PASS' and report['source_status'] == ''
    assert report['timing_eligible'] is False and report['host_isolation_receipt'] is None
    assert report['aggregate_speedup'] is None
    commit = report['source_commit']
    assert re.fullmatch('[0-9a-f]{40}', commit)
    expected = {}
    for name, digest in receipt['sources'].items():
        assert Path(name).name == name
        path = 'round67/' + name
        assert sha(HERE.parent / path) == digest, path
        blob = subprocess.check_output(['git', 'show', commit + ':' + PREFIX + path], cwd=HERE)
        assert hashlib.sha256(blob).hexdigest() == digest, path
        expected[path] = digest
    for name in ('round40/fixtures/inputs.json.gz', 'round51/producer.cpp'):
        digest = sha(HERE.parent / name)
        blob = subprocess.check_output(['git', 'show', commit + ':' + PREFIX + name], cwd=HERE)
        assert hashlib.sha256(blob).hexdigest() == digest, name
        expected[name] = digest
    for section in ('binaries', 'generated'):
        for name, digest in receipt[section].items():
            assert Path(name).name == name
            assert sha(out / 'build' / name) == digest, name
            expected['round67/build/' + name] = digest
    expected['round67/build/receipt.json'] = sha(out / 'build/receipt.json')
    normalized = {path.split('/' + PREFIX, 1)[1]: digest for path, digest in report['bindings'].items()}
    assert len(normalized) == len(report['bindings']) and normalized == expected
    assert report['metal_enabled'] == receipt['metal_enabled']
    assert report['probe']['log_sha256'] == sha(out / 'probe.log')
    assert report['probe']['exit_code'] == (0 if report['metal_available'] else 77)
    assert ('METAL_AVAILABLE' if report['metal_available'] else 'METAL_UNAVAILABLE') in (out / 'probe.log').read_text()
    names = ['test-unavailable', 'test-unavailable-ubsan']
    if report['metal_available']:
        assert report['metal_enabled']
        names = ['test', 'test-ubsan', *names]
    assert [control['name'] for control in report['controls']] == names
    for control in report['controls']:
        path = out / (control['name'] + '.log')
        assert control['exit_code'] == 0 and control['log_sha256'] == sha(path)
        assert 'PASS 474 exact controls;' in path.read_text() and 'FAIL' not in path.read_text()
    if not report['metal_available']:
        assert report['records'] == []
    else:
        plan = json.loads((out / 'plan.json').read_text())
        assert report['plan_sha256'] == sha(out / 'plan.json')
        assert plan['timing_eligible'] is False and plan['host_isolation_receipt'] is None and plan['aggregate_speedup'] is None
        orders = [list(row) for row in itertools.permutations(range(3))] * 3
        assert plan['arm_orders'] == orders and plan['warmup_order'] == [0, 1, 2] and plan['warmup_retained'] is True
        assert plan['arms'] == ['cpu', 'metal_staged', 'metal_tiled']
        fixture = HERE.parent / 'round40/fixtures/inputs.json.gz'
        fixtures = {item['name']: item for item in json.loads(gzip.decompress(fixture.read_bytes()))}
        names = ['n31-m3-ell6-seed101', 'n31-m3-ell8-seed201', 'n31-m3-ell9-seed201']
        assert [row['name'] for row in plan['workloads']] == names
        assert [(row['name'], row['binary']) for row in report['records']] == [(name, binary) for name in names for binary in ('bench', 'bench-ubsan')]
        for workload in plan['workloads']:
            item = fixtures[workload['name']]
            raw = struct.pack('<5Q', 0x3736524e52454b, 2 * item['ell'], item['ell'], item['n'], len(item['reference_anf']))
            raw += b''.join(struct.pack('<2Q', *pair) for pair in item['reference_anf'])
            assert workload == {'name': item['name'], 'x': 2 * item['ell'], 'y': item['ell'], 'equations': item['n'],
                                'terms': len(item['reference_anf']), 'input_sha256': hashlib.sha256(raw).hexdigest(),
                                'fixture_sha256': sha(fixture), 'workload_sha256': item['workload_sha256']}
            assert (out / 'inputs' / (item['name'] + '.bin')).read_bytes() == raw
        for record in report['records']:
            workload = next(row for row in plan['workloads'] if row['name'] == record['name'])
            output = out / (record['name'] + '-' + record['binary'] + '.csv')
            assert record['exit_code'] == 0 and record['output_sha256'] == sha(output)
            assert record['stderr_sha256'] == sha(output.with_suffix('.stderr'))
            assert len(record['rows']) == 57
            with output.open() as stream:
                raw_rows = list(csv.DictReader(stream))
            assert len(raw_rows) == 57
            stride = 1 + workload['y'] * (workload['y'] + 1) // 2
            size = (1 << workload['x']) * stride * 4
            for index, (row, text) in enumerate(zip(record['rows'], raw_rows)):
                assert row.keys() == text.keys()
                for key, value in row.items():
                    assert type(value)(text[key]) == value and math.isfinite(value), key
                trial, position = index // 3 - 1, index % 3
                order = [0, 1, 2] if trial == -1 else orders[trial]
                assert (row['trial'], row['position'], row['arm'], row['valid']) == (trial, position, order[position], 1)
                for key in ('wall', 'copy_in', 'encode', 'wait', 'copy_out', 'device', 'verification'):
                    assert row[key] >= 0
                assert row['logical_xors'] == workload['x'] * (1 << (workload['x'] - 1)) * stride
                if row['arm']:
                    dispatches = workload['x'] if row['arm'] == 1 else workload['x'] - 3
                    assert row['input_bytes'] == row['output_bytes'] == row['scratch_bytes'] == size
                    assert row['encoded_dispatches'] == row['submitted_dispatches'] == row['completed_dispatches'] == dispatches
                    assert row['logical_xors'] == workload['x'] * (1 << (workload['x'] - 1)) * stride
                    assert sum(row[key] for key in ('copy_in', 'encode', 'wait', 'copy_out')) <= row['wall']
            rows = record['rows']
            assert record['median_ms'] == {str(arm): statistics.median(row['wall'] * 1000 for row in rows if row['arm'] == arm and row['trial'] >= 0)
                                           for arm in range(3)}
            assert record['paired_difference_ms'] == {str(arm): [1000 * (next(r['wall'] for r in rows if r['trial'] == trial and r['arm'] == arm)
                                                                               - next(r['wall'] for r in rows if r['trial'] == trial and r['arm'] == 0))
                                                               for trial in range(18)] for arm in (1, 2)}
    return {'status': 'PASS', 'source_commit': commit, 'bindings': len(expected),
            'exact_controls': 474 * len(report['controls']),
            'panel_rows': sum(len(record['rows']) for record in report['records']),
            'metal_available': report['metal_available'], 'timing_eligible': False,
            'host_isolation_receipt': None, 'aggregate_speedup': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.evidence)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
