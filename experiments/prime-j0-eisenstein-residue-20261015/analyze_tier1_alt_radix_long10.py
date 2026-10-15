#!/usr/bin/env python3
"""Audit every long-arm Tier 1 record against its frozen acceptance contract."""

from hashlib import sha256
from math import exp, log
from pathlib import Path
import json
import random
import statistics

HERE = Path(__file__).resolve().parent
JOB = '14dd3766e7d643e380872b915398ce96'
ROOT = '/workspace/bench-sources'
PANEL = '/workspace/isolated-bench/panels'
STEMS = {'cache10': 'prime-j0-cache10-long10',
         'alt': 'prime-j0-alt-radix-long10'}


def load(path: Path):
    return json.loads(path.read_text())


def rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def digest(path: Path):
    return sha256(path.read_bytes()).hexdigest()


def interval(values):
    if len(values) != 16:
        return None
    logs = [log(value) for value in values]
    rng = random.Random(20261015)
    boot = sorted(exp(statistics.median(logs[rng.randrange(16)] for _ in range(16)))
                  for _ in range(10000))
    return [boot[250], boot[9749]]


def audit():
    rules = load(HERE/'tier1-alt-radix-long10-cpu40-rules.json')
    planned = load(HERE/'tier1-alt-radix-long10-cpu40-manifest.json')
    launch = load(HERE/'tier1-alt-radix-long10-launch.json')
    folder = HERE/JOB
    manifest, summary = load(folder/'manifest.json'), load(folder/'summary.json')
    runs, pairs = rows(folder/'runs.jsonl'), rows(folder/'pairs.jsonl')
    assert launch['job_id'] == JOB
    assert launch['manifest_sha256'] == digest(HERE/'tier1-alt-radix-long10-cpu40-manifest.json')
    assert launch['rules_sha256'] == digest(HERE/'tier1-alt-radix-long10-cpu40-rules.json')
    assert manifest == planned
    assert manifest['repetitions'] == rules['repetitions'] == 16
    assert manifest['outer_repeats'] == rules['outer_repeats'] == 10
    assert len(runs) == 96 and len(pairs) == 48
    assert summary['expected_pairs'] == 48
    assert summary['artifact_sha256'][f'{PANEL}/tier1-alt-radix-long10-cpu40-rules.json'] == launch['rules_sha256']
    assert summary['artifact_sha256'][f'{PANEL}/native_long_alt_panel_overlay.py'] == rules['hashes']['overlay']
    for label, stem in STEMS.items():
        for key, member in (('front','src/bin/eisenstein_fixed.rs'),
                            ('windows','src/bin/eisenstein_fixed/unit_orbit_windows.rs'),
                            ('binary','target/release/eisenstein_fixed')):
            assert summary['artifact_sha256'][f'{ROOT}/{stem}/{member}'] == rules['hashes'][f'{label}_{key}']
        assert summary['artifact_sha256'][f'{ROOT}/{stem}/src/bin/mixed640_uniform_fixture.json'] == rules['fixture_sha256']
    cases = {case['id']:case for case in manifest['cases']}
    invalid = []
    for serial, run in enumerate(runs, 1):
        assert run['serial'] == serial
        case = cases[run['case']]
        assert run['command'] == case[run['variant']]
        assert run['binary_sha256'] == summary['artifact_sha256'][run['command'][0]]
        if run['status'] != 'valid' or run['issues'] or run['returncode'] != 0 or run['timed_out']:
            invalid.append({'serial':serial, 'status':run['status'], 'issues':run['issues']})
            continue
        assert run['postflight']['ok']
        assert (folder/run['stderr_file']).read_text() == ''
        fields = dict(word.split('=',1) for word in (folder/run['stdout_file']).read_text().split())
        assert fields == run['fields']
        assert fields['verified'] == '1' and fields['point'] == case['expected_result']
        assert all(fields.get(key) == value for key,value in case['expected_fields'].items())
        assert int(fields['retained_bytes']) < rules['table_bytes']['cap']
    lookup = {(pair['repeat'], pair['case']):pair for pair in pairs}
    low, high = rules['aa_acceptance']
    aa_failures, ratios = [], []
    for repeat in range(16):
        before, after = lookup[(repeat,'cal_before')], lookup[(repeat,'cal_after')]
        if before['status'] != 'valid' or after['status'] != 'valid' or not (
                low <= before['speedup'] <= high and low <= after['speedup'] <= high):
            aa_failures.append({'repeat':repeat, 'before':before['speedup'],
                                'after':after['speedup']})
        pair = lookup[(repeat,'compare_alt_radix')]
        if pair['status'] == 'valid' and not pair['issues']:
            ratios.append(pair['speedup'])
    bounds = interval(ratios)
    tier_gate_passed = (summary['status'] == 'completed' and summary['artifacts_stable']
                        and not invalid and not aa_failures and len(ratios) == 16)
    directional = bounds is not None and (bounds[0] > 1 or bounds[1] < 1)
    qualified = tier_gate_passed and directional
    arms = [run for run in runs if run['case'] == 'compare_alt_radix' and run['status'] == 'valid']
    ref = [run for run in arms if run['variant'] == 'reference']
    cand = [run for run in arms if run['variant'] == 'candidate']
    return {
        'schema':1, 'measurement_tier':'tier1_instance', 'job_id':JOB,
        'instance_id':manifest['allocation']['instance_id'],
        'operations_per_arm':122880, 'completed_arms':len(runs),
        'completed_pairs':len(pairs), 'invalid_arms':invalid,
        'aa_acceptance':[low,high], 'aa_failures':aa_failures,
        'artifact_stable':summary['artifacts_stable'],
        'runner_status':summary['status'], 'tier_gate_passed':tier_gate_passed,
        'fixture_sha256':rules['fixture_sha256'],
        'runs_sha256':digest(folder/'runs.jsonl'),
        'pairs_sha256':digest(folder/'pairs.jsonl'),
        'comparison':{
            'valid_pairs':len(ratios),
            'descriptive_reference_over_candidate_median':statistics.median(ratios) if ratios else None,
            'paired_bootstrap95_by_repeat':bounds,
            'aggregate_status':'qualified' if qualified else 'unknown_after_tier_gate',
            'qualified_comparison_ratio':statistics.median(ratios) if qualified else None,
            'reference_online_ms_mean':statistics.mean(run['online_ms'] for run in ref) if ref else None,
            'candidate_online_ms_mean':statistics.mean(run['online_ms'] for run in cand) if cand else None,
            'reference_retained_bytes':sorted({int(run['fields']['retained_bytes']) for run in ref}),
            'candidate_retained_bytes':sorted({int(run['fields']['retained_bytes']) for run in cand}),
        },
    }


if __name__ == '__main__':
    print(json.dumps(audit(),sort_keys=True,indent=2))
