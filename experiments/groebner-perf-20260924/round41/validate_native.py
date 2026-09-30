"""Portable CPU, UBSan and explicitly requested physical Metal correctness."""
import argparse
import base64
from contextlib import ExitStack
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'round38'))
import compact as baseline
sys.path.insert(0, str(HERE.parent / 'round37'))
import test_fixed_width as independent
import wide_metal as candidate
from controls import cases
from wide_query import WideMetalQuery
from public_replay import Point


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integer(value):
    return {k: v for k, v in value.items() if type(v) in (int, bool)}


def mathematical(value):
    fields = ('status', 'verified', 'assignment', 'basis_terms', 'basis_sha256', 'curve_witness', 'public_target')
    return {key: value[key] for key in fields}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--metal', action='store_true', help='Record an explicit device request; unavailable devices do not count as GPU coverage')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    receipt_path = HERE / 'build/receipt.json'
    receipt = json.loads(receipt_path.read_text())
    def source_check():
        for name, expected in receipt['sources'].items():
            assert sha(HERE.parent / name) == expected
        for name, expected in receipt['binaries'].items():
            assert sha(HERE / 'build' / name) == expected
    source_check()
    metal = {'requested': args.metal, 'status': 'NOT_REQUESTED', 'device': None}
    if args.metal:
        try:
            with candidate.Producer(2, 10, 32, backend='metal') as probe:
                metal.update(status='AVAILABLE', device=probe.device)
        except ValueError as error:
            # Build, shader and allocation failures must fail validation.
            if str(error) != 'requested Metal device unavailable':
                raise
            metal.update(status='UNAVAILABLE', detail=str(error))
    modes = [('cpu', 'cpu', False), ('ubsan', 'cpu', True)]
    if metal['status'] == 'AVAILABLE':
        modes.append(('metal', 'metal', False))
    fixture_path = HERE.parent / 'round40/fixtures/inputs.json.gz'
    report = {'schema': 'wide-metal-native-validation/1', 'status': 'RUNNING',
              'scope': 'Exact systems and frozen planted complete PDP queries. No timing, natural-yield, full IC or rho claim.',
              'host': {'platform': platform.platform(), 'architecture': platform.machine(), 'python': sys.version},
              'metal': metal, 'validator_sha256': sha(Path(__file__)),
              'build_receipt_sha256': sha(receipt_path), 'fixture_sha256': sha(fixture_path),
              'controls': [], 'budgets': [], 'queries': [], 'proofs': {},
              'timing_eligible': False, 'candidate_id': None, 'online_speedup': None}
    controls = list(cases())
    assert len(controls) == 4330
    with ExitStack() as stack:
        contexts = {}
        for index, (name, x, y, e, items) in enumerate(controls):
            shape = x, y, e
            if shape not in contexts:
                contexts[shape] = {
                    mode: (stack.enter_context(candidate.Producer(x, y, e, backend=backend, sanitizer=sanitizer)),
                           stack.enter_context(candidate.Checker(x, y, e, sanitizer=sanitizer)))
                    for mode, backend, sanitizer in modes}
            truth = independent.truth(x + y, items)
            packed = candidate.Packed(x + y, e, items)
            cpu_proof = None
            for mode, backend, _ in modes:
                producer, checker = contexts[shape][mode]
                expected_gpu = backend == 'metal' and e <= 32
                if len(truth) > 256:
                    try:
                        producer.produce(packed, checker=checker)
                    except candidate.Inconclusive as error:
                        assert 'roots exceed 256' in str(error)
                        assert bool(error.metrics['gpu_used']) == expected_gpu
                        report['controls'].append({'name': name, 'shape': shape, 'mode': mode,
                            'status': 'expected-inconclusive', 'direct_truth_roots': len(truth),
                            'detail': str(error), 'metrics': integer(error.metrics)})
                    else:
                        raise AssertionError('root-limit control returned a partial answer')
                    continue
                answer = producer.produce(packed, checker=checker)
                assert answer['roots'] == truth and answer['certificate']['verified'], (name, mode)
                assert independent.verify_basis(x + y, items, truth, answer['basis'], len(truth)), (name, mode)
                assert independent.check_identities(x, y, e, items, answer['proof_bytes']) == answer['certificate']['stats']['contradictions']
                assert bool(answer['stats']['gpu_used']) == expected_gpu
                assert bool(answer['stats']['gpu_shape_fallback']) == (backend == 'metal' and e > 32)
                if mode == 'cpu':
                    cpu_proof = answer['proof_bytes']
                elif mode == 'ubsan':
                    assert answer['proof_bytes'] == cpu_proof
                if name == 'rank32-high-word-pivot':
                    assert answer['roots'] == [0, 1, 2, 3]
                if name == 'high-equation-constant-witness':
                    assert answer['roots'] == []
                    assert any(answer['proof_bytes'])
                report['controls'].append({'name': name, 'shape': shape, 'mode': mode, 'status': 'verified',
                    'proof_sha256': answer['proof_sha256'], 'device': producer.device,
                    'metrics': integer(answer['stats']), 'symmetry': integer(answer['symmetry_stats'])})
            if (index + 1) % 256 == 0:
                print('CONTROL_SYSTEMS_PASS', index + 1, flush=True)
    for mode in ('budget_test', 'multiplier_budget_test', 'copy_budget_test', 'reconstruction_budget_test'):
        items = [(4, 1), (8, 2), (12, 4), (0, 4)]
        with candidate.Producer(2, 2, 3, **{mode: True}) as producer, candidate.Checker(2, 2, 3) as checker:
            try:
                answer = producer.produce(candidate.Packed(4, 3, items), checker=checker)
                assert answer['roots'] == [] and answer['certificate']['verified']
                report['budgets'].append({'mode': mode, 'status': 'verified', 'metrics': integer(answer['stats']),
                                         'multiplier': integer(answer['multiplier_stats']), 'symmetry': integer(answer['symmetry_stats'])})
            except candidate.Inconclusive as error:
                report['budgets'].append({'mode': mode, 'status': 'inconclusive', 'detail': str(error),
                                         'metrics': integer(error.metrics)})
    inputs = json.loads(gzip.decompress(fixture_path.read_bytes()))
    assert len(inputs) == 18
    spec = importlib.util.spec_from_file_location('wide_control_query', HERE.parent / 'round38/compact_query.py')
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    query_modes = [('baseline-cpu', prior.CompactQuery, 'cpu', False)]
    query_modes += [('wide-' + label, WideMetalQuery, backend, sanitizer) for label, backend, sanitizer in modes]
    expectations, cpu_proofs = {}, {}
    for label, cls, backend, sanitizer in query_modes:
        with ExitStack() as stack:
            contexts = {}
            for item in inputs:
                shape = tuple(item[k] for k in ('n', 'mod', 'b', 'm', 'ell'))
                if shape not in contexts:
                    contexts[shape] = stack.enter_context(cls(*shape, backend=backend, sanitizer=sanitizer))
                answer = contexts[shape].solve(Point(**item['target']))
                assert answer['status'] == 'solved' and answer['verified'], (item['name'], label)
                original = 0
                for monomial, coefficient in item['reference_anf']:
                    if monomial & answer['assignment'] == monomial:
                        original ^= coefficient
                assert original == 0
                proof = answer.pop('proof_bytes')
                assert hashlib.sha256(proof).hexdigest() == answer['proof_sha256']
                report['proofs'].setdefault(answer['proof_sha256'], base64.b64encode(proof).decode())
                if label == 'baseline-cpu':
                    expectations[item['name']] = mathematical(answer)
                    cpu_proofs[item['name']] = proof
                else:
                    assert mathematical(answer) == expectations[item['name']]
                    if backend == 'cpu':
                        assert proof == cpu_proofs[item['name']]
                expected_gpu = backend == 'metal' and item['n'] <= 32
                assert bool(answer['metrics']['gpu_used']) == expected_gpu
                report['queries'].append({'name': item['name'], 'workload_sha256': item['workload_sha256'],
                                          'arm': label, 'result': answer})
                print('QUERY_PASS', item['name'], label, 'gpu', expected_gpu, flush=True)
    source_check()
    report['status'] = 'PASS'
    args.output.write_bytes(gzip.compress(json.dumps(report, separators=(',', ':')).encode(), mtime=0))
    print('PASS', len(report['controls']), 'native controls;', len(report['queries']), 'queries;', metal, flush=True)


if __name__ == '__main__':
    main()
