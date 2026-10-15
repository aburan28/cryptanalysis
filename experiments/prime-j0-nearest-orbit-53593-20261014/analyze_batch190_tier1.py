#!/usr/bin/env python3
"""Audit the frozen 2048-operation-per-arm RunPod throughput panel."""
from hashlib import sha256
import json
from math import exp, log
from pathlib import Path
import random
import re
import statistics

ROOT = Path(__file__).resolve().parent / 'tier1-runpod-20261014'
JOB = 'c78ecb1ef4e2403fbf9d768f4432cc67'


def load(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    rules = load(ROOT / 'panels/batch190-rules.json')
    planned = load(ROOT / 'panels/radix53593-vs-radix35533-batch.json')
    folder = ROOT / JOB
    manifest = load(folder / 'manifest.json')
    summary = load(folder / 'summary.json')
    runs = rows(folder / 'runs.jsonl')
    pairs = rows(folder / 'pairs.jsonl')
    assert manifest == planned
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
    comparison = []
    for repeat in range(rules['repetitions']):
        before = lookup[(repeat, 'cal_before')]
        measured = lookup[(repeat, 'compare')]
        after = lookup[(repeat, 'cal_after')]
        assert all(item['status'] == 'valid' for item in (before, measured, after))
        comparison.append(measured['speedup'])
        if not (low <= before['speedup'] <= high and
                low <= after['speedup'] <= high):
            failures.append({'repeat': repeat,
                             'before_ratio': before['speedup'],
                             'after_ratio': after['speedup'],
                             'comparison_ratio': measured['speedup']})
    log_ratios = [log(value) for value in comparison]
    rng = random.Random(35533)
    boot = sorted(exp(statistics.median(
        log_ratios[rng.randrange(len(log_ratios))] for _ in log_ratios))
                  for _ in range(10000))
    ci = [boot[250], boot[9749]]
    qualified = not failures and (ci[0] > 1 or ci[1] < 1)
    compare_runs = [row for row in runs if row['case'] == 'compare']
    ref = [row for row in compare_runs if row['variant'] == 'reference']
    cand = [row for row in compare_runs if row['variant'] == 'candidate']
    ref_ms = statistics.mean(row['online_ms'] for row in ref)
    cand_ms = statistics.mean(row['online_ms'] for row in cand)
    return {
        'measurement_tier': 'tier1_instance',
        'workload': '128 frozen scalars times 16 passes per arm',
        'operations_per_arm': 2048,
        'runpod_instance_id': manifest['allocation']['instance_id'],
        'job': JOB,
        'completed_runs': len(runs),
        'completed_pairs': len(pairs),
        'artifact_stable': summary['artifacts_stable'],
        'aa_acceptance_range': [low, high],
        'aa_failed_comparisons': failures,
        'paired_bootstrap95_by_repeat': ci,
        'qualified_comparison_ratio': statistics.median(comparison) if qualified else None,
        'descriptive_radix53593_over_radix35533_median': statistics.median(comparison),
        'reference_online_ms_mean': ref_ms,
        'candidate_online_ms_mean': cand_ms,
        'reference_us_per_scalar': 1000*ref_ms/2048,
        'candidate_us_per_scalar': 1000*cand_ms/2048,
        'reference_preparation_ms_mean': statistics.mean(float(row['fields']['preparation_ms']) for row in ref),
        'candidate_preparation_ms_mean': statistics.mean(float(row['fields']['preparation_ms']) for row in cand),
        'reference_retained_bytes': sorted({int(row['fields']['retained_bytes']) for row in ref}),
        'candidate_retained_bytes': sorted({int(row['fields']['retained_bytes']) for row in cand}),
        'runs_sha256': sha256((folder / 'runs.jsonl').read_bytes()).hexdigest(),
        'pairs_sha256': sha256((folder / 'pairs.jsonl').read_bytes()).hexdigest(),
    }


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True, indent=2))
