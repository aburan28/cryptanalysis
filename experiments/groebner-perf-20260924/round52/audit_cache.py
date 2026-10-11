"""Replay each distinct original-ANF query proof with every cache load audited."""
import argparse
import base64
from contextlib import ExitStack
import gzip
import hashlib
import json
from pathlib import Path

from adapter import HERE, Checker, load, producer
from bindings import bindings
from locality_accounting import locality_accounting, compare_certificates


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    frozen = bindings()
    source = read(args.input)
    assert source['status'] == 'PASS' and source['partial_coefficients'] == 'local'
    assert source['build_receipt_sha256'] == sha(HERE/'build/receipt.json')
    fixture = HERE.parent/'round40/fixtures/inputs.json.gz'
    assert sha(fixture) == source['fixture_sha256']
    items = {row['name']: row for row in read(fixture)}
    prior = load('cache52_audit_checker48', HERE.parent/'round48/independent_checker.py')
    records, seen = [], set()
    with ExitStack() as stack:
        contexts = {}
        for row in source['queries']:
            item, answer = items[row['name']], row['result']
            key = row['name'], answer['proof_sha256']
            if key in seen:
                continue
            seen.add(key)
            shape = 2*item['ell'], item['ell'], item['n']
            if shape not in contexts:
                c = stack.enter_context(Checker(*shape, locality_audit_test=True, symmetry=False, identity='factored_local'))
                old = stack.enter_context(prior.Checker(*shape, symmetry=False, identity='factored_local'))
                contexts[shape] = c, old
            c, old = contexts[shape]
            packed = producer.Packed(item['nvars'], item['n'], item['reference_anf'])
            proof = base64.b64decode(source['proofs'][answer['proof_sha256']], validate=True)
            assert hashlib.sha256(proof).hexdigest() == answer['proof_sha256']
            for transform in ('full', 'tile16'):
                c.configure_transform(transform); old.configure_transform(transform)
                arguments = packed, answer['basis_certificate']['solutions'], answer['basis_terms'], proof
                checked, baseline = c.certify(*arguments), old.certify(*arguments)
                assert checked['verified'] and baseline['verified']
                compare_certificates(checked, baseline)
                locality_accounting(checked, item['ell'], item['n'], 'local', audit=True)
                records.append({'name': row['name'], 'proof_sha256': key[1], 'transform': transform,
                                'locality': checked['partial_locality_stats'], 'partial': checked['partial_stats'],
                                'root_count': checked['root_count'], 'status': 'PASS'})
                print('CACHE_AUDIT_PASS', row['name'], transform, checked['partial_locality_stats']['audit_words'], flush=True)
    for name, expected in frozen.items():
        assert sha(Path(name)) == expected, name
    report = {'status': 'PASS', 'input_sha256': sha(args.input), 'records': records,
              'unique_query_proofs': len(seen), 'audited_words': sum(r['locality']['audit_words'] for r in records),
              'executed_bindings': frozen, 'timing_eligible': False}
    args.output.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
