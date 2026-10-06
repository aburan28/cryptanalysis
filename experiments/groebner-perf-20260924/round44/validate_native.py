"""Frozen polynomial corpus and complete-query correctness, with ablation."""
import argparse
import base64
from contextlib import ExitStack
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import normalized as candidate
from normalized_query import NormalizedQuery
from tagged_reference import certify_roots

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'round37'))
import test_fixed_width as independent
from public_replay import Point

spec = importlib.util.spec_from_file_location('accepted_normalized42_validation', HERE.parent / 'round42/normalized.py')
accepted = importlib.util.module_from_spec(spec)
spec.loader.exec_module(accepted)


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.name.endswith('.gz') else path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integer(record):
    return {k: v for k, v in record.items() if type(v) in (int, bool)}


def accounting(answer, partials, constants, extended, assignments):
    check = answer['certificate']
    assert check['verified']
    assert check['stats']['assignments'] == assignments
    assert check['stats']['contradictions'] == constants + len(extended) + sum(v[2] for v in partials)
    assert check['stats']['extended_contradictions'] == len(extended)
    assert check['partial_stats']['records'] == len(partials)
    assert check['partial_stats']['rank_sum'] == sum(v[1] for v in partials)
    assert check['partial_stats']['assignments'] == sum(v[3] for v in partials)
    part, sym, mul = (answer[k] for k in ('partial_stats', 'symmetry_stats', 'multiplier_stats'))
    assert part['handled_branches'] + part['copied_records'] == len(partials)
    assert mul['certified_branches'] + sym['affine_copies'] - part['copied_records'] == len(extended)
    assert mul['attempts'] == mul['certified_branches'] + mul['failed_branches']
    assert mul['proof_words'] * 8 == len(answer['proof_bytes'])
    norm, proj, defer = (answer[k] for k in ('normalization_stats', 'projection_stats', 'deferred_stats'))
    assert norm['attempts'] == norm['prepared'] + norm['mismatches'] + norm['nonunits'] + norm['budget_skips']
    assert norm['transpose_parities'] == 0 and norm['work'] <= proj['work']
    assert proj['work'] + mul['rows'] + mul['row_xors'] + defer['reconstruction_pivots'] <= 67108864


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--metal', action='store_true')
    args = parser.parse_args()
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
    receipt_path = HERE / 'build/receipt.json'
    receipt = read(receipt_path)

    def check_sources():
        for path, digest in receipt['sources'].items():
            assert sha(HERE.parent / path) == digest, path
        for kind in ('binaries', 'generated'):
            for path, digest in receipt[kind].items():
                assert sha(HERE / 'build' / path) == digest, path

    check_sources()
    corpus_path = HERE.parent / 'round42/fixtures/controls.json.gz'
    manifest = read(HERE.parent / 'round42/fixtures/manifest.json')
    assert sha(corpus_path) == manifest['sha256']
    cases = read(corpus_path)
    assert len(cases) == manifest['controls'] == 6001
    truths = {name: independent.truth(x + y, terms) for name, x, y, e, terms, mod, kind in cases}
    modes = [('cpu', False), ('cpu', True)]
    metal = {'requested': args.metal, 'status': 'NOT_REQUESTED', 'device': None}
    if args.metal:
        try:
            with candidate.Producer(2, 9, 31, backend='metal') as probe:
                metal.update(status='AVAILABLE', device=probe.device)
        except ValueError as error:
            if str(error) != 'requested Metal device unavailable':
                raise
            metal.update(status='UNAVAILABLE', detail=str(error))
        else:
            modes.append(('metal', False))
    report = {'schema': 'partial-affine-query-validation/1', 'status': 'RUNNING',
              'validator_sha256': sha(Path(__file__)), 'build_receipt_sha256': sha(receipt_path),
              'corpus_sha256': sha(corpus_path), 'metal': metal,
              'controls': [], 'queries': [], 'proofs': {}, 'devices': [],
              'timing_eligible': False, 'candidate_id': None, 'online_speedup': None}
    journal_path = output.with_suffix(output.suffix + '.jsonl')
    with journal_path.open('x') as journal:
        def retain(kind, row):
            report[kind].append(row)
            journal.write(json.dumps({'kind': kind, **row}, separators=(',', ':')) + '\n')
            journal.flush()

        for backend, sanitizer in modes:
            with ExitStack() as stack:
                contexts = {}
                for index, (name, x, y, e, terms, modulus, kind) in enumerate(cases):
                    shape = x, y, e, modulus
                    if shape not in contexts:
                        p = stack.enter_context(candidate.Producer(x, y, e, backend=backend, sanitizer=sanitizer))
                        old = stack.enter_context(accepted.Producer(x, y, e, backend=backend, sanitizer=sanitizer))
                        if modulus is not None:
                            p.configure_normalization(modulus)
                            old.configure_normalization(modulus)
                        c = stack.enter_context(candidate.Checker(x, y, e, sanitizer=sanitizer))
                        contexts[shape] = p, c, old
                        report['devices'].append({'backend': backend, 'sanitizer': sanitizer, 'shape': shape, 'device': p.device})
                    p, c, old = contexts[shape]
                    packed = candidate.Packed(x + y, e, terms)
                    original = None
                    for enabled in (False, True):
                        p.configure_partial(enabled)
                        row = {'case': name, 'backend': backend, 'sanitizer': sanitizer, 'partial_enabled': enabled,
                               'kind': kind, 'shape': [x, y, e], 'truth_roots': len(truths[name])}
                        try:
                            answer = p.produce(packed, checker=c)
                        except candidate.Inconclusive as error:
                            assert len(truths[name]) > 256 and 'complete roots exceed 256' in str(error), (name, str(error))
                            row.update(status='expected-inconclusive', detail=str(error),
                                       partial=integer(error.partial_stats), metrics=integer(error.metrics))
                        else:
                            if original is None:
                                original = old.produce(packed)
                            assert answer['roots'] == truths[name] == original['roots'], (name, backend, enabled)
                            assert answer['basis'] == original['basis']
                            if not enabled:
                                assert answer['proof_bytes'] == original['proof_bytes']
                                assert all(value == 0 for value in integer(answer['partial_stats']).values())
                            assert independent.verify_basis(x + y, terms, truths[name], answer['basis'], len(truths[name]))
                            roots, constants, extended, partials, assignments = certify_roots(
                                x, y, e, tuple(tuple(v) for v in terms), answer['proof_bytes'], sys.byteorder)
                            assert list(roots) == truths[name]
                            accounting(answer, partials, constants, extended, assignments)
                            assert answer['symmetry_stats']['representatives'] + answer['symmetry_stats']['aliases'] == 1 << x
                            if kind == 'zero-scalar':
                                assert answer['normalization_stats']['zero_scalars'] > 0
                            if kind == 'nonunit':
                                assert answer['normalization_stats']['nonunits'] > 0
                            expected_gpu = backend == 'metal' and e <= 32
                            assert bool(answer['stats']['gpu_used']) == expected_gpu
                            row.update(status='verified', proof_sha256=answer['proof_sha256'], gpu_used=expected_gpu,
                                       checker=integer(answer['certificate']['stats']),
                                       checker_partial=integer(answer['certificate']['partial_stats']),
                                       metrics=integer(answer['stats']))
                            for key in ('normalization', 'projection', 'multiplier', 'deferred', 'symmetry', 'partial'):
                                row[key] = integer(answer[key + '_stats'])
                        retain('controls', row)
                    if (index + 1) % 1000 == 0:
                        print('CONTROLS_PASS', backend, sanitizer, index + 1, 'enabled+disabled', flush=True)
        inputs_path = HERE.parent / 'round40/fixtures/inputs.json.gz'
        inputs = read(inputs_path)
        for backend, sanitizer in modes:
            with ExitStack() as stack:
                workspaces = {}
                for item in inputs:
                    shape = tuple(item[k] for k in ('n', 'mod', 'b', 'm', 'ell'))
                    if shape not in workspaces:
                        workspaces[shape] = stack.enter_context(NormalizedQuery(*shape, backend=backend, sanitizer=sanitizer))
                    workspace = workspaces[shape]
                    ablation = None
                    for enabled in (False, True):
                        workspace.basis.producer.configure_partial(enabled)
                        answer = workspace.solve(Point(**item['target']))
                        assert answer['status'] == 'solved' and answer['verified']
                        proof = answer.pop('proof_bytes')
                        assert hashlib.sha256(proof).hexdigest() == answer['proof_sha256']
                        expected_gpu = backend == 'metal' and item['n'] <= 32
                        assert bool(answer['metrics']['gpu_used']) == expected_gpu
                        if ablation is None:
                            ablation = answer
                        else:
                            for key in ('basis_terms', 'assignment'):
                                assert answer[key] == ablation[key]
                            assert answer['basis_certificate']['solutions'] == ablation['basis_certificate']['solutions']
                        report['proofs'].setdefault(answer['proof_sha256'], base64.b64encode(proof).decode())
                        retain('queries', {'name': item['name'], 'workload_sha256': item['workload_sha256'],
                                           'backend': backend, 'sanitizer': sanitizer, 'partial_enabled': enabled, 'result': answer})
                        print('QUERY_PASS', item['name'], backend, sanitizer, enabled, 'GPU', expected_gpu, flush=True)
    assert len(report['queries']) == 36 * len(modes) and len(report['controls']) == 12002 * len(modes)
    check_sources()
    report.update(status='PASS', fixture_sha256=sha(inputs_path))
    output.write_bytes(gzip.compress(json.dumps(report, separators=(',', ':')).encode(), mtime=0))
    print('PARTIAL_VALIDATION_PASS', len(report['controls']), 'systems;', len(report['queries']), 'queries', flush=True)


if __name__ == '__main__':
    main()
