#!/usr/bin/env python3
"""Reaudit the bounded-limb pair-field comparison and its raw Tier 1 arms."""
from hashlib import sha256
from math import exp, log
from pathlib import Path
import json
import random
import statistics
import tarfile

HERE = Path(__file__).resolve().parent
JOB = 'c325c7ff36a74f0c8cd85db3024432f8'
STEM = '/workspace/bench-sources/eisenstein-residue-native'
FIXTURE = '/workspace/bench-sources/prime-j0-affine-uniform-native/src/bin/mixed640_uniform_fixture.json'


def digest(payload):
    return sha256(payload).hexdigest()


def load(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    rules = load(HERE / 'tier1-eisenstein-fixed-cpu40-rules.json')
    planned = load(HERE / 'tier1-eisenstein-fixed-cpu40-manifest.json')
    folder = HERE / JOB
    manifest = load(folder / 'manifest.json')
    summary = load(folder / 'summary.json')
    runs = lines(folder / 'runs.jsonl')
    pairs = lines(folder / 'pairs.jsonl')
    provenance = HERE / 'eisenstein-pair-fixed-provenance.tar.gz'
    assert digest((HERE / 'eisenstein_pair_fixed.rs').read_bytes()) == rules['candidate_front_sha256']
    assert digest((HERE / 'eisenstein_pair_fixed_int.rs').read_bytes()) == rules['candidate_limb_sha256']
    with tarfile.open(provenance, 'r:gz') as archive:
        members = {member.name: member for member in archive.getmembers()}
        for name, expected in (
            ('src/bin/eisenstein_pair_native.rs', rules['reference_source_sha256']),
            ('src/bin/eisenstein_pair_fixed.rs', rules['candidate_front_sha256']),
            ('src/bin/eisenstein_pair_fixed_int.rs', rules['candidate_limb_sha256']),
            ('eisenstein_pair_native', rules['reference_binary_sha256']),
            ('eisenstein_pair_fixed', rules['candidate_binary_sha256']),
            ('mixed640_uniform_fixture.json', rules['fixture_sha256']),
        ):
            assert digest(archive.extractfile(members[name]).read()) == expected
        assert archive.extractfile(members['fixed-full-replay.stderr']).read() == b''
        replay = archive.extractfile(members['fixed-full-replay.stdout']).read().decode()
        assert 'count=12288' in replay and 'verified=1' in replay
        test = archive.extractfile(members['fixed-limb-test.stdout']).read().decode()
        assert '1 passed; 0 failed' in test
    assert manifest == planned
    assert summary['status'] == 'completed' and summary['artifacts_stable']
    assert summary['valid_pairs'] == summary['expected_pairs'] == 48
    hashes = summary['artifact_sha256']
    for path, expected in (
        (STEM+'/src/bin/eisenstein_pair_native.rs', rules['reference_source_sha256']),
        (STEM+'/src/bin/eisenstein_pair_fixed.rs', rules['candidate_front_sha256']),
        (STEM+'/src/bin/eisenstein_pair_fixed_int.rs', rules['candidate_limb_sha256']),
        (STEM+'/eisenstein_pair_native', rules['reference_binary_sha256']),
        (STEM+'/eisenstein_pair_fixed', rules['candidate_binary_sha256']),
        (FIXTURE, rules['fixture_sha256']),
    ):
        assert hashes[path] == expected
    assert len(runs) == 96 and len(pairs) == 48
    expected_cases = {case['id']: case for case in manifest['cases']}
    assert set(expected_cases) == {'cal_before', 'compare', 'cal_after'}
    for serial, run in enumerate(runs,1):
        assert run['serial'] == serial and run['status'] == 'valid'
        assert not run['issues'] and not run['timed_out'] and run['returncode'] == 0
        assert run['postflight']['ok'] and (folder/run['stderr_file']).read_bytes() == b''
        case = expected_cases[run['case']]
        assert run['command'] == case[run['variant']]
        fields = dict(item.split('=',1) for item in
                      (folder/run['stdout_file']).read_text().split())
        assert fields == run['fields'] and float(fields['online_ms']) == run['online_ms']
        assert fields['count'] == '128' and fields['verified'] == '1'
        assert fields['packed_x_bytes'] == '33' and fields['reducer'] == 'solinas'
        if run['command'][0] == STEM+'/eisenstein_pair_fixed':
            assert fields['scheme'] == 'eisenstein_pair_fixed'
            assert run['binary_sha256'] == rules['candidate_binary_sha256']
        else:
            assert fields['scheme'] == 'eisenstein_pair_bigint'
            assert run['binary_sha256'] == rules['reference_binary_sha256']
    lookup = {(pair['repeat'],pair['case']):pair for pair in pairs}
    low,high = rules['aa_acceptance']
    aa_failures=[]
    ratios=[]
    for repeat in range(rules['repetitions']):
        before=lookup[(repeat,'cal_before')]
        comparison=lookup[(repeat,'compare')]
        after=lookup[(repeat,'cal_after')]
        assert all(pair['status']=='valid' and not pair['issues']
                   for pair in (before,comparison,after))
        ratios.append(comparison['speedup'])
        if not (low<=before['speedup']<=high and low<=after['speedup']<=high):
            aa_failures.append({'repeat':repeat,'before':before['speedup'],
                                'after':after['speedup'],
                                'comparison':comparison['speedup']})
    rng=random.Random(30114)
    logs=[log(ratio) for ratio in ratios]
    boot=sorted(exp(statistics.median(logs[rng.randrange(len(logs))]
                                      for _ in logs)) for _ in range(10000))
    interval=[boot[250],boot[9749]]
    qualified=not aa_failures and (interval[0]>1 or interval[1]<1)
    comparison_runs=[row for row in runs if row['case']=='compare']
    bigint=[row['online_ms'] for row in comparison_runs if row['variant']=='reference']
    fixed=[row['online_ms'] for row in comparison_runs if row['variant']=='candidate']
    return {
        'schema':1,'measurement_tier':'tier1_instance','job_id':JOB,
        'instance_id':manifest['allocation']['instance_id'],
        'scalars_per_arm':128,'completed_arms':len(runs),'completed_pairs':len(pairs),
        'artifact_stable':True,'aa_acceptance':[low,high],'aa_failures':aa_failures,
        'paired_bootstrap95_by_repeat':interval,
        'descriptive_bigint_over_fixed_median':statistics.median(ratios),
        'qualified_comparison_ratio':statistics.median(ratios) if qualified else None,
        'aggregate_status':'qualified' if qualified else 'unknown_after_tier_gate',
        'bigint_online_ms_mean':statistics.mean(bigint),
        'fixed_online_ms_mean':statistics.mean(fixed),
        'reference_binary_sha256':rules['reference_binary_sha256'],
        'candidate_binary_sha256':rules['candidate_binary_sha256'],
        'fixture_sha256':rules['fixture_sha256'],
        'provenance_sha256':digest(provenance.read_bytes()),
        'runs_sha256':digest((folder/'runs.jsonl').read_bytes()),
        'pairs_sha256':digest((folder/'pairs.jsonl').read_bytes()),
    }


if __name__=='__main__':
    print(json.dumps(audit(),sort_keys=True,indent=2))
