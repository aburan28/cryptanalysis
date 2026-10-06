"""Synthetic metadata/corruption controls; none of these timings are measurements."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

from audit import BUILD_SOURCE_KEYS, PREFIX, audit_report
from benchmark import ARMS, digest, sources
from build import generated_sources

HERE = Path(__file__).resolve().parent


def synthetic_report():
    snapshot = sources()
    hashes = {k: hashlib.sha256(v.encode()).hexdigest() for k, v in snapshot.items()}
    receipts = {str(v): json.loads((HERE.parent/f'round{v}/build/receipt.json').read_text())
                for v in (14, 15, 17, 18, 20)}
    for version in ('14', '15', '17', '18'):
        receipts[version]['binaries'] = {'synthetic': 'binary-'+version}
    receipts['20']['binaries'] = {PREFIX+'round4/build/packed_dual.so': 'producer'}
    for version, names in BUILD_SOURCE_KEYS.items():
        spec = importlib.util.spec_from_file_location('fixture_build_'+version,
            HERE.parent/f'round{version}/build.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        receipts[version] = {'source_sha256': {k: hashes[k] for k in names},
            'binaries': {'synthetic': 'binary-'+version},
            'generated_sha256': {k: hashlib.sha256(v.encode()).hexdigest()
                for k, v in module.generated_sources(snapshot).items()}}
    report = {'schema': 'round24-mapped-metal/1', 'status': 'RECORDED',
        'candidate_id': None, 'IC_online_ms': None, 'rho_online_ms': None,
        'arms': ARMS, 'repetitions': 2, 'source_snapshot': snapshot, 'source_sha256': hashes,
        'build_receipts': receipts, 'candidates': {},
        'admission': {'admitted': True, 'load': [0, 0, 0], 'max_load_per_cpu': 1, 'timed_attempts': 240},
        'host': {'logical_cpus': 1, 'load_end': [0, 0, 0]},
        'timing_qualification': {'eligible': True}, 'inputs': [], 'rows': []}
    # v=0 and (x,y)=(0,1) on y^2+xy=x^3+1 over GF(8).
    for i in range(16):
        fixture = {'name': 'synthetic-'+str(i), 'n': 3, 'mod': 11, 'b': 1,
            'm': 1, 'ell': 1, 'nvars': 1, 'target': {'x': 0, 'y': 1}, 'reference_anf': [[1, 1]]}
        workload = digest(fixture)
        report['inputs'].append({**fixture, 'fixture_ns': 0, 'workload_sha256': workload})
        for rep in range(3):
            row = {'name': fixture['name'], 'workload_id': workload, 'workload_sha256': workload,
                'repetition': rep, 'warmup': rep == 0, 'order': ARMS, 'load': [0, 0, 0], 'load_end': [0, 0, 0]}
            for arm in ARMS:
                version = '18' if arm == 'cpu' else '23' if arm == 'sparse-cpu' else '22' if arm == 'coeff' else '24'
                backend = {'18': 'independent-packed-bitslice-zeta', '23': 'independent-packed-sparse-proof',
                    '22': 'independent-packed-metal-coefficient-zeta', '24': 'independent-packed-metal-mapped-zeta'}[version]
                certificate = {'verified': True, 'backend': backend}
                if arm == 'sparse-cpu':
                    certificate['proof_stats'] = {'mode': 2, 'budget_limit': 65536, 'seconds': 0}
                if version in ('22', '24'):
                    certificate.update(scratch_bytes=72, evaluation_counts={'word_bits': 32, 'zeta_words': 1, 'high_gather_words': 0},
                        gpu_timing={**{k: 0 for k in ('prepare', 'encode', 'execute', 'extract', 'basis_check', 'total', 'spin', 'polls')},
                            'device': None, 'calls': 1, 'dispatches': 2, 'threads': 256, 'blocking_fallback': 1,
                            'shared_buffer_bytes': 72, 'zeta_words': 1, 'high_gather_words': 0})
                answer = {'status': 'solved', 'verified': True, 'groebner_verified': True,
                    'public_target': fixture['target'], 'assignment': 0, 'basis_sha256': 'basis',
                    'basis_certificate': certificate, 'complete_query_ns': 16,
                    'phases_ns': {'basis_and_certificate': 16}, 'verification_seconds': 0,
                    'curve_witness': {'verified': True, 'code': 0, 'points': [fixture['target']], 'signs': 0, 'patterns': 1},
                    'query_arm': arm, 'replay_backend': 'native-public-point', 'replay_binary_sha256': 'binary-17',
                    'descent_binary_sha256': 'binary-14', 'binary_sha256': 'producer',
                    'equation_backend': 'independent-native-direct-packed', 'equation_binary_sha256': 'binary-'+version,
                    'verifier_binary_sha256': 'binary-'+version, 'gpu_device': 'synthetic device' if version in ('22', '24') else None}
                row[arm] = {'wall_ns': 20, 'cpu_ns': 20, 'phases_ns': {'public_query': 18, 'reference_equations': 2},
                    'outside_timing_witness_audit': {'verified': True, 'wall_ns': 1}, 'result': answer}
            report['rows'].append(row)
    return report


class AuditTests(unittest.TestCase):
    def test_contract_and_failed_attempts(self):
        report = synthetic_report()
        checked = audit_report(report)
        self.assertEqual(checked['statuses'], {a+':solved': 48 for a in ARMS})
        self.assertFalse(any(checked['controls'][0]['candidate_gpu_win'].values()))
        report['rows'][1]['mapped']['result'] = {'status': 'work-limit', 'verified': False}
        checked = audit_report(report)
        self.assertEqual(checked['statuses']['mapped:work-limit'], 1)
        self.assertNotIn('candidate_gpu_win', checked['controls'][0])

    def test_corrupted_receipts_equations_and_accounting(self):
        original = synthetic_report()
        mutations = [
            lambda r: r['rows'][0]['mapped']['result']['curve_witness']['points'][0].update(y=0),
            lambda r: r['rows'][0]['mapped'].update(wall_ns=21),
            lambda r: r['rows'][0]['cpu']['result'].update(assignment=1),
            lambda r: r['rows'][0]['mapped']['result'].update(verifier_binary_sha256='wrong'),
            lambda r: r['rows'][0]['mapped']['result'].update(equation_binary_sha256='wrong'),
            lambda r: r['rows'][0]['mapped']['result'].update(binary_sha256='wrong'),
            lambda r: r['rows'][0]['mapped']['result'].update(replay_binary_sha256='wrong'),
            lambda r: r['rows'][0]['mapped']['result']['basis_certificate'].update(backend='wrong'),
            lambda r: r['rows'][0]['mapped']['result']['basis_certificate']['gpu_timing'].update(dispatches=0),
            lambda r: r['rows'][0]['mapped']['result']['basis_certificate']['gpu_timing'].update(total=float('nan')),
            lambda r: r['rows'][0]['mapped']['result']['basis_certificate']['gpu_timing'].update(zeta_words=0),
            lambda r: r['rows'][0]['mapped']['result']['basis_certificate']['evaluation_counts'].update(word_bits=64),
            lambda r: r['rows'][0]['sparse-cpu']['result']['basis_certificate']['proof_stats'].update(mode=0),
            lambda r: r['rows'].pop(),
            lambda r: r['inputs'][0].update(b=2),
            lambda r: r['source_snapshot'].pop(PREFIX+'round24/build.py'),
            lambda r: r['build_receipts']['24']['source_sha256'].clear(),
            lambda r: r['build_receipts']['23']['source_sha256'].clear(),
            lambda r: r['build_receipts']['22']['source_sha256'].clear(),
            lambda r: r['build_receipts']['20']['source_sha256'].clear(),
            lambda r: r['build_receipts']['24']['generated_sha256'].update({'mapped_gpu.mm': 'wrong'}),
            lambda r: r['build_receipts']['22']['generated_sha256'].clear(),
            lambda r: r['build_receipts']['23']['generated_sha256'].clear(),
        ]
        for change in mutations:
            with self.subTest(change=mutations.index(change)):
                report = copy.deepcopy(original)
                change(report)
                with self.assertRaises(AssertionError): audit_report(report)

    def test_cpu_improvement_and_load_must_both_be_charged(self):
        report = synthetic_report()
        for row in report['rows']:
            row['sparse-cpu'].update(wall_ns=10, phases_ns={'public_query': 8, 'reference_equations': 2})
            row['sparse-cpu']['result'].update(complete_query_ns=8, phases_ns={'basis_and_certificate': 8})
        checked = audit_report(report)
        self.assertFalse(any(c['candidate_gpu_win']['mapped'] for c in checked['controls']))
        report['rows'][0]['load_end'][0] = 2
        report['timing_qualification']['eligible'] = False
        self.assertFalse(audit_report(report)['timing_admission_eligible'])
        report['status'] = 'INTERRUPTED'
        with self.assertRaises(AssertionError): audit_report(report)


class GenerationTests(unittest.TestCase):
    def test_only_owned_mapping_changes(self):
        snapshot = sources()
        generated = generated_sources(snapshot)
        host = generated['mapped_gpu.mm']
        original = snapshot[PREFIX+'round22/coefficient_gpu.mm'].replace('#include "build/', '#include "')
        restored = host.replace('    Word *mapped = nullptr;\n', '').replace(
            '        mapped = buffer ? static_cast<Word *>(buffer.contents) : nullptr;\n'
            '        if (!mapped) throw std::runtime_error("shared buffer allocation failed");',
            '        if (!buffer || !buffer.contents) throw std::runtime_error("shared buffer allocation failed");')
        restored = restored.replace('    Word *data() { return mapped; }', '    Word *data() { return static_cast<Word *>(buffer.contents); }')
        restored = restored.replace('    const Word *data() const { return mapped; }', '    const Word *data() const { return static_cast<const Word *>(buffer.contents); }')
        self.assertEqual(restored, original)
        for name in ('round22/coefficient_gpu.mm', 'round22/build.py', 'round22/test_coefficients.mm'):
            bad = dict(snapshot)
            bad[PREFIX+name] += '\n'
            with self.assertRaises(ValueError): generated_sources(bad)


if __name__ == '__main__':
    unittest.main()
