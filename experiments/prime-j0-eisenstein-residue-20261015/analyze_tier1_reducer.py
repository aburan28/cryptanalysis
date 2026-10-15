#!/usr/bin/env python3
"""Reaudit the frozen native pair-field quotient panel and every raw arm."""
from hashlib import sha256
from math import exp, log
from pathlib import Path
import json
import random
import statistics
import tarfile

HERE = Path(__file__).resolve().parent
JOB = '16ad0015d96b497ca15cc3de3ce090e6'
STEM = '/workspace/bench-sources/eisenstein-residue-native'
FIXTURE = '/workspace/bench-sources/prime-j0-affine-uniform-native/src/bin/mixed640_uniform_fixture.json'


def digest(payload):
    return sha256(payload).hexdigest()


def load(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    rules = load(HERE / 'tier1-eisenstein-reducer-cpu40-rules.json')
    planned = load(HERE / 'tier1-eisenstein-reducer-cpu40-manifest.json')
    folder = HERE / JOB
    manifest = load(folder / 'manifest.json')
    summary = load(folder / 'summary.json')
    runs = lines(folder / 'runs.jsonl')
    pairs = lines(folder / 'pairs.jsonl')
    provenance = HERE / 'eisenstein-pair-native-provenance.tar.gz'
    assert digest((HERE / 'eisenstein_pair_native.rs').read_bytes()) == rules['source_sha256']
    with tarfile.open(provenance, 'r:gz') as archive:
        members = {member.name: member for member in archive.getmembers()}
        for name, expected in (
            ('src/bin/eisenstein_pair_native.rs', rules['source_sha256']),
            ('eisenstein_pair_native', rules['binary_sha256']),
            ('mixed640_uniform_fixture.json', rules['fixture_sha256']),
        ):
            assert digest(archive.extractfile(members[name]).read()) == expected
        assert archive.extractfile(members['native-solinas-full-replay.stderr']).read() == b''
        full = archive.extractfile(members['native-solinas-full-replay.stdout']).read().decode()
        assert 'count=12288' in full and 'verified=1' in full and 'reducer=solinas' in full
    assert manifest == planned
    assert summary['status'] == 'completed' and summary['artifacts_stable']
    assert summary['valid_pairs'] == summary['expected_pairs'] == 48
    hashes = summary['artifact_sha256']
    assert hashes[STEM + '/src/bin/eisenstein_pair_native.rs'] == rules['source_sha256']
    assert hashes[STEM + '/eisenstein_pair_native'] == rules['binary_sha256']
    assert hashes[FIXTURE] == rules['fixture_sha256']
    assert len(runs) == 96 and len(pairs) == 48
    expected = {case['id']: case for case in manifest['cases']}
    assert set(expected) == {'cal_before', 'compare', 'cal_after'}
    for serial, run in enumerate(runs, 1):
        assert run['serial'] == serial and run['status'] == 'valid'
        assert not run['issues'] and not run['timed_out'] and run['returncode'] == 0
        assert run['postflight']['ok']
        assert run['binary_sha256'] == rules['binary_sha256']
        assert (folder / run['stderr_file']).read_bytes() == b''
        fields = dict(item.split('=', 1) for item in
                      (folder / run['stdout_file']).read_text().split())
        assert fields == run['fields'] and float(fields['online_ms']) == run['online_ms']
        case = expected[run['case']]
        assert all(fields.get(key) == value for key, value in case['expected_fields'].items())
        assert run['command'] == case[run['variant']]
        assert fields['reducer'] == run['command'][-1]
    lookup = {(pair['repeat'], pair['case']): pair for pair in pairs}
    aa_failures = []
    comparisons = []
    low, high = rules['aa_acceptance']
    for repeat in range(rules['repetitions']):
        before = lookup[(repeat, 'cal_before')]
        comparison = lookup[(repeat, 'compare')]
        after = lookup[(repeat, 'cal_after')]
        assert all(pair['status'] == 'valid' and not pair['issues']
                   for pair in (before, comparison, after))
        comparisons.append(comparison['speedup'])
        if not (low <= before['speedup'] <= high and low <= after['speedup'] <= high):
            aa_failures.append({'repeat': repeat, 'before': before['speedup'],
                                'after': after['speedup'],
                                'comparison': comparison['speedup']})
    rng = random.Random(30113)
    logs = [log(ratio) for ratio in comparisons]
    boot = sorted(exp(statistics.median(logs[rng.randrange(len(logs))]
                                        for _ in logs)) for _ in range(10000))
    interval = [boot[250], boot[9749]]
    qualified = not aa_failures and (interval[0] > 1 or interval[1] < 1)
    comparisons_rows = [run for run in runs if run['case'] == 'compare']
    division = [run['online_ms'] for run in comparisons_rows
                if run['variant'] == 'reference']
    solinas = [run['online_ms'] for run in comparisons_rows
               if run['variant'] == 'candidate']
    return {
        'schema': 1, 'measurement_tier': 'tier1_instance',
        'job_id': JOB, 'instance_id': manifest['allocation']['instance_id'],
        'scalars_per_arm': 128, 'completed_arms': len(runs),
        'completed_pairs': len(pairs), 'artifact_stable': True,
        'aa_acceptance': [low, high], 'aa_failures': aa_failures,
        'paired_bootstrap95_by_repeat': interval,
        'descriptive_division_over_solinas_median': statistics.median(comparisons),
        'qualified_comparison_ratio': statistics.median(comparisons) if qualified else None,
        'aggregate_status': 'qualified' if qualified else 'unknown_after_tier_gate',
        'division_online_ms_mean': statistics.mean(division),
        'solinas_online_ms_mean': statistics.mean(solinas),
        'source_sha256': rules['source_sha256'],
        'binary_sha256': rules['binary_sha256'],
        'fixture_sha256': rules['fixture_sha256'],
        'provenance_sha256': digest(provenance.read_bytes()),
        'runs_sha256': digest((folder / 'runs.jsonl').read_bytes()),
        'pairs_sha256': digest((folder / 'pairs.jsonl').read_bytes()),
    }


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True, indent=2))
