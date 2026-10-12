"""Synthetic report fixtures test rejection rules; these are not measurements."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from audit import PREFIX, REQUIRED_SOURCES, audit
from benchmark import ARMS, digest, sources
from build import generated_sources


def synthetic_report():
    # y=1 at x=0 lies on y^2+xy=x^3+1 over GF(8). The ANF v has root 0.
    report = {'status': 'RECORDED', 'candidate_id': None, 'IC_online_ms': None,
              'rho_online_ms': None, 'arms': ARMS, 'repetitions': 2,
              'source_snapshot': {}, 'source_sha256': {},
              'build_receipts': {'17': {'source_sha256': {}, 'binaries': {'mock': 'replay'}},
                                 '14': {'binaries': {'mock': 'descent'}},
                                 '15': {'binaries': {'mock': 'checker'}},
                                 '18': {'source_sha256': {}, 'binaries': {'mock': 'truth'}},
                                 '19': {'source_sha256': {}, 'binaries': {'mock': 'gpu'}}},
              'admission': {'admitted': True, 'max_load_per_cpu': 1, 'timed_attempts': 144},
              'host': {'logical_cpus': 1, 'load_end': [0, 0, 0]},
              'timing_qualification': {'eligible': True}, 'inputs': [], 'rows': []}
    report['source_snapshot'] = sources()
    reference = (Path(__file__).resolve().parent.parent / 'round15/reference/boolean_certificate.cpp').read_text()
    report['source_snapshot'][PREFIX + 'round15/reference/boolean_certificate.cpp'] = reference
    helpers = reference.split('extern "C" int boolean_certificate(', 1)[0]
    checks = '        out->roots = alive;' + reference.split('        out->roots = alive;', 1)[1].split(
        '    } catch (const std::invalid_argument&)', 1)[0]
    report['build_receipts']['18']['generated_sha256'] = {
        name: hashlib.sha256(source.encode()).hexdigest() for name, source in (
            ('certificate_helpers.inc', helpers), ('basis_checks.inc', checks))}
    hashes = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in report['source_snapshot'].items()}
    report['source_sha256'] = hashes
    report['build_receipts']['17']['source_sha256'] = {name: hashes[name] for name in (
        PREFIX + 'round17/replay.c', 'experiments/pdp-degree-heuristics/pdpkernel.c')}
    report['build_receipts']['14']['source_sha256'] = hashes[PREFIX + 'round14/contraction.cpp']
    report['build_receipts']['15']['ordered_source_sha256'] = hashes[PREFIX + 'round15/ordered_certificate.cpp']
    report['build_receipts']['15']['reference_sha256'] = {name: hashes[PREFIX + 'round15/reference/' + name]
        for name in ('boolean_certificate.cpp', 'packed_certificate.cpp')}
    report['build_receipts']['18']['source_sha256'] = {name: hashes[name] for name in (
        PREFIX + 'round18/packed_verifier.cpp', PREFIX + 'round15/reference/boolean_certificate.cpp')}
    report['build_receipts']['19']['source_sha256'] = {name: hashes[name] for name in (
        PREFIX + 'round19/packed_gpu.mm', PREFIX + 'round19/tiled_truth.metal', PREFIX + 'round19/build.py',
        PREFIX + 'round18/packed_verifier.cpp', PREFIX + 'round15/reference/boolean_certificate.cpp')}
    report['build_receipts']['19']['generated_sha256'] = {name: hashlib.sha256(text.encode()).hexdigest()
        for name, text in generated_sources(report['source_snapshot']).items()}
    for i in range(16):
        frozen = {'name': f'synthetic-audit-fixture-{i}', 'n': 3, 'mod': 11, 'b': 1,
                  'm': 1, 'ell': 1, 'nvars': 1, 'target': {'x': 0, 'y': 1, 'inf': False},
                  'reference_anf': [[1, 1]]}
        workload = digest(frozen)
        report['inputs'].append({**frozen, 'workload_sha256': workload, 'fixture_ns': 1})
        for repetition in range(3):
            row = {'name': frozen['name'], 'workload_sha256': workload, 'repetition': repetition,
                   'warmup': repetition == 0, 'order': ARMS, 'load': [0, 0, 0]}
            for arm in ARMS:
                # Deliberately artificial integer timings: only audit contracts
                # are exercised, and the temporary report is deleted afterwards.
                row[arm] = {'wall_ns': 20, 'cpu_ns': 20,
                            'phases_ns': {'public_query': 18, 'reference_equations': 2},
                            'outside_timing_witness_audit': {'verified': True, 'wall_ns': 1},
                            'result': {'status': 'solved', 'verified': True, 'groebner_verified': True,
                                       'public_target': frozen['target'], 'assignment': 0,
                                       'basis_sha256': 'mock', 'basis_certificate': {'verified': True, 'backend':
                                           'independent-packed-bitslice-zeta' if arm == 'cpu' else 'independent-packed-metal-tiled-zeta'},
                                       'complete_query_ns': 16, 'phases_ns': {'basis_and_certificate': 16},
                                       'curve_witness': {'verified': True, 'code': 0,
                                                         'points': [frozen['target']], 'signs': 0, 'patterns': 1},
                                       'replay_backend': 'native-public-point',
                                       'replay_binary_sha256': 'replay',
                                       'descent_binary_sha256': 'descent', 'verifier_binary_sha256': 'truth' if arm == 'cpu' else 'gpu',
                                       'query_arm': arm, 'equation_backend': 'independent-native-direct-packed',
                                       'equation_binary_sha256': 'truth' if arm == 'cpu' else 'gpu'}}
                answer = row[arm]['result']
                answer['gpu_device'] = None if arm == 'cpu' else 'synthetic audit device'
                if arm != 'cpu':
                    answer['basis_certificate'].update(scratch_bytes=75,
                        evaluation_counts={'zeta_words': 0, 'high_gather_words': 3},
                        gpu_timing={'prepare': 0, 'encode': 0, 'execute': 0, 'extract': 0,
                            'basis_check': 0, 'total': 0, 'spin': 0, 'device': None,
                            'calls': 1, 'dispatches': 2, 'threads': 256, 'blocking_fallback': 1,
                            'polls': 0, 'shared_buffer_bytes': 72, 'zeta_words': 0, 'high_gather_words': 3})
            report['rows'].append(row)
    return report


class AuditTests(unittest.TestCase):
    def run_audit(self, report):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic-not-a-measurement.json.gz'
            path.write_bytes(gzip.compress(json.dumps(report).encode()))
            return audit(path)

    def test_valid_contract_and_failed_attempts(self):
        report = synthetic_report()
        answer = self.run_audit(report)
        self.assertEqual(len(answer['controls']), 16)
        self.assertTrue(answer['timing_admission_eligible'])
        report['rows'][1]['gpu-poll']['result'] = {'status': 'work-limit', 'verified': False}
        answer = self.run_audit(report)
        failed = answer['controls'][0]
        self.assertFalse(failed['all_attempts_verified'])
        self.assertNotIn('wall_baseline_over_arm', failed)
        self.assertEqual(answer['statuses']['gpu-poll:work-limit'], 1)

    def test_point_phase_identity_and_coverage_corruption_rejected(self):
        original = synthetic_report()
        mutations = [
            lambda r: r['rows'][0]['cpu']['result']['curve_witness']['points'][0].update(y=0),
            lambda r: r['rows'][0]['cpu'].update(wall_ns=21),
            lambda r: r['rows'][0]['cpu']['result'].update(assignment=1),
            lambda r: r['rows'][0]['gpu-poll']['result'].update(replay_binary_sha256='wrong'),
            lambda r: r['rows'][0]['gpu-poll']['result'].update(replay_backend='python-public-point'),
            lambda r: r['rows'][0]['gpu-poll']['result'].update(equation_binary_sha256='wrong'),
            lambda r: r['rows'][0]['gpu-poll']['result']['basis_certificate'].update(backend='wrong'),
            lambda r: r['rows'][0]['gpu-poll']['result'].update(verifier_binary_sha256='wrong'),
            lambda r: r['rows'].pop(),
            lambda r: r['build_receipts']['18']['generated_sha256'].update({'basis_checks.inc': 'wrong'}),
            lambda r: r['inputs'][0].update(b=2),
            lambda r: r['source_snapshot'].pop(PREFIX + 'round17/replay.c'),
            lambda r: r['build_receipts']['17']['source_sha256'].update({PREFIX + 'round17/replay.c': 'wrong'}),
            lambda r: r['rows'][0]['gpu-poll']['result']['basis_certificate']['gpu_timing'].update(dispatches=0),
            lambda r: r['rows'][0]['gpu-poll']['result']['basis_certificate']['gpu_timing'].update(total=float('nan')),
            lambda r: r['build_receipts']['19']['generated_sha256'].update({'packed_gpu_core.inc': 'wrong'}),
        ]
        for mutate in mutations:
            report = copy.deepcopy(original)
            mutate(report)
            with self.assertRaises(AssertionError): self.run_audit(report)

    def test_overload_and_incomplete_evidence(self):
        report = synthetic_report()
        report['rows'][0]['load'][0] = 2
        report['timing_qualification']['eligible'] = False
        self.assertFalse(self.run_audit(report)['timing_admission_eligible'])
        report['status'] = 'INTERRUPTED'
        with self.assertRaises(AssertionError): self.run_audit(report)


if __name__ == '__main__':
    unittest.main()
