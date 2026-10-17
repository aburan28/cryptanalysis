#!/usr/bin/env python3
"""Independently audit the frozen one-scalar on-demand RunPod panel."""

from hashlib import sha256
from math import exp, isfinite, log
from pathlib import Path
import json
import random
import statistics
import tarfile

from check_secp256k1_tau_generator import G, N, mul

HERE = Path(__file__).resolve().parent
STEM = 'tier1-tau32-demand-cold-cpu40'
RAW = HERE / 'tau32-demand-cold-tier1-raw.tar.gz'
PROVENANCE = HERE / 'tau32-demand-native-provenance.tar.gz'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def bootstrap(ratios):
    if len(ratios) != 16:
        return None
    logs = [log(value) for value in ratios]
    rng = random.Random(20261015)
    draws = sorted(exp(statistics.median(logs[rng.randrange(16)] for _ in range(16)))
                   for _ in range(10000))
    return [draws[250], draws[9749]]


def main():
    launch = load(HERE / f'{STEM}-launch.json')
    rules = load(HERE / f'{STEM}-rules.json')
    planned = load(HERE / f'{STEM}-manifest.json')
    job = launch['job_id']
    assert digest(HERE / f'{STEM}-rules.json') == launch['rules_sha256']
    assert digest(HERE / f'{STEM}-manifest.json') == launch['manifest_sha256']
    assert digest(RAW) == launch['raw_archive_sha256']
    assert digest(PROVENANCE) == launch['provenance_sha256']
    with tarfile.open(RAW, 'r:gz') as archive:
        names = set(archive.getnames())
        assert all(name == job or name.startswith(job + '/') for name in names)

        def read(name):
            return archive.extractfile(job + '/' + name).read()

        manifest = json.loads(read('manifest.json'))
        summary = json.loads(read('summary.json'))
        runs_bytes, pairs_bytes = read('runs.jsonl'), read('pairs.jsonl')
        runs = [json.loads(line) for line in runs_bytes.splitlines()]
        pairs = [json.loads(line) for line in pairs_bytes.splitlines()]
        assert manifest == planned
        assert manifest['repetitions'] == rules['repetitions'] == 16
        assert len(runs) == 96 and len(pairs) == 48
        assert summary['expected_pairs'] == 48
        artifacts = summary['artifact_sha256']
        panel = '/workspace/isolated-bench/panels/'
        assert artifacts[panel + f'{STEM}-rules.json'] == launch['rules_sha256']
        assert artifacts[panel + 'native_sparse_on_demand_overlay.py'] == rules['hashes']['overlay']
        assert rules['hashes']['overlay'] == digest(HERE / 'native_sparse_on_demand_overlay.py')
        locations = {
            'reference': '/workspace/bench-sources/prime-j0-sparse-tau32/',
            'candidate': '/workspace/bench-sources/prime-j0-sparse-tau32-demand/',
        }
        with tarfile.open(PROVENANCE, 'r:gz') as archive_sources:
            for label, prefix in locations.items():
                for key, relative in (
                    ('front', 'src/bin/eisenstein_fixed.rs'),
                    ('windows', 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'),
                ):
                    expected = rules['hashes'][label + '_' + key]
                    assert artifacts[prefix + relative] == expected
                    assert sha256(archive_sources.extractfile(prefix.removeprefix('/workspace/') + relative).read()).hexdigest() == expected
                binary = (prefix + 'target/release/eisenstein_fixed' if label == 'reference'
                          else '/workspace/bench-target-tau32-demand/release/eisenstein_fixed')
                archive_binary = binary.removeprefix('/workspace/')
                expected = rules['hashes'][label + '_binary']
                assert artifacts[binary] == expected
                assert sha256(archive_sources.extractfile(archive_binary).read()).hexdigest() == expected
                fixture = archive_sources.extractfile(
                    prefix.removeprefix('/workspace/') + 'src/bin/mixed640_uniform_fixture.json').read()
                assert sha256(fixture).hexdigest() == rules['fixture_sha256']
            first = json.loads(fixture)['cases'][0]
            scalar = int(first['scalar_hex'], 16) % N
            point = mul(scalar, G)
            independently_replayed = ':'.join(f'{coordinate:064x}' for coordinate in point)
            assert independently_replayed == first['point_hex'] == rules['expected_point_hex']

        cases = {case['id']: case for case in planned['cases']}
        run_lookup = {}
        invalid = []
        selected = []
        for serial, run in enumerate(runs, 1):
            assert run['serial'] == serial
            case = cases[run['case']]
            assert run['command'] == case[run['variant']]
            assert run['binary_sha256'] == artifacts[run['command'][0]]
            assert read(run['stderr_file']) == b''
            fields = dict(word.split('=', 1) for word in read(run['stdout_file']).decode().split())
            assert fields == run['fields']
            assert fields['verified'] == '1' and fields['count'] == '1'
            assert fields['point'] == independently_replayed == case['expected_result']
            for key, value in case['expected_fields'].items():
                assert fields[key] == value
            assert isfinite(float(fields['online_ms'])) and float(fields['online_ms']) > 0
            assert isfinite(float(fields['preparation_ms'])) and float(fields['preparation_ms']) >= 0
            if run['case'] == 'compare_demand_cold' and run['variant'] == 'candidate':
                assert float(fields['preparation_ms']) == 0
                selected.append(int(fields['max_selected']))
            else:
                assert int(fields['retained_bytes']) == rules['reference_retained_bytes']
            run_lookup[(run['repeat'], run['case'], run['variant'])] = run
            if (run['status'] != 'valid' or run['issues'] or run['returncode'] != 0
                    or run['timed_out'] or not run['postflight']['ok']):
                invalid.append({'serial': serial, 'status': run['status'], 'issues': run['issues']})

    pair_lookup = {(pair['repeat'], pair['case']): pair for pair in pairs}
    assert len(pair_lookup) == 48

    def cold(run):
        return float(run['fields']['preparation_ms']) + float(run['fields']['online_ms'])

    low, high = rules['aa_acceptance']
    aa_failures, ratios, reference, candidate = [], [], [], []
    for repeat in range(16):
        for name in ('cal_before', 'cal_after'):
            pair = pair_lookup[(repeat, name)]
            left, right = (run_lookup[(repeat, name, variant)]
                           for variant in ('reference', 'candidate'))
            ratio = cold(left) / cold(right)
            if pair['status'] != 'valid' or not low <= ratio <= high:
                aa_failures.append({'repeat': repeat, 'case': name,
                                    'cold_ratio': ratio, 'pair_status': pair['status']})
        pair = pair_lookup[(repeat, 'compare_demand_cold')]
        left, right = (run_lookup[(repeat, 'compare_demand_cold', variant)]
                       for variant in ('reference', 'candidate'))
        if pair['status'] == 'valid' and not pair['issues']:
            reference.append(cold(left))
            candidate.append(cold(right))
            ratios.append(cold(left) / cold(right))
    bounds = bootstrap(ratios)
    gate = (summary['status'] == 'completed' and summary['measurement_tier'] == 'tier1_instance'
            and summary['artifacts_stable'] and not invalid and not aa_failures
            and len(ratios) == 16)
    qualified = gate and bounds is not None and (bounds[0] > 1 or bounds[1] < 1)
    receipt = {
        'schema': 1, 'job_id': job, 'measurement_tier': 'tier1_instance',
        'runner_status': summary['status'], 'artifact_stable': summary['artifacts_stable'],
        'completed_arms': len(runs), 'completed_pairs': len(pairs),
        'invalid_arms': invalid, 'aa_failures': aa_failures, 'tier_gate_passed': gate,
        'fixture_scalar_replayed_independently': True,
        'raw_archive_sha256': digest(RAW), 'provenance_sha256': digest(PROVENANCE),
        'runs_sha256': sha256(runs_bytes).hexdigest(),
        'pairs_sha256': sha256(pairs_bytes).hexdigest(),
        'comparison': {
            'valid_pairs': len(ratios),
            'reference_cold_ms_mean': statistics.mean(reference) if reference else None,
            'candidate_cold_ms_mean': statistics.mean(candidate) if candidate else None,
            'descriptive_reference_over_candidate_cold_median': statistics.median(ratios) if ratios else None,
            'paired_bootstrap95_by_repeat': bounds,
            'aggregate_status': 'qualified' if qualified else 'unknown_after_tier_gate',
            'qualified_cold_ratio': statistics.median(ratios) if qualified else None,
            'candidate_max_selected_entries': max(selected) if selected else None,
            'reference_retained_bytes': rules['reference_retained_bytes'],
        },
    }
    (HERE / f'{STEM}-audit.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
