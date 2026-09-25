"""Audit saved GPU evidence; this does not execute Metal or recheck RREF in CI."""
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paired(samples, numerator, denominator):
    ratios = [math.log(s[numerator] / s[denominator]) for s in samples]
    rng = random.Random(2026092508)
    boot = sorted(math.exp(statistics.mean(rng.choices(ratios, k=len(ratios))))
                  for _ in range(4000))
    return {'geometric_mean': math.exp(statistics.mean(ratios)),
            'bootstrap_95': [boot[99], boot[3899]]}


def main():
    rows, hashes, attempts = [], 0, 0
    matrix_gz = HERE.parent / 'round3/matrices.json.gz'
    expected = {'local-panel-screen', 'table-baseline', 'local-panel16-screen',
                'trailing-vector-screen', 'interleaved-confirmation'}
    assert {p.name.removesuffix('-receipt.json') for p in (HERE / 'results').glob('*-receipt.json')} == expected
    for name in ['confirm.mm', 'local_rref.mm', 'local_panel.metal', 'run_gpu.py']:
        assert sha(HERE / name) == sha(HERE / 'results/sources/interleaved-confirmation' / name), name
    inventory = json.loads((HERE / 'results/profile-inventory.json').read_text())
    for relative, expected_hash in inventory['retained_sha256'].items():
        assert sha(HERE / relative) == expected_hash, relative
        hashes += 1
    for path in sorted((HERE / 'results').glob('*-receipt.json')):
        receipt = json.loads(path.read_text())
        for relative, expected in receipt['source_sha256'].items():
            assert sha(HERE / relative) == expected, relative
            hashes += 1
        assert sha(matrix_gz) == receipt['matrix_gz_sha256']
        assert hashlib.sha256(gzip.decompress(matrix_gz.read_bytes())).hexdigest() == receipt['matrix_sha256']
        assert receipt['status'] in {'PASS', 'failed', 'timeout', 'error', 'build_failed'}
        result = path.with_name(path.name.replace('-receipt.json', '.json'))
        if 'result_sha256' in receipt:
            assert sha(result) == receipt['result_sha256']
            hashes += 1
        if receipt['status'] != 'PASS':
            rows.append({'run': result.name, 'status': receipt['status']})
            continue
        report = json.loads(result.read_text())
        assert report['exact_rref_and_rank'] is True
        assert receipt['checked_matrices'] == report['checked_matrices']
        for cell in report['cells']:
            assert cell.get('batch', cell.get('target_count')) == 1
            samples = [s for s in cell['samples'] if not s['warmup']]
            assert sum(s['warmup'] for s in cell['samples']) == 1
            attempts += len(cell['samples'])
            row = {'run': result.name, 'case': cell['name'], 'status': 'PASS'}
            if receipt['variant'] == 'confirm':
                assert len(samples) == 15
                assert all(sorted(s['order']) == [0, 1, 2] for s in cell['samples'])
                assert len({s['rank'] for s in cell['samples']}) == 1
                keys = ['cpu_wall_ms', 'cpu_thread_ms', 'baseline_gpu_wall_ms',
                        'revised_gpu_wall_ms', 'baseline_gpu_device_ms', 'revised_gpu_device_ms']
                assert all(s[k] > 0 for s in samples for k in keys)
                row['medians_ms'] = {k: statistics.median(s[k] for s in samples) for k in keys}
                row['old_gpu_over_revised_wall'] = paired(samples, 'baseline_gpu_wall_ms', 'revised_gpu_wall_ms')
                row['old_gpu_over_revised_device'] = paired(samples, 'baseline_gpu_device_ms', 'revised_gpu_device_ms')
                row['cpu_over_revised_wall'] = paired(samples, 'cpu_wall_ms', 'revised_gpu_wall_ms')
            else:
                assert len(samples) == 9
                row['cpu_over_gpu_wall'] = paired(samples, 'cpu_ms', 'gpu_wall_ms')
            rows.append(row)
    assert attempts == 336 and hashes > 0
    print(json.dumps({'audit': 'PASS', 'scope': 'retained evidence integrity; no Metal execution',
                      'source_and_result_hashes': hashes, 'paired_sample_groups_including_warmups': attempts,
                      'candidate_id': None, 'IC_online_ms': None, 'rho_online_ms': None,
                      'rows': rows}, indent=2))


if __name__ == '__main__':
    main()
