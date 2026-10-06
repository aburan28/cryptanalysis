"""Offline original-ANF root, basis and symmetry accounting audit; no native code."""
import argparse
import base64
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'round44'))
from tagged_reference import certify_roots, TAG
from transform_accounting import MODES, reconcile_transform
from identity_accounting import QUERY_VARIANTS, IDENTITY_MODES, reconcile_identity, per_record
sys.path.insert(0, str(HERE.parent / 'round27'))
from reference import verify_basis


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=48)
def independent_aliases(x, y, equations, items, raw, byteorder, partials):
    """Use a polynomial dictionary and proof tuples, not checker tables."""
    assert x % 2 == 0
    half, mask = x // 2, (1 << (x // 2)) - 1
    branches, limbs = 1 << x, (equations + 63) // 64
    def swap(branch):
        return ((branch & mask) << half) | (branch >> half)
    polynomial = {}
    for monomial, coefficient in items:
        polynomial[monomial] = polynomial.get(monomial, 0) ^ coefficient
    for monomial, coefficient in polynomial.items():
        exchanged = (monomial & ~(branches - 1)) | swap(monomial & (branches - 1))
        assert coefficient == polynomial.get(exchanged, 0), 'original equations are asymmetric'
    words = tuple(int.from_bytes(raw[i:i+8], byteorder) for i in range(0, len(raw), 8))
    records = {}
    for branch in range(branches):
        payload = words[branch * limbs:(branch + 1) * limbs]
        if any(payload):
            records[branch] = ('constant', payload)
    prefix, entry = branches * limbs, 1 + (y + 1) * limbs
    for offset in range(prefix, len(words), entry):
        tagged = bool(words[offset] & TAG)
        records[words[offset] & ~TAG] = ('partial' if tagged else 'multiplier', words[offset+1:offset+entry])
    partial = {branch: (rank, inconsistent, assignments) for branch, rank, inconsistent, assignments in partials}
    result = dict.fromkeys(('inferred_aliases', 'constant_aliases', 'multiplier_aliases', 'partial_aliases',
                          'enumerated_aliases', 'derived_partial_rank', 'derived_partial_assignments',
                          'derived_partial_inconsistent', 'avoided_assignments', 'proof_mismatches',
                          'proof_pairs', 'proof_words'), 0)
    for a in range(branches):
        b = swap(a)
        if a >= b:
            continue
        result['proof_pairs'] += 1
        left, right = records.get(a, ('enumerated', ())), records.get(b, ('enumerated', ()))
        if left[0] == right[0]:
            for u, v in zip(left[1], right[1]):
                result['proof_words'] += 1
                if u != v:
                    break
        if left != right:
            result['proof_mismatches'] += 1
            continue
        result['inferred_aliases'] += 1
        result[left[0] + '_aliases'] += 1
        if left[0] == 'partial':
            assert partial[a] == partial[b]
            rank, inconsistent, assignments = partial[b]
            result['derived_partial_rank'] += rank
            result['derived_partial_inconsistent'] += int(inconsistent)
            result['derived_partial_assignments'] += assignments
            result['avoided_assignments'] += assignments
        elif left[0] == 'enumerated':
            result['avoided_assignments'] += 1 << y
    features = 1 + y + y * (y - 1) // 2
    result['representatives'] = result['inferred_aliases']
    result['avoided_constant_parities'] = features * limbs * result['inferred_aliases']
    result['avoided_multiplier_parities'] = (y + 1) * features * limbs * result['multiplier_aliases']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = json.loads(gzip.decompress(args.input.read_bytes()))
    assert report['schema'] == 'independent-grouped-identity-checker-validation/1' and report['status'] == 'PASS'
    assert report['sources'][str(HERE / 'validate_native.py')] == sha(HERE / 'validate_native.py')
    for section in ('sources', 'binaries', 'references'):
        for name, digest in report[section].items():
            assert sha(Path(name)) == digest, name
    fixture_path = HERE.parent / 'round40/fixtures/inputs.json.gz'
    fixtures = {i['name']: i for i in json.loads(gzip.decompress(fixture_path.read_bytes()))}
    assert report['references'][str(fixture_path)] == sha(fixture_path)
    modes = [('cpu', False), ('cpu', True)]
    if report['metal']['status'] == 'AVAILABLE':
        modes.append(('metal', False))
    expected = {(name, backend, sanitizer, partial, symmetry, transform, identity) for name in fixtures
                for backend, sanitizer in modes for partial in (False, True) for symmetry in (False, True) for transform, identity in QUERY_VARIANTS}
    seen, records, proofs = set(), [], set()
    with args.output.with_suffix(args.output.suffix + '.jsonl').open('x') as journal:
        for row in report['queries']:
            key = row['name'], row['backend'], row['sanitizer'], row['partial_enabled'], row['symmetry_enabled'], row['transform_mode'], row['identity_mode']
            assert key in expected and key not in seen
            seen.add(key)
            item, answer = fixtures[row['name']], row['result']
            assert row['workload_sha256'] == item['workload_sha256']
            assert answer['status'] == 'solved' and answer['verified']
            raw = base64.b64decode(report['proofs'][answer['proof_sha256']], validate=True)
            assert hashlib.sha256(raw).hexdigest() == answer['proof_sha256']
            x, y, e = 2 * item['ell'], item['ell'], item['n']
            items = tuple(tuple(v) for v in item['reference_anf'])
            roots, constants, extended, partials, assignments = certify_roots(
                x, y, e, items, raw, answer['proof_byteorder'])
            roots = list(roots)
            assert roots == answer['basis_certificate']['solutions']
            assert verify_basis(item['nvars'], item['reference_anf'], roots, answer['basis_terms'], len(roots))
            assert answer['assignment'] in roots
            expected_aliases = independent_aliases(x, y, e, items, raw, answer['proof_byteorder'], partials)
            cert = answer['basis_certificate']
            reconcile_transform(cert, x, y, e, audit=False)
            reconcile_identity(cert, x, y, e, audit=False)
            assert cert['identity_check_stats']['mode'] == IDENTITY_MODES[row['identity_mode']]
            assert cert['transform_check_stats']['requested_mode'] == MODES[row['transform_mode']]
            stats, partial, symmetry = cert['stats'], cert['partial_stats'], cert['symmetry_check_stats']
            assert symmetry['requested'] == symmetry['enabled'] == int(row['symmetry_enabled'])
            aliases = dict(expected_aliases) if row['symmetry_enabled'] else dict.fromkeys(expected_aliases, 0)
            aliases['avoided_multiplier_parities'] = aliases['multiplier_aliases'] * per_record(y, e, row['identity_mode'])['parities']
            for name, value in aliases.items():
                assert symmetry[name] == value, (key, name, symmetry[name], value)
            assert stats['contradictions'] == constants + len(extended) + sum(v[2] for v in partials)
            assert stats['extended_contradictions'] == len(extended)
            assert stats['assignments'] + aliases['avoided_assignments'] == assignments
            assert partial['records'] + aliases['partial_aliases'] == len(partials)
            assert partial['rank_sum'] + aliases['derived_partial_rank'] == sum(v[1] for v in partials)
            assert partial['assignments'] + aliases['derived_partial_assignments'] == sum(v[3] for v in partials)
            assert partial['inconsistent'] + aliases['derived_partial_inconsistent'] == sum(v[2] for v in partials)
            words_per_record = (y + 1) * ((e + 63) // 64)
            assert stats['multiplier_words'] == (len(extended) - aliases['multiplier_aliases']) * words_per_record
            assert stats['roots'] == stats['standard'] == len(roots)
            record = {'name': row['name'], 'backend': row['backend'], 'sanitizer': row['sanitizer'],
                      'partial_enabled': row['partial_enabled'], 'symmetry_enabled': row['symmetry_enabled'],
                      'transform_mode': row['transform_mode'], 'identity_mode': row['identity_mode'],
                      'identity_counters': dict(cert['identity_check_stats']),
                      'transform_counters': {k:v for k,v in cert['transform_check_stats'].items() if type(v) is int},
                      'proof_sha256': answer['proof_sha256'], 'roots': roots, 'reduced_basis_verified': True,
                      'full_assignments': assignments, 'physical_assignments': stats['assignments'],
                      'independently_derived_aliases': aliases}
            records.append(record)
            proofs.add(answer['proof_sha256'])
            journal.write(json.dumps(record, separators=(',', ':')) + '\n')
            journal.flush()
            print('ORIGINAL_ANF_IDENTITY_AUDIT_PASS', *key, flush=True)
    assert seen == expected
    for section in ('sources', 'binaries', 'references'):
        for name, digest in report[section].items():
            assert sha(Path(name)) == digest, name
    result = {'schema': 'independent-grouped-identity-original-anf-audit/1', 'status': 'PASS',
              'input_sha256': sha(args.input), 'auditor_sha256': sha(Path(__file__)),
              'fixture_sha256': sha(fixture_path), 'records': records, 'unique_proofs': len(proofs),
              'scope': 'Original ANF symmetry; every witness and full root count; reduced basis; independent proof-pair, avoided-work and recursive transform plus grouped identity accounting. No native library is loaded. Audit cache is outside query timing.',
              'timing_eligible': False, 'candidate_id': None, 'online_speedup': None}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('INDEPENDENT_IDENTITY_AUDIT_PASS', len(records), 'records;', len(proofs), 'proofs', flush=True)


if __name__ == '__main__':
    main()
