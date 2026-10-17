#!/usr/bin/env python3
"""Independent receipt and point replay for the matched rho restart kernel."""
from hashlib import sha256
from math import exp, isfinite, log
from pathlib import Path
import json
import random
import statistics
import sys
import tarfile

from check_secp256k1_tau_generator import G, N, add, mul

HERE = Path(__file__).resolve().parent


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def interval(ratios):
    if len(ratios) != 16:
        return None
    values = [log(x) for x in ratios]
    rng = random.Random(20261015)
    draws = sorted(exp(statistics.median(values[rng.randrange(16)] for _ in range(16)))
                   for _ in range(10000))
    return [draws[250], draws[9749]]


def audit(count):
    assert count in (1, 128)
    stem = f'tier1-rho-restart-hybrid-{count}-cpu40'
    launch = load(HERE / f'{stem}-launch.json')
    rules = load(HERE / f'{stem}-rules.json')
    planned = load(HERE / f'{stem}-manifest.json')
    raw = HERE / f'rho-restart-hybrid-{count}-raw.tar.gz'
    provenance = HERE / 'rho-restart-hybrid-native-provenance.tar.gz'
    assert digest(raw) == launch['raw_archive_sha256']
    assert digest(provenance) == launch['provenance_sha256']
    assert digest(HERE / f'{stem}-rules.json') == launch['rules_sha256']
    assert digest(HERE / f'{stem}-manifest.json') == launch['manifest_sha256']
    assert digest(HERE / 'rho-restart-first128-fixture.json') == rules['fixture_sha256']
    assert digest(HERE / 'rho_restart_hybrid.rs') == rules['hashes']['helper']
    assert digest(HERE / 'native_rho_restart_hybrid_overlay.py') == rules['hashes']['overlay']
    with tarfile.open(provenance) as archive:
        for key, expected in rules['hashes'].items():
            member = rules['paths'][key].lstrip('/')
            assert sha256(archive.extractfile(member).read()).hexdigest() == expected
    fixture = load(HERE / 'rho-restart-first128-fixture.json')
    with tarfile.open(HERE / 'radix4033-native-provenance.tar.gz') as archive:
        original = archive.extractfile(
            'bench-sources/prime-j0-sparse-radix4033/src/bin/mixed640_uniform_fixture.json').read()
    assert sha256(original).hexdigest() == fixture['source_fixture_sha256']
    source = json.loads(original)['cases']
    assert fixture['q_hex'] == source[fixture['q_source_index']]['point_hex']
    q = tuple(int(x, 16) for x in fixture['q_hex'].split(':'))
    assert q == mul(int(source[fixture['q_source_index']]['scalar_hex'], 16) % N, G)
    for i, case in enumerate(fixture['cases'][:count]):
        a, b = int(case['a_hex'], 16), int(case['b_hex'], 16)
        assert a == int(source[i]['scalar_hex'], 16) % N
        assert b == int(source[i + 128]['scalar_hex'], 16) % N
        point = add(mul(a, G), mul(b, q))
        assert point is not None
        assert ':'.join(f'{coordinate:064x}' for coordinate in point) == case['point_hex']
    assert fixture['cases'][count - 1]['point_hex'] == rules['expected_point_hex']
    job = launch['job_id']
    with tarfile.open(raw) as archive:
        assert all(name == job or name.startswith(job + '/') for name in archive.getnames())
        def read(name):
            return archive.extractfile(job + '/' + name).read()
        actual_manifest = json.loads(read('manifest.json'))
        summary = json.loads(read('summary.json'))
        runs_bytes, pairs_bytes = read('runs.jsonl'), read('pairs.jsonl')
        runs = [json.loads(line) for line in runs_bytes.splitlines()]
        pairs = [json.loads(line) for line in pairs_bytes.splitlines()]
        assert actual_manifest == planned and len(runs) == 96 and len(pairs) == 48
        assert summary['expected_pairs'] == 48
        artifacts = summary['artifact_sha256']
        assert artifacts['/workspace/isolated-bench/panels/' + stem + '-rules.json'] == launch['rules_sha256']
        for key, expected in rules['hashes'].items():
            assert artifacts[rules['paths'][key]] == expected
        cases = {case['id']: case for case in planned['cases']}
        lookup, invalid, prep = {}, [], {'openssl': [], 'hybrid': []}
        for serial, run in enumerate(runs, 1):
            assert run['serial'] == serial
            case = cases[run['case']]
            assert run['command'] == case[run['variant']]
            assert run['binary_sha256'] == rules['hashes']['binary']
            assert read(run['stderr_file']) == b''
            fields = dict(word.split('=', 1) for word in read(run['stdout_file']).decode().split())
            assert fields == run['fields']
            assert fields['verified'] == '1' and int(fields['count']) == count
            assert fields['point'] == rules['expected_point_hex']
            assert fields['mode'] == run['command'][2]
            assert isfinite(float(fields['online_ms'])) and float(fields['online_ms']) > 0
            assert isfinite(float(fields['preparation_ms'])) and float(fields['preparation_ms']) > 0
            if fields['mode'] == 'hybrid':
                assert int(fields['retained_bytes']) == 436132
            else:
                assert int(fields['retained_bytes']) == 0
            prep[fields['mode']].append(float(fields['preparation_ms']))
            lookup[(run['repeat'], run['case'], run['variant'])] = run
            if (run['status'] != 'valid' or run['issues'] or run['returncode'] != 0
                    or run['timed_out'] or not run['postflight']['ok']):
                invalid.append({'serial': serial, 'status': run['status'], 'issues': run['issues']})
    pairs_by_id = {(pair['repeat'], pair['case']): pair for pair in pairs}
    assert len(pairs_by_id) == 48
    aa_failures, ratios, ref, cand = [], [], [], []
    low, high = rules['aa_acceptance']
    for repeat in range(16):
        for case in ('cal_before', 'cal_after'):
            pair = pairs_by_id[(repeat, case)]
            a, b = (lookup[(repeat, case, variant)] for variant in ('reference', 'candidate'))
            ratio = float(a['fields']['online_ms']) / float(b['fields']['online_ms'])
            if pair['status'] != 'valid' or not low <= ratio <= high:
                aa_failures.append({'repeat': repeat, 'case': case, 'ratio': ratio,
                                    'pair_status': pair['status']})
        pair = pairs_by_id[(repeat, 'compare_hybrid')]
        a, b = (lookup[(repeat, 'compare_hybrid', variant)]
                for variant in ('reference', 'candidate'))
        if pair['status'] == 'valid' and not pair['issues']:
            x, y = float(a['fields']['online_ms']), float(b['fields']['online_ms'])
            ref.append(x)
            cand.append(y)
            ratios.append(x / y)
    bounds = interval(ratios)
    gate = (summary['status'] == 'completed' and summary['measurement_tier'] == 'tier1_instance'
            and summary['artifacts_stable'] and not invalid and not aa_failures and len(ratios) == 16)
    qualified = gate and bounds is not None and (bounds[0] > 1 or bounds[1] < 1)
    receipt = {'schema': 1, 'job_id': job, 'measurement_tier': 'tier1_instance',
               'frozen_restart_outputs_independently_replayed': count,
               'runner_status': summary['status'], 'artifact_stable': summary['artifacts_stable'],
               'completed_arms': len(runs), 'completed_pairs': len(pairs),
               'invalid_arms': invalid, 'aa_failures': aa_failures, 'tier_gate_passed': gate,
               'raw_archive_sha256': digest(raw), 'provenance_sha256': digest(provenance),
               'runs_sha256': sha256(runs_bytes).hexdigest(),
               'pairs_sha256': sha256(pairs_bytes).hexdigest(),
               'preparation_ms_mean_by_mode': {k: statistics.mean(v) for k, v in prep.items()},
               'comparison': {'valid_pairs': len(ratios),
                              'reference_ms_mean': statistics.mean(ref) if ref else None,
                              'candidate_ms_mean': statistics.mean(cand) if cand else None,
                              'descriptive_reference_over_candidate_median': statistics.median(ratios) if ratios else None,
                              'paired_bootstrap95_by_repeat': bounds,
                              'aggregate_status': 'qualified' if qualified else 'unknown_after_tier_gate',
                              'qualified_ratio': statistics.median(ratios) if qualified else None}}
    (HERE / f'{stem}-audit.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    return receipt


if __name__ == '__main__':
    counts = tuple(int(arg) for arg in sys.argv[1:]) or (1, 128)
    print(json.dumps([audit(count) for count in counts], indent=2, sort_keys=True))
