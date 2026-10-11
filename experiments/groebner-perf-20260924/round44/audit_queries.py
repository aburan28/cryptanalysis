"""Offline original-ANF root completeness and reduced-basis audit; no native code."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import sys

from tagged_reference import certify_roots

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'round27'))
from reference import verify_basis


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = json.loads(gzip.decompress(args.input.read_bytes()))
    assert report['schema'] == 'partial-affine-query-validation/1' and report['status'] == 'PASS'
    assert sha(HERE / 'validate_native.py') == report['validator_sha256']
    fixture_path = HERE.parent / 'round40/fixtures/inputs.json.gz'
    assert sha(fixture_path) == report['fixture_sha256']
    fixtures = {i['name']: i for i in json.loads(gzip.decompress(fixture_path.read_bytes()))}
    receipt_path = HERE / 'build/receipt.json'
    assert sha(receipt_path) == report['build_receipt_sha256']
    receipt = json.loads(receipt_path.read_text())
    sources = {str(HERE.parent / name): value for name, value in receipt['sources'].items()}
    for name, expected in sources.items():
        assert sha(Path(name)) == expected
    builds = {('cpu', False), ('cpu', True)}
    if report['metal']['status'] == 'AVAILABLE':
        builds.add(('metal', False))
    expected_arms = {(backend, sanitizer, enabled) for backend, sanitizer in builds for enabled in (False, True)}
    assert len(report['queries']) == 18 * len(expected_arms)
    seen, records, proofs = set(), [], set()
    disabled = {}
    journal_path = args.output.with_suffix(args.output.suffix + '.jsonl')
    with journal_path.open('x') as journal:
        for row in report['queries']:
            arm = row['backend'], row['sanitizer'], row['partial_enabled']
            key = row['name'], arm
            assert key not in seen and arm in expected_arms
            seen.add(key)
            item, answer = fixtures[row['name']], row['result']
            assert row['workload_sha256'] == item['workload_sha256']
            assert answer['status'] == 'solved' and answer['verified']
            raw = base64.b64decode(report['proofs'][answer['proof_sha256']], validate=True)
            assert hashlib.sha256(raw).hexdigest() == answer['proof_sha256']
            roots, constants, extended, partials, assignments = certify_roots(
                2 * item['ell'], item['ell'], item['n'], tuple(tuple(v) for v in item['reference_anf']),
                raw, answer['proof_byteorder'])
            roots = list(roots)
            assert roots == answer['basis_certificate']['solutions']
            assert verify_basis(item['nvars'], item['reference_anf'], roots, answer['basis_terms'], len(roots))
            assert answer['assignment'] in roots
            cert = answer['basis_certificate']
            stats, part = cert['stats'], cert['partial_stats']
            assert stats['contradictions'] == constants + len(extended) + sum(v[2] for v in partials)
            assert stats['extended_contradictions'] == len(extended)
            assert stats['assignments'] == assignments
            assert part['records'] == len(partials)
            assert part['rank_sum'] == sum(v[1] for v in partials)
            assert part['assignments'] == sum(v[3] for v in partials)
            assert part['inconsistent'] == sum(v[2] for v in partials)
            production, symmetry = answer['partial_stats'], answer['symmetry_stats']
            assert production['handled_branches'] + production['copied_records'] == len(partials)
            if not row['partial_enabled']:
                assert not partials and not production['attempts']
                disabled[key[:1] + arm[:2]] = answer
            else:
                prior = disabled[key[:1] + arm[:2]]
                assert prior['basis_terms'] == answer['basis_terms']
                assert prior['basis_certificate']['solutions'] == roots
            assert answer['multiplier_stats']['certified_branches'] + symmetry['affine_copies'] - production['copied_records'] == len(extended)
            expected_gpu = row['backend'] == 'metal' and item['n'] <= 32
            assert bool(answer['metrics']['gpu_used']) == expected_gpu
            proofs.add(answer['proof_sha256'])
            record = {'name': row['name'], 'backend': row['backend'], 'sanitizer': row['sanitizer'],
                      'partial_enabled': row['partial_enabled'], 'workload_sha256': item['workload_sha256'],
                      'proof_sha256': answer['proof_sha256'], 'constant_identities': constants,
                      'multiplier_identities': len(extended), 'partial_records': len(partials),
                      'partial_rank_sum': part['rank_sum'], 'partial_assignments': part['assignments'],
                      'assignments': assignments, 'roots': roots, 'reduced_basis_verified': True, 'gpu_used': expected_gpu}
            records.append(record)
            journal.write(json.dumps(record, separators=(',', ':')) + '\n')
            journal.flush()
            print('ORIGINAL_ANF_AUDIT_PASS', *key, flush=True)
    assert seen == {(name, arm) for name in fixtures for arm in expected_arms}
    for name, expected in sources.items():
        assert sha(Path(name)) == expected
    result = {'schema': 'partial-affine-original-anf-audit/1', 'status': 'PASS',
              'scope': 'Every original-equation witness checked, affine rank recomputed, every residual assignment exhausted; exact reduced basis checked. No native code loaded. Audit-only cache is outside all query timing.',
              'input_sha256': sha(args.input), 'source_sha256': sources,
              'fixture_sha256': sha(fixture_path), 'records': records, 'unique_proofs': len(proofs),
              'timing_eligible': False, 'candidate_id': None, 'online_speedup': None}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('INDEPENDENT_AUDIT_PASS', len(records), 'query records;', len(proofs), 'unique proofs', flush=True)


if __name__ == '__main__':
    main()
