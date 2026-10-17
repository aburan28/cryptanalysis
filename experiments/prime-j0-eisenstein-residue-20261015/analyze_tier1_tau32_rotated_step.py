#!/usr/bin/env python3
"""Audit the paired rotated endomorphism radix-step panels from frozen raw worker files."""
from hashlib import sha256
from math import exp, isfinite, log
from pathlib import Path
import json, random, statistics, sys, tarfile
from check_secp256k1_tau_generator import G, N, mul

HERE = Path(__file__).resolve().parent
PROVENANCE = HERE / 'tau32-rotated-step-native-provenance.tar.gz'

def digest(path): return sha256(path.read_bytes()).hexdigest()
def load(path): return json.loads(path.read_text())
def interval(ratios):
    if len(ratios) != 16: return None
    values = [log(x) for x in ratios]
    rng = random.Random(20261015)
    draws = sorted(exp(statistics.median(values[rng.randrange(16)] for _ in range(16)))
                   for _ in range(10000))
    return [draws[250], draws[9749]]

def audit(count):
    assert count in (1, 128)
    stem = f'tier1-tau32-rotated-step-{count}-cpu40'
    raw = HERE / f'tau32-rotated-step-{count}-raw.tar.gz'
    launch, rules, planned = (load(HERE / f'{stem}-{suffix}.json')
                              for suffix in ('launch', 'rules', 'manifest'))
    assert digest(raw) == launch['raw_archive_sha256']
    assert digest(PROVENANCE) == launch['provenance_sha256']
    assert digest(HERE / f'{stem}-rules.json') == launch['rules_sha256']
    assert digest(HERE / f'{stem}-manifest.json') == launch['manifest_sha256']
    with tarfile.open(PROVENANCE, 'r:gz') as provenance:
        for label, suffix in (('reference', 'digit-graph'), ('candidate', 'rotated-step')):
            prefix = f'bench-sources/prime-j0-sparse-tau32-{suffix}/'
            for key, rel in (('front', 'src/bin/eisenstein_fixed.rs'),
                             ('windows', 'src/bin/eisenstein_fixed/unit_orbit_windows.rs')):
                assert sha256(provenance.extractfile(prefix + rel).read()).hexdigest() == rules['hashes'][label + '_' + key]
            fixture = provenance.extractfile(prefix + 'src/bin/mixed640_uniform_fixture.json').read()
            assert sha256(fixture).hexdigest() == rules['fixture_sha256']
            binary = provenance.extractfile(f'bench-target-tau32-{suffix}/release/eisenstein_fixed').read()
            assert sha256(binary).hexdigest() == rules['hashes'][label + '_binary']
        for label, name in (('reference', 'native_sparse_digit_graph_overlay.py'),
                            ('candidate', 'native_sparse_rotated_step_overlay.py')):
            assert sha256(provenance.extractfile('isolated-bench/panels/' + name).read()).hexdigest() == digest(HERE / name)
            if label == 'candidate':
                assert digest(HERE / name) == rules['hashes']['candidate_overlay']
        cases = json.loads(fixture)['cases'][:count]
        assert len(cases) == count
        for case in cases:
            result = mul(int(case['scalar_hex'], 16) % N, G)
            assert ':'.join(f'{x:064x}' for x in result) == case['point_hex']
        assert cases[-1]['point_hex'] == rules['expected_point_hex']
    job = launch['job_id']
    with tarfile.open(raw, 'r:gz') as archive:
        assert all(name == job or name.startswith(job + '/') for name in archive.getnames())
        def read(name): return archive.extractfile(job + '/' + name).read()
        manifest, summary = json.loads(read('manifest.json')), json.loads(read('summary.json'))
        runs_bytes, pairs_bytes = read('runs.jsonl'), read('pairs.jsonl')
        runs = [json.loads(line) for line in runs_bytes.splitlines()]
        pairs = [json.loads(line) for line in pairs_bytes.splitlines()]
        assert manifest == planned and len(runs) == 96 and len(pairs) == 48
        assert summary['expected_pairs'] == 48
        artifacts = summary['artifact_sha256']
        assert artifacts['/workspace/isolated-bench/panels/' + stem + '-rules.json'] == launch['rules_sha256']
        for label, suffix in (('reference', 'digit-graph'), ('candidate', 'rotated-step')):
            prefix = f'/workspace/bench-sources/prime-j0-sparse-tau32-{suffix}/'
            for key, rel in (('front', 'src/bin/eisenstein_fixed.rs'),
                             ('windows', 'src/bin/eisenstein_fixed/unit_orbit_windows.rs')):
                assert artifacts[prefix + rel] == rules['hashes'][label + '_' + key]
            assert artifacts[f'/workspace/bench-target-tau32-{suffix}/release/eisenstein_fixed'] == rules['hashes'][label + '_binary']
        cases_by_id = {case['id']: case for case in manifest['cases']}
        run_lookup, invalid, selected = {}, [], []
        for serial, run in enumerate(runs, 1):
            assert run['serial'] == serial
            case = cases_by_id[run['case']]
            assert run['command'] == case[run['variant']]
            assert run['binary_sha256'] == artifacts[run['command'][0]]
            assert read(run['stderr_file']) == b''
            fields = dict(word.split('=', 1) for word in read(run['stdout_file']).decode().split())
            assert fields == run['fields']
            assert fields['verified'] == '1' and int(fields['count']) == count
            assert fields['point'] == rules['expected_point_hex'] == case['expected_result']
            assert float(fields['preparation_ms']) == 0
            assert isfinite(float(fields['online_ms'])) and float(fields['online_ms']) > 0
            selected.append(int(fields['max_selected']))
            run_lookup[(run['repeat'], run['case'], run['variant'])] = run
            if (run['status'] != 'valid' or run['issues'] or run['returncode'] != 0
                    or run['timed_out'] or not run['postflight']['ok']):
                invalid.append({'serial': serial, 'status': run['status'], 'issues': run['issues']})
    pair_lookup = {(pair['repeat'], pair['case']): pair for pair in pairs}
    assert len(pair_lookup) == 48
    aa_failures, ratios, reference, candidate = [], [], [], []
    low, high = rules['aa_acceptance']
    for repeat in range(16):
        for name in ('cal_before', 'cal_after'):
            pair = pair_lookup[(repeat, name)]
            a, b = (run_lookup[(repeat, name, variant)] for variant in ('reference', 'candidate'))
            ratio = float(a['fields']['online_ms']) / float(b['fields']['online_ms'])
            if pair['status'] != 'valid' or not low <= ratio <= high:
                aa_failures.append({'repeat': repeat, 'case': name, 'ratio': ratio, 'pair_status': pair['status']})
        pair = pair_lookup[(repeat, 'compare_rotated')]
        a, b = (run_lookup[(repeat, 'compare_rotated', variant)] for variant in ('reference', 'candidate'))
        if pair['status'] == 'valid' and not pair['issues']:
            x, y = float(a['fields']['online_ms']), float(b['fields']['online_ms'])
            reference.append(x); candidate.append(y); ratios.append(x/y)
    bounds = interval(ratios)
    gate = (summary['status'] == 'completed' and summary['measurement_tier'] == 'tier1_instance'
            and summary['artifacts_stable'] and not invalid and not aa_failures and len(ratios) == 16)
    qualified = gate and bounds is not None and (bounds[0] > 1 or bounds[1] < 1)
    receipt = {'schema': 1, 'job_id': job, 'measurement_tier': 'tier1_instance',
               'frozen_outputs_independently_replayed': count,
               'runner_status': summary['status'], 'artifact_stable': summary['artifacts_stable'],
               'completed_arms': len(runs), 'completed_pairs': len(pairs),
               'invalid_arms': invalid, 'aa_failures': aa_failures, 'tier_gate_passed': gate,
               'raw_archive_sha256': digest(raw), 'provenance_sha256': digest(PROVENANCE),
               'runs_sha256': sha256(runs_bytes).hexdigest(), 'pairs_sha256': sha256(pairs_bytes).hexdigest(),
               'comparison': {'valid_pairs': len(ratios),
                              'reference_ms_mean': statistics.mean(reference) if reference else None,
                              'candidate_ms_mean': statistics.mean(candidate) if candidate else None,
                              'descriptive_reference_over_candidate_median': statistics.median(ratios) if ratios else None,
                              'paired_bootstrap95_by_repeat': bounds,
                              'aggregate_status': 'qualified' if qualified else 'unknown_after_tier_gate',
                              'qualified_ratio': statistics.median(ratios) if qualified else None,
                              'max_selected_entries': max(selected)}}
    (HERE / f'{stem}-audit.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    return receipt

if __name__ == '__main__':
    counts = tuple(int(value) for value in sys.argv[1:]) or (1, 128)
    print(json.dumps([audit(count) for count in counts], indent=2, sort_keys=True))
