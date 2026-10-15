#!/usr/bin/env python3
"""Audit every arm and frozen A/A gate for the two-x Tier 1 panel."""
from hashlib import sha256
import json
from math import exp, log
from pathlib import Path
import random
import re
import statistics
import tarfile

HERE = Path(__file__).resolve().parent
JOB = '0131d510f20941bc81104accf08cf0fa'


def load(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    operations_per_arm = 128*96
    rules = load(HERE / 'tier1-two-x-cpu40-rules.json')
    planned = load(HERE / 'tier1-two-x-cpu40-manifest.json')
    folder = HERE / JOB
    manifest = load(folder / 'manifest.json')
    summary = load(folder / 'summary.json')
    runs = lines(folder / 'runs.jsonl')
    pairs = lines(folder / 'pairs.jsonl')
    provenance = HERE / 'prime-j0-affine-two-x-native-provenance.tar.gz'
    assert sha256(provenance.read_bytes()).hexdigest() == (
        '3f4473284c867dda7a8d7963e8b2588dfe25747c5c0507c2ed2fb009651649e5')
    with tarfile.open(provenance, 'r:gz') as archive:
        for suffix, key in (('src/bin/eisenstein_fixed.rs', 'candidate_front_source_sha256'),
                            ('src/bin/eisenstein_fixed/unit_orbit_windows.rs',
                             'candidate_windows_source_sha256')):
            assert sha256(archive.extractfile(suffix).read()).hexdigest() == rules[key]
        assert sha256(archive.extractfile('native_two_x_overlay.py').read()).hexdigest() == (
            sha256((HERE / 'native_two_x_overlay.py').read_bytes()).hexdigest())
    assert manifest == planned
    assert summary['status'] == 'completed' and summary['artifacts_stable']
    for variant in ('reference', 'candidate'):
        stem = '/workspace/bench-sources/prime-j0-affine-' + (
            'layer-native' if variant == 'reference' else 'two-x-native')
        for suffix, key in (('target/release/eisenstein_fixed', 'binary'),
                            ('src/bin/eisenstein_fixed.rs', 'front_source'),
                            ('src/bin/eisenstein_fixed/unit_orbit_windows.rs', 'windows_source')):
            assert summary['artifact_sha256'][stem + '/' + suffix] == rules[
                variant + '_' + key + '_sha256']
    assert len(runs) == 2*len(manifest['cases'])*rules['repetitions'] == 96
    assert len(pairs) == len(manifest['cases'])*rules['repetitions'] == 48
    assert summary['valid_pairs'] == summary['expected_pairs'] == len(pairs)
    expected = {case['id']: case for case in manifest['cases']}
    for serial, run in enumerate(runs, 1):
        assert run['serial'] == serial and run['status'] == 'valid'
        assert not run['issues'] and not run['timed_out'] and run['returncode'] == 0
        assert run['postflight']['ok']
        assert (folder / run['stderr_file']).read_text() == ''
        stdout_fields = dict(item.split('=', 1) for item in
                             (folder / run['stdout_file']).read_text().split())
        assert stdout_fields == run['fields']
        assert float(stdout_fields['online_ms']) == run['online_ms']
        case = expected[run['case']]
        assert all(run['fields'].get(k) == v for k, v in case['expected_fields'].items())
        assert run['fields'].get('point') == case['expected_result']
        assert run['fields'].get('verified') == '1'
        assert run['binary_sha256'] == summary['artifact_sha256'][run['command'][0]]
    bound = re.search(r'\[([0-9.]+),([0-9.]+)\]', rules['calibration_acceptance'])
    assert bound
    low, high = map(float, bound.groups())
    lookup = {(pair['repeat'], pair['case']): pair for pair in pairs}
    aa_failures = []
    comparisons = []
    for repeat in range(rules['repetitions']):
        before = lookup[(repeat, 'cal_before')]
        measured = lookup[(repeat, 'compare')]
        after = lookup[(repeat, 'cal_after')]
        assert all(item['status'] == 'valid' for item in (before, measured, after))
        comparisons.append(measured['speedup'])
        if not (low <= before['speedup'] <= high and
                low <= after['speedup'] <= high):
            aa_failures.append({'repeat': repeat,
                                'before_ratio': before['speedup'],
                                'after_ratio': after['speedup'],
                                'comparison_ratio': measured['speedup']})
    rng = random.Random(23102)
    logs = [log(value) for value in comparisons]
    bootstrap = sorted(exp(statistics.median(
        logs[rng.randrange(len(logs))] for _ in logs)) for _ in range(10000))
    interval = [bootstrap[250], bootstrap[9749]]
    qualified = not aa_failures and (interval[0] > 1 or interval[1] < 1)
    measured_runs = [row for row in runs if row['case'] == 'compare']
    reference = [row for row in measured_runs if row['variant'] == 'reference']
    candidate = [row for row in measured_runs if row['variant'] == 'candidate']
    ref_ms = statistics.mean(row['online_ms'] for row in reference)
    cand_ms = statistics.mean(row['online_ms'] for row in candidate)
    return {
        'schema': 1,
        'measurement_tier': 'tier1_instance',
        'runpod_instance_id': manifest['allocation']['instance_id'],
        'job_id': JOB,
        'operations_per_arm': operations_per_arm,
        'completed_runs': len(runs),
        'completed_pairs': len(pairs),
        'artifact_stable': summary['artifacts_stable'],
        'aa_acceptance_range': [low, high],
        'aa_failed_comparisons': aa_failures,
        'paired_bootstrap95_by_repeat': interval,
        'descriptive_reference_over_candidate_median': statistics.median(comparisons),
        'qualified_comparison_ratio': statistics.median(comparisons) if qualified else None,
        'aggregate_status': 'qualified' if qualified else 'unknown_after_tier_gate',
        'reference_online_ms_mean': ref_ms,
        'candidate_online_ms_mean': cand_ms,
        'reference_us_per_scalar': 1000*ref_ms/operations_per_arm,
        'candidate_us_per_scalar': 1000*cand_ms/operations_per_arm,
        'reference_preparation_ms_mean': statistics.mean(float(row['fields']['preparation_ms']) for row in reference),
        'candidate_preparation_ms_mean': statistics.mean(float(row['fields']['preparation_ms']) for row in candidate),
        'reference_retained_bytes': sorted({int(row['fields']['retained_bytes']) for row in reference}),
        'candidate_retained_bytes': sorted({int(row['fields']['retained_bytes']) for row in candidate}),
        'runs_sha256': sha256((folder / 'runs.jsonl').read_bytes()).hexdigest(),
        'pairs_sha256': sha256((folder / 'pairs.jsonl').read_bytes()).hexdigest(),
    }


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True, indent=2))
