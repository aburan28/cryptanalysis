#!/usr/bin/env python3
"""Audit the frozen norm-12211 versus norm-53593 RunPod panel."""
from hashlib import sha256
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parent / 'tier1-runpod-20261014'
JOB = '83919cdcad424eafbf517158e82e9741'


def load(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    rules = load(ROOT / 'panels/panel-rules.json')
    planned = load(ROOT / 'panels/rolling12211-vs-radix53593.json')
    folder = ROOT / JOB
    manifest = load(folder / 'manifest.json')
    summary = load(folder / 'summary.json')
    runs = rows(folder / 'runs.jsonl')
    pairs = rows(folder / 'pairs.jsonl')
    assert manifest == planned, 'executed manifest differs from frozen panel'
    assert summary['status'] == 'completed' and summary['artifacts_stable']
    assert len(runs) == 2 * len(manifest['cases']) * rules['repetitions']
    assert len(pairs) == len(manifest['cases']) * rules['repetitions']
    assert summary['valid_pairs'] == len(pairs) == summary['expected_pairs']

    expected = {case['id']: case for case in manifest['cases']}
    for serial, run in enumerate(runs, 1):
        assert run['serial'] == serial and run['status'] == 'valid'
        case = expected[run['case']]
        assert all(run['fields'].get(k) == v
                   for k, v in case['expected_fields'].items())
        assert run['fields'].get('point') == case['expected_result']
        assert run['fields'].get('verified') == '1'
        assert run['binary_sha256'] == summary['artifact_sha256'][run['command'][0]]

    bound = re.search(r'\[([0-9.]+),([0-9.]+)\]', rules['calibration_acceptance'])
    assert bound
    low, high = map(float, bound.groups())
    lookup = {(pair['repeat'], pair['case']): pair for pair in pairs}
    failures = []
    ratios = []
    for index in rules['case_indices']:
        for repeat in range(rules['repetitions']):
            before = lookup[(repeat, f'cal_before_{index}')]
            measured = lookup[(repeat, f'compare_{index}')]
            after = lookup[(repeat, f'cal_after_{index}')]
            assert all(item['status'] == 'valid' for item in (before, measured, after))
            ratios.append(measured['speedup'])
            if not (low <= before['speedup'] <= high and
                    low <= after['speedup'] <= high):
                failures.append({'case_index': index, 'repeat': repeat,
                                 'before_ratio': before['speedup'],
                                 'after_ratio': after['speedup'],
                                 'comparison_ratio': measured['speedup']})

    compare_runs = [row for row in runs if row['case'].startswith('compare_')]
    ref = [row for row in compare_runs if row['variant'] == 'reference']
    cand = [row for row in compare_runs if row['variant'] == 'candidate']
    return {
        'measurement_tier': 'tier1_instance',
        'runpod_instance_id': manifest['allocation']['instance_id'],
        'job': JOB,
        'completed_runs': len(runs),
        'completed_pairs': len(pairs),
        'artifact_stable': summary['artifacts_stable'],
        'aa_acceptance_range': [low, high],
        'aa_failed_comparisons': failures,
        'qualified_latency_ratio': None if failures else statistics.median(ratios),
        'descriptive_rolling12211_over_radix53593_median': statistics.median(ratios),
        'descriptive_rolling12211_over_radix53593_mean': statistics.mean(ratios),
        'reference_online_ms_mean': statistics.mean(row['online_ms'] for row in ref),
        'candidate_online_ms_mean': statistics.mean(row['online_ms'] for row in cand),
        'reference_preparation_ms_mean': statistics.mean(float(row['fields']['preparation_ms']) for row in ref),
        'candidate_preparation_ms_mean': statistics.mean(float(row['fields']['preparation_ms']) for row in cand),
        'reference_retained_bytes': sorted({int(row['fields']['retained_bytes']) for row in ref}),
        'candidate_retained_bytes': sorted({int(row['fields']['retained_bytes']) for row in cand}),
        'runs_sha256': sha256((folder / 'runs.jsonl').read_bytes()).hexdigest(),
        'pairs_sha256': sha256((folder / 'pairs.jsonl').read_bytes()).hexdigest(),
    }


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True, indent=2))
