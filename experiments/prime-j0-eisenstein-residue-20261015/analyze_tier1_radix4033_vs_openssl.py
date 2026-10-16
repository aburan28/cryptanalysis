#!/usr/bin/env python3
"""Audit frozen OpenSSL fixed-base and norm-4033 paired Tier 1 panels."""
from hashlib import sha256
from math import exp, isfinite, log
from pathlib import Path
import json
import random
import statistics
import sys
import tarfile

from check_secp256k1_tau_generator import G, N, mul

HERE = Path(__file__).resolve().parent


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def interval(ratios):
    if len(ratios) != 16:
        return None
    values = [log(value) for value in ratios]
    rng = random.Random(20261015)
    draws = sorted(exp(statistics.median(values[rng.randrange(16)] for _ in range(16)))
                   for _ in range(10000))
    return [draws[250], draws[9749]]


def audit(count, fixed_table=False):
    assert count in (1, 128)
    variant = '-fixed-table' if fixed_table else ''
    stem = f'tier1-radix4033-vs-openssl{variant}-{count}-cpu40'
    launch = load(HERE / f'{stem}-launch.json')
    manifest = load(HERE / f'{stem}-manifest.json')
    rules = load(HERE / f'{stem}-rules.json')
    raw = HERE / f'radix4033-vs-openssl{variant}-{count}-raw.tar.gz'
    openssl_archive = HERE / 'openssl-secp256k1-native-provenance.tar.gz'
    candidate_archive = HERE / 'radix4033-native-provenance.tar.gz'
    assert digest(raw) == launch['raw_archive_sha256']
    assert digest(openssl_archive) == launch['openssl_provenance_sha256']
    assert digest(candidate_archive) == launch['candidate_provenance_sha256']
    assert digest(HERE / f'{stem}-manifest.json') == launch['manifest_sha256']
    assert digest(HERE / f'{stem}-rules.json') == launch['rules_sha256']

    paths = rules['paths']
    hashes = rules['hashes']
    with tarfile.open(openssl_archive, 'r:gz') as provenance:
        for key in ('openssl_source', 'openssl_fixture', 'openssl_binary', 'libcrypto'):
            assert sha256(provenance.extractfile(paths[key].lstrip('/')).read()).hexdigest() == hashes[key]
    assert digest(HERE / 'openssl_secp256k1_baseline.c') == hashes['openssl_source']
    assert digest(HERE / 'openssl-secp256k1-first128-fixture.txt') == hashes['openssl_fixture']

    with tarfile.open(candidate_archive, 'r:gz') as provenance:
        prefix = 'bench-sources/prime-j0-sparse-radix4033/'
        fixture_bytes = provenance.extractfile(prefix + 'src/bin/mixed640_uniform_fixture.json').read()
        old_rules = load(HERE / 'tier1-radix4033-1-cpu40-rules.json')
        expected = {
            'candidate_source': old_rules['hashes']['candidate_front'],
            'candidate_windows': old_rules['hashes']['candidate_windows'],
            'candidate_fixture': old_rules['fixture_sha256'],
            'candidate_binary': old_rules['hashes']['candidate_binary'],
            'candidate_overlay': old_rules['hashes']['candidate_overlay'],
        }
        for key, value in expected.items():
            member = paths[key].removeprefix('/workspace/')
            assert sha256(provenance.extractfile(member).read()).hexdigest() == value
    original = json.loads(fixture_bytes)['cases'][:128]
    text_lines = (HERE / 'openssl-secp256k1-first128-fixture.txt').read_text().splitlines()
    assert len(text_lines) == len(original) == 128
    for line, case in zip(text_lines, original):
        assert line == case['scalar_hex'] + ' ' + case['point_hex']
    for case in original[:count]:
        result = mul(int(case['scalar_hex'], 16) % N, G)
        assert ':'.join(f'{value:064x}' for value in result) == case['point_hex']
    assert original[count - 1]['point_hex'] == rules['expected_point_hex']

    job = launch['job_id']
    with tarfile.open(raw, 'r:gz') as archive:
        assert all(name == job or name.startswith(job + '/') for name in archive.getnames())
        def read(name):
            return archive.extractfile(job + '/' + name).read()
        actual_manifest = json.loads(read('manifest.json'))
        summary = json.loads(read('summary.json'))
        runs_bytes, pairs_bytes = read('runs.jsonl'), read('pairs.jsonl')
        runs = [json.loads(line) for line in runs_bytes.splitlines()]
        pairs = [json.loads(line) for line in pairs_bytes.splitlines()]
        assert actual_manifest == manifest and len(runs) == 96 and len(pairs) == 48
        assert summary['expected_pairs'] == 48
        artifact_hashes = summary['artifact_sha256']
        assert artifact_hashes['/workspace/isolated-bench/panels/' + stem + '-rules.json'] == launch['rules_sha256']
        for key, path in paths.items():
            if key in hashes:
                assert artifact_hashes[path] == hashes[key]
        old = load(HERE / 'tier1-radix4033-1-cpu40-rules.json')
        for key, expected in [('candidate_source', old['hashes']['candidate_front']),
                              ('candidate_windows', old['hashes']['candidate_windows']),
                              ('candidate_fixture', old['fixture_sha256']),
                              ('candidate_binary', old['hashes']['candidate_binary']),
                              ('candidate_overlay', old['hashes']['candidate_overlay'])]:
            assert artifact_hashes[paths[key]] == expected
        cases_by_id = {case['id']: case for case in manifest['cases']}
        run_lookup, invalid, preparation, candidate_preparation = {}, [], [], []
        for serial, run in enumerate(runs, 1):
            assert run['serial'] == serial
            case = cases_by_id[run['case']]
            assert run['command'] == case[run['variant']]
            assert run['binary_sha256'] == artifact_hashes[run['command'][0]]
            assert read(run['stderr_file']) == b''
            fields = dict(word.split('=', 1) for word in read(run['stdout_file']).decode().split())
            assert fields == run['fields']
            assert fields['verified'] == '1' and int(fields['count']) == count
            assert fields['point'] == rules['expected_point_hex'] == case['expected_result']
            assert isfinite(float(fields['online_ms'])) and float(fields['online_ms']) > 0
            assert isfinite(float(fields['preparation_ms'])) and float(fields['preparation_ms']) >= 0
            if run['command'][0] == paths['openssl_binary']:
                preparation.append(float(fields['preparation_ms']))
            elif fixed_table:
                assert int(fields['retained_bytes']) == rules['expected_candidate_retained_bytes']
                candidate_preparation.append(float(fields['preparation_ms']))
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
                aa_failures.append({'repeat': repeat, 'case': name, 'ratio': ratio,
                                    'pair_status': pair['status']})
        pair = pair_lookup[(repeat, 'compare_radix4033')]
        a, b = (run_lookup[(repeat, 'compare_radix4033', variant)]
                for variant in ('reference', 'candidate'))
        if pair['status'] == 'valid' and not pair['issues']:
            x, y = float(a['fields']['online_ms']), float(b['fields']['online_ms'])
            reference.append(x)
            candidate.append(y)
            ratios.append(x / y)
    bounds = interval(ratios)
    gate = (summary['status'] == 'completed' and summary['measurement_tier'] == 'tier1_instance'
            and summary['artifacts_stable'] and not invalid and not aa_failures and len(ratios) == 16)
    qualified = gate and bounds is not None and (bounds[0] > 1 or bounds[1] < 1)
    receipt = {'schema': 1, 'job_id': job, 'measurement_tier': 'tier1_instance',
               'frozen_outputs_independently_replayed': count,
               'runner_status': summary['status'], 'artifact_stable': summary['artifacts_stable'],
               'completed_arms': len(runs), 'completed_pairs': len(pairs),
               'invalid_arms': invalid, 'aa_failures': aa_failures, 'tier_gate_passed': gate,
               'raw_archive_sha256': digest(raw),
               'openssl_provenance_sha256': digest(openssl_archive),
               'candidate_provenance_sha256': digest(candidate_archive),
               'runs_sha256': sha256(runs_bytes).hexdigest(),
               'pairs_sha256': sha256(pairs_bytes).hexdigest(),
               'openssl_warmup_ms_mean': statistics.mean(preparation),
               'candidate_table_preparation_ms_mean': (
                   statistics.mean(candidate_preparation) if candidate_preparation else None),
               'candidate_retained_bytes': rules.get('expected_candidate_retained_bytes'),
               'comparison': {'valid_pairs': len(ratios),
                              'reference_ms_mean': statistics.mean(reference) if reference else None,
                              'candidate_ms_mean': statistics.mean(candidate) if candidate else None,
                              'descriptive_reference_over_candidate_median': statistics.median(ratios) if ratios else None,
                              'paired_bootstrap95_by_repeat': bounds,
                              'aggregate_status': 'qualified' if qualified else 'unknown_after_tier_gate',
                              'qualified_ratio': statistics.median(ratios) if qualified else None}}
    (HERE / f'{stem}-audit.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    return receipt


if __name__ == '__main__':
    fixed_table = '--fixed-table' in sys.argv[1:]
    counts = tuple(int(arg) for arg in sys.argv[1:] if arg != '--fixed-table') or (1, 128)
    print(json.dumps([audit(count, fixed_table) for count in counts], indent=2, sort_keys=True))
