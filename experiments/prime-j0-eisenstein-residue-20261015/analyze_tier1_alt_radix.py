#!/usr/bin/env python3
"""Audit all raw arms in the frozen norm-110557 Tier 1 panel."""

from hashlib import sha256
from math import exp, log
from pathlib import Path
import json
import random
import statistics
import tarfile

HERE = Path(__file__).resolve().parent
JOB = '51a80dfd759e4d5e8d5196a0a031aa78'
STEMS = {
    'cache10': 'prime-j0-cache10-native/',
    'alt': 'prime-j0-alt-radix-native/',
}


def load(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def digest(path):
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
    rules = load(HERE/'tier1-alt-radix-cpu40-rules.json')
    planned = load(HERE/'tier1-alt-radix-cpu40-manifest.json')
    folder = HERE/JOB
    manifest, summary = load(folder/'manifest.json'), load(folder/'summary.json')
    runs, pairs = rows(folder/'runs.jsonl'), rows(folder/'pairs.jsonl')
    assert manifest == planned
    assert manifest['repetitions'] == rules['repetitions'] == 16
    assert len(runs) == 96 and len(pairs) == 48
    assert summary['expected_pairs'] == 48
    assert all(case['expected_fields']['fixture_sha256'] == rules['fixture_sha256']
               for case in manifest['cases'])
    provenance = HERE/'alt-radix-native-provenance.tar.gz'
    with tarfile.open(provenance, 'r:gz') as archive:
        for label, stem in STEMS.items():
            remote = '/workspace/bench-sources/'+stem
            for key, member in (('front','src/bin/eisenstein_fixed.rs'),
                                ('windows','src/bin/eisenstein_fixed/unit_orbit_windows.rs'),
                                ('binary','target/release/eisenstein_fixed')):
                expected = rules['hashes'][label+'_'+key]
                assert sha256(archive.extractfile(stem+member).read()).hexdigest() == expected
                assert summary['artifact_sha256'][remote+member] == expected
            fixture = archive.extractfile(stem+'src/bin/mixed640_uniform_fixture.json').read()
            assert sha256(fixture).hexdigest() == rules['fixture_sha256']
            replay_name = 'cache10-full-replay.stdout' if label == 'cache10' else 'alt-full-replay2.stdout'
            fields = dict(word.split('=',1) for word in archive.extractfile(stem+replay_name)
                          .read().decode().strip().split())
            assert fields['verified'] == '1' and fields['count'] == '12288'
            assert fields['point'] == manifest['cases'][0]['expected_result']
            assert fields['fixture_sha256'] == rules['fixture_sha256']
            assert int(fields['retained_bytes']) == rules['table_bytes'][label]
            assert int(fields['retained_bytes']) < rules['table_bytes']['cap']
            overlays = (['native_cache_uniform_overlay.py','native_cache10_overlay.py']
                        if label == 'cache10' else ['native_alt_radix_overlay.py'])
            for overlay in overlays:
                assert sha256(archive.extractfile(stem+overlay).read()).hexdigest() == rules['overlay_sha256'][overlay]
    cases = {case['id']:case for case in manifest['cases']}
    invalid = []
    for serial, run in enumerate(runs,1):
        assert run['serial'] == serial
        case = cases[run['case']]
        assert run['command'] == case[run['variant']]
        assert run['binary_sha256'] == summary['artifact_sha256'][run['command'][0]]
        if run['status'] != 'valid' or run['issues'] or run['returncode'] != 0 or run['timed_out']:
            invalid.append({'serial':serial,'status':run['status'],'issues':run['issues']})
            continue
        assert run['postflight']['ok']
        assert (folder/run['stderr_file']).read_text() == ''
        fields = dict(word.split('=',1) for word in (folder/run['stdout_file']).read_text().split())
        assert fields == run['fields']
        assert fields['verified'] == '1' and fields['point'] == case['expected_result']
        assert all(fields.get(key) == value for key,value in case['expected_fields'].items())
        assert int(fields['retained_bytes']) < rules['table_bytes']['cap']
    lookup = {(pair['repeat'],pair['case']):pair for pair in pairs}
    low,high = rules['aa_acceptance']
    aa_failures,ratios = [],[]
    for repeat in range(16):
        before,after = lookup[(repeat,'cal_before')],lookup[(repeat,'cal_after')]
        if before['status'] != 'valid' or after['status'] != 'valid' or not (
                low <= before['speedup'] <= high and low <= after['speedup'] <= high):
            aa_failures.append({'repeat':repeat,'before':before['speedup'],'after':after['speedup']})
        pair = lookup[(repeat,'compare_alt_radix')]
        if pair['status'] == 'valid' and not pair['issues']:
            ratios.append(pair['speedup'])
    bounds = interval(ratios)
    qualified = (summary['status'] == 'completed' and summary['artifacts_stable']
                 and not invalid and not aa_failures and len(ratios) == 16
                 and bounds is not None and (bounds[0] > 1 or bounds[1] < 1))
    arms = [run for run in runs if run['case'] == 'compare_alt_radix' and run['status'] == 'valid']
    ref = [run for run in arms if run['variant'] == 'reference']
    cand = [run for run in arms if run['variant'] == 'candidate']
    return {
        'schema':1,'measurement_tier':'tier1_instance','job_id':JOB,
        'instance_id':manifest['allocation']['instance_id'],
        'operations_per_arm':12288,'completed_arms':len(runs),'completed_pairs':len(pairs),
        'invalid_arms':invalid,'aa_acceptance':[low,high],'aa_failures':aa_failures,
        'artifact_stable':summary['artifacts_stable'],'runner_status':summary['status'],
        'fixture_sha256':rules['fixture_sha256'],'provenance_sha256':digest(provenance),
        'runs_sha256':digest(folder/'runs.jsonl'),'pairs_sha256':digest(folder/'pairs.jsonl'),
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
