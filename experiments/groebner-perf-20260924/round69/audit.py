"""Audit retained identity diagnostics and independently replay original ANF proofs."""
import argparse
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import numpy as np
from inputs import generate, FIXTURE
from run import AUDIT_SOURCES, parse_csv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / 'round44'))
from tagged_reference import certify_roots
sys.path.insert(0, str(HERE.parent / 'round34'))
from affine_reference import branch_model
sys.path.insert(0, str(HERE.parent / 'round27'))
from reference import verify_basis


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(out):
    report = json.loads((out / 'report.json').read_text())
    receipt = json.loads((out / 'build/receipt.json').read_text())
    assert report['schema'] == 'independent-multiplier-diagnostic/1' and report['status'] == 'PASS'
    assert report['source_status'] == '' and report['timing_eligible'] is False
    assert report['host_isolation_receipt'] is None and report['aggregate_speedup'] is None
    assert report['build_receipt_sha256'] == sha(out / 'build/receipt.json')
    sources = dict(receipt['sources'])
    for path in [FIXTURE, *(HERE.parent / v for v in AUDIT_SOURCES), *(HERE / 'fixtures').iterdir()]:
        sources[str(path.relative_to(HERE.parent))] = sha(path)
    assert sources == report['sources']
    commit = report['source_commit']
    assert len(commit) == 40 and all(c in '0123456789abcdef' for c in commit)
    for relative, digest in sources.items():
        path = HERE.parent / relative
        assert path.resolve().is_relative_to(HERE.parent.resolve()) and sha(path) == digest
        blob = subprocess.check_output(['git', 'show', commit + ':' + str(path.relative_to(ROOT))], cwd=ROOT)
        assert hashlib.sha256(blob).hexdigest() == digest
    for section in ('binaries', 'generated'):
        for name, digest in receipt[section].items():
            assert Path(name).name == name and sha(out / 'build' / name) == digest
    assert report['architecture'] == receipt['architecture']
    assert report['metal_enabled'] == receipt['metal_enabled']
    available = report['metal_available']
    assert report['probe']['exit_code'] == (0 if available else 77)
    assert report['probe']['log_sha256'] == sha(out / 'probe.log')
    assert ('METAL_AVAILABLE' if available else 'METAL_UNAVAILABLE') in (out / 'probe.log').read_text()
    names = ('test', 'test-ubsan', 'test-unavailable', 'test-unavailable-ubsan')
    assert [v['name'] for v in report['controls']] == list(names)
    cells = comparisons = 0
    for control in report['controls']:
        path = out / (control['name'] + '.log')
        assert control['exit_code'] == 0 and control['log_sha256'] == sha(path)
        gpu = available and 'unavailable' not in control['name']
        count, checks = (557, 2180) if gpu else (556, 0)
        assert f'PASS {count} exact control cells; {checks} GPU output comparisons;' in path.read_text()
        assert 'FAIL' not in path.read_text()
        cells += count; comparisons += checks
    plan = json.loads((out / 'plan.json').read_text())
    assert report['plan_sha256'] == sha(out / 'plan.json')
    assert plan['schema'] == 'independent-multiplier-panel/1'
    assert plan['timing_eligible'] is False and plan['host_isolation_receipt'] is None and plan['aggregate_speedup'] is None
    assert plan['arms'] == ['cpu_factored_local', 'metal_record', 'metal_coefficient']
    orders = [list(v) for v in itertools.permutations(range(3))] * 3
    assert plan['orders'] == orders and plan['warmup_order'] == [0, 1, 2]
    with tempfile.TemporaryDirectory(prefix='multiplier-reconstruction-', dir=out.parent) as temporary:
        reconstructed = generate(Path(temporary) / 'inputs')
        assert len(reconstructed) == len(plan['inputs']) == 3
        for expected, actual in zip(reconstructed, plan['inputs']):
            a, b = dict(expected), dict(actual)
            a.pop('input_path'); b.pop('input_path')
            assert a == b
            assert sha(out / 'inputs' / (actual['name'] + '.bin')) == actual['input_sha256']
    expected_records = [(v['name'], binary) for v in plan['inputs'] for binary in ('bench', 'bench-ubsan')]
    assert [(r['name'], r['binary']) for r in report['records']] == expected_records
    for record in report['records']:
        item = next(v for v in plan['inputs'] if v['name'] == record['name'])
        path = out / (record['name'] + '-' + record['binary'] + '.csv')
        assert record['exit_code'] == 0 and record['output_sha256'] == sha(path)
        assert record['stderr_sha256'] == sha(path.with_suffix('.stderr'))
        assert ('METAL_AVAILABLE' if available else 'METAL_UNAVAILABLE') in path.with_suffix('.stderr').read_text()
        rows = parse_csv(path)
        assert rows == record['rows'] and len(rows) == (57 if available else 19)
        positions = [(t, p, a) for t in range(-1, 18) for p, a in enumerate([0, 1, 2] if t < 0 else orders[t]) if available or a == 0]
        y, count = item['y'], item['records']
        groups = 1 + y + math.comb(y, 2) + math.comb(y, 3)
        limbs = (item['equations'] + 63) // 64
        for row, position in zip(rows, positions):
            assert (row['trial'], row['position'], row['arm']) == position
            assert row['warmup'] == int(row['trial'] == -1) and row['status'] == 'PASS'
            for k, v in row.items():
                if k.endswith('_seconds') or k.startswith('load_'):
                    assert math.isfinite(v) and v >= 0
            assert row['records'] == count and row['coefficient_checks'] == count * groups
            assert row['first_invalid_record'] == (1 << 64) - 1 and row['records_after_first_invalid'] == 0
            dispatched = bool(row['arm'] and count)
            assert row['submitted_dispatches'] == row['completed_dispatches'] == int(dispatched)
            assert row['input_bytes'] == (item['coefficient_bytes'] + count * (y + 1) * limbs * 8 + count * 4 if dispatched else 0)
            assert row['output_bytes'] == row['initialized_bytes'] == (count * 4 if dispatched else 0)
            assert row['dispatched_threads'] >= (count * (groups if row['arm'] == 2 else 1) if dispatched else 0)
            assert sum(row[k] for k in ('validation_seconds', 'copy_in_seconds', 'encode_seconds', 'wait_seconds', 'copy_out_seconds')) <= row['wall_seconds'] + 1e-9
            assert row['wall_seconds'] <= row['outer_seconds'] + 1e-9
        arms = range(3) if available else (0,)
        assert record['median_ms'] == {str(a): statistics.median(v['outer_seconds'] * 1000 for v in rows if v['arm'] == a and not v['warmup']) for a in arms}
        assert record['paired_difference_ms'] == {str(a): [1000 * (next(v['outer_seconds'] for v in rows if v['trial'] == t and v['arm'] == a)
                                                                  - next(v['outer_seconds'] for v in rows if v['trial'] == t and v['arm'] == 0)) for t in range(18)] for a in arms if a}
    # Separate direct-superset original-ANF reconstruction, all proof records,
    # partial ranks, remaining roots, and exact Boolean bases. No native loading.
    fixtures = {v['name']: v for v in json.loads(gzip.decompress(FIXTURE.read_bytes()))}
    independent = []
    for saved in plan['inputs']:
        item = fixtures[saved['name']]
        raw = gzip.decompress((HERE / 'fixtures' / saved['proof_file']).read_bytes())
        args = (saved['x'], saved['y'], saved['equations'], tuple(tuple(v) for v in item['reference_anf']))
        roots, constants, extended, partials, assignments = certify_roots(*args, raw, 'little')
        assert list(roots) == saved['expected_roots']
        assert verify_basis(item['nvars'], item['reference_anf'], list(roots), saved['basis_terms'], len(roots))
        _, vectors, masks, _, _ = branch_model(*args)
        dtype = '<u4' if saved['equations'] <= 32 else '<u8'
        limbs = (saved['equations'] + 63) // 64
        table = np.memmap(out / 'inputs' / (saved['name'] + '.bin'), dtype=dtype, mode='r', offset=24,
                          shape=(len(masks) * limbs, 1 << saved['x']))
        equation_mask = (1 << saved['equations']) - 1
        for f in range(len(masks)):
            for l in range(limbs):
                words = np.fromiter((((v >> (f * saved['equations'])) & equation_mask) >> (64 * l) & ((1 << 64) - 1) for v in vectors), dtype=dtype, count=len(vectors))
                assert np.array_equal(words, table[f * limbs + l])
        del table
        independent.append({'name': saved['name'], 'proof_sha256': saved['proof_sha256'], 'roots': list(roots),
                            'constants': constants, 'extended_records': len(extended), 'partial_records': len(partials),
                            'residual_assignments': assignments, 'all_reconstructed_coefficients_match': True, 'exact_basis_verified': True})
        print('ORIGINAL_ANF_AND_TABLE_PASS', saved['name'], flush=True)
    return {'status': 'PASS', 'source_commit': commit, 'source_bindings': len(sources),
            'exact_controls': cells, 'gpu_output_comparisons': comparisons,
            'panel_rows': sum(len(v['rows']) for v in report['records']),
            'metal_available': available, 'original_anf_proofs': independent,
            'native_artifacts_loaded': False, 'timing_eligible': False,
            'host_isolation_receipt': None, 'aggregate_speedup': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    result = audit(args.evidence.resolve())
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('INDEPENDENT_MULTIPLIER_AUDIT_PASS', result['panel_rows'], result['source_bindings'], flush=True)
