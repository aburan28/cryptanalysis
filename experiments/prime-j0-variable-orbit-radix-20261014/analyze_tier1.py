#!/usr/bin/env python3
"""Audit every arm and the frozen A/A gate for the 18-versus-17 panel."""
from hashlib import sha256
import json
from math import exp, log
from pathlib import Path
import random
import re
import statistics

HERE = Path(__file__).resolve().parent
JOB = 'afe0e12317f848c4a69ac76671362ce6'
OPERATIONS_PER_ARM = 128*64


def load(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    rules = load(HERE / 'tier1-18v17-rules.json')
    planned = load(HERE / 'tier1-18v17-manifest.json')
    folder = HERE / JOB
    manifest = load(folder / 'manifest.json')
    summary = load(folder / 'summary.json')
    runs = lines(folder / 'runs.jsonl')
    pairs = lines(folder / 'pairs.jsonl')
    assert manifest == planned
    assert summary['status'] == 'completed' and summary['artifacts_stable']
    assert len(runs) == 2*len(manifest['cases'])*rules['repetitions'] == 96
    assert len(pairs) == len(manifest['cases'])*rules['repetitions'] == 48
    assert summary['valid_pairs'] == summary['expected_pairs'] == len(pairs)
    expected = {case['id']: case for case in manifest['cases']}
    for serial, run in enumerate(runs, 1):
        assert run['serial'] == serial and run['status'] == 'valid'
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
    rng = random.Random(19183)
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
        'operations_per_arm': OPERATIONS_PER_ARM,
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
        'reference_us_per_scalar': 1000*ref_ms/OPERATIONS_PER_ARM,
        'candidate_us_per_scalar': 1000*cand_ms/OPERATIONS_PER_ARM,
        'reference_preparation_ms_mean': statistics.mean(float(row['fields']['preparation_ms']) for row in reference),
        'candidate_preparation_ms_mean': statistics.mean(float(row['fields']['preparation_ms']) for row in candidate),
        'reference_retained_bytes': sorted({int(row['fields']['retained_bytes']) for row in reference}),
        'candidate_retained_bytes': sorted({int(row['fields']['retained_bytes']) for row in candidate}),
        'runs_sha256': sha256((folder / 'runs.jsonl').read_bytes()).hexdigest(),
        'pairs_sha256': sha256((folder / 'pairs.jsonl').read_bytes()).hexdigest(),
    }


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True, indent=2))
