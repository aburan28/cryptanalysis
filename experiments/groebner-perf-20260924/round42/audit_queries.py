"""Offline original-ANF completeness and reduced-basis audit, without native code."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'round34'))
from affine_reference import certify_roots
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
    assert report['status'] == 'PASS'
    assert sha(HERE / 'validate_native.py') == report['validator_sha256']
    fixture_path = HERE.parent / 'round40/fixtures/inputs.json.gz'
    assert sha(fixture_path) == report['fixture_sha256']
    fixtures = {i['name']: i for i in json.loads(gzip.decompress(fixture_path.read_bytes()))}
    receipt_path = HERE / 'build/receipt.json'
    assert sha(receipt_path) == report['build_receipt_sha256']
    receipt = json.loads(receipt_path.read_text())
    sources = {str(HERE.parent / name): value for name, value in receipt['sources'].items()}
    for path in (HERE.parent / 'round34/affine_reference.py', HERE.parent / 'round27/reference.py', Path(__file__)):
        sources[str(path)] = sha(path)
    for name, expected in sources.items():
        assert sha(Path(name)) == expected
    expected_arms = {('cpu', False), ('cpu', True)}
    if report['metal']['status'] == 'AVAILABLE':
        expected_arms.add(('metal', False))
    assert len(report['queries']) == 18 * len(expected_arms)
    seen, records, proofs = set(), [], set()
    journal_path = args.output.with_suffix(args.output.suffix + '.jsonl')
    with journal_path.open('x') as journal:
        for row in report['queries']:
            arm = (row['backend'], row['sanitizer'])
            key = row['name'], arm
            assert key not in seen and arm in expected_arms
            seen.add(key)
            item, answer = fixtures[row['name']], row['result']
            assert row['workload_sha256'] == item['workload_sha256']
            assert answer['status'] == 'solved' and answer['verified']
            raw = base64.b64decode(report['proofs'][answer['proof_sha256']], validate=True)
            assert hashlib.sha256(raw).hexdigest() == answer['proof_sha256']
            roots, constants, extended, assignments = certify_roots(2 * item['ell'], item['ell'], item['n'],
                tuple(tuple(v) for v in item['reference_anf']), raw, answer['proof_byteorder'])
            roots = list(roots)
            assert roots == answer['basis_certificate']['solutions']
            assert verify_basis(item['nvars'], item['reference_anf'], roots, answer['basis_terms'], len(roots))
            assert answer['assignment'] in roots
            stats = answer['basis_certificate']['stats']
            assert stats['contradictions'] == constants + len(extended)
            assert stats['extended_contradictions'] == len(extended)
            assert stats['assignments'] == assignments
            expected_gpu = row['backend'] == 'metal' and item['n'] <= 32
            assert bool(answer['metrics']['gpu_used']) == expected_gpu
            proofs.add(answer['proof_sha256'])
            record = {'name': row['name'], 'backend': row['backend'], 'sanitizer': row['sanitizer'], 'workload_sha256': item['workload_sha256'],
                      'proof_sha256': answer['proof_sha256'], 'constant_identities': constants,
                      'affine_identities': len(extended), 'fallback_assignments': assignments,
                      'roots': roots, 'reduced_basis_verified': True, 'gpu_used': expected_gpu}
            records.append(record)
            journal.write(json.dumps(record, separators=(',', ':')) + '\n')
            journal.flush()
            print('ORIGINAL_ANF_AUDIT_PASS', *key, flush=True)
    assert seen == {(name, arm) for name in fixtures for arm in expected_arms}
    for name, expected in sources.items():
        assert sha(Path(name)) == expected
    result = {'schema': 'normalized-wide-original-anf-audit/1', 'status': 'PASS',
              'scope': 'Every original-equation rejection identity and all uncovered assignments; reduced bases checked by complete-root evaluation and Boolean quotient dimension. Native code is not loaded.',
              'input_sha256': sha(args.input), 'source_sha256': sources,
              'fixture_sha256': sha(fixture_path), 'records': records, 'unique_proofs': len(proofs),
              'timing_eligible': False, 'candidate_id': None, 'online_speedup': None}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('INDEPENDENT_AUDIT_PASS', len(records), 'query records;', len(proofs), 'unique proofs', flush=True)


if __name__ == '__main__':
    main()
