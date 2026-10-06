"""Independent mathematical and checkpoint audit on actual complete toy runs."""
import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from replay_query import HERE
from replay_audit import audit, audit_report


class ReplayAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'trace.json.gz'
            subprocess.run([sys.executable,str(HERE/'replay_measure.py'),'--correctness-only',
                            '--dimensions','3','--repetitions','2','--output',str(out)],check=True)
            cls.summary = audit(out)
            cls.report = json.loads(gzip.decompress(out.read_bytes()))

    def test_actual_basis_relation_recovery_and_journal(self):
        self.assertFalse(self.summary['timing_admission_eligible'])
        self.assertTrue(all(w['all_attempts_verified'] for w in self.summary['workloads']))
        self.assertGreater(self.summary['independent_unique_basis_proofs'],0)

    def test_corrupt_partial_root_trace_is_rejected(self):
        def chosen(r):
            return next(a for a in r['rows'][0]['results']['euclid']['answer']['attempts'] if a['relations'])
        mutations = {
            'missing_prefix':lambda a:a.update(root_checks=[]),
            'wrong_count':lambda a:a.update(roots_checked=999),
            'wrong_assignment':lambda a:a['root_checks'][0].update(assignment=999),
            'false_rejection':lambda a:a['root_checks'][0].update(status='lift_rejected'),
            'wrong_policy':lambda a:a.update(target_root_policy='all-roots'),
            'missing_basis_root':lambda a:a['basis']['basis_certificate'].update(solutions=[]),
            'continued_after_accept':lambda a:a['root_checks'].append(copy.deepcopy(a['root_checks'][0])),
        }
        for name,mutate in mutations.items():
            with self.subTest(name=name):
                r = copy.deepcopy(self.report)
                mutate(chosen(r))
                # Preserve the redundant receipt binding to test the mathematical
                # trace validation itself, rather than only duplicate equality.
                r['rows'][0]['receipts']['euclid']['target_result'] = r['rows'][0]['results']['euclid']['answer']
                with self.assertRaises(ValueError): audit_report(r)

    def test_verifier_reference_and_receipt_corruption_is_rejected(self):
        def first_basis(report):
            return next(a['basis'] for a in report['rows'][0]['receipts']['euclid']['preparation']['attempts'] if a.get('basis', {}).get('status') == 'gb')
        mutations = {
            'wrong_arithmetic': lambda r: r['rows'][0]['results']['euclid']['answer']['independent_arithmetic'].update(inversion='trusted producer scalar'),
            'wrong_verifier': lambda r: first_basis(r).update(verifier_binary_sha256='wrong'),
            'wrong_backend': lambda r: first_basis(r)['basis_certificate'].update(backend='producer-roots'),
            'wrong_rho_pair': lambda r: r['rows'][0]['receipts']['euclid'].update(rho_measured=r['rows'][0]['results']['rho-power']['answer']),
            'wrong_rho_arithmetic': lambda r: r['rows'][0]['results']['rho-euclid']['answer']['reference_policy']['independent_arithmetic'].update(inversion='exponentiation by 2^n-2'),
            'unbound_sparse_source': lambda r: r['build_receipts']['23']['source_sha256'].clear(),
            'wrong_generated_proof': lambda r: r['build_receipts']['23']['generated_sha256'].clear(),
            'wrong_rho_target': lambda r: r['rows'][0]['results']['rho-euclid']['answer']['target'].update(x=1),
            'multiworker_rho': lambda r: r['rows'][0]['results']['rho-euclid']['answer']['reference_policy'].update(worker_count=2),
            'shared_rho_memory': lambda r: r['rows'][0]['results']['rho-euclid']['answer']['reference_policy'].update(distinguished_point_memory_bytes=1024),
            'multiple_native_threads': lambda r: r['rows'][0]['receipts']['euclid']['resource_envelope'].update(native_threads=2),
            'omitted_online_work': lambda r: r['rows'][0]['results']['euclid']['answer'].update(online_wall_ns=1),
            'reused_run': lambda r: r['rows'].append(copy.deepcopy(r['rows'][0])),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                report = copy.deepcopy(self.report)
                mutate(report)
                with self.assertRaises(ValueError): audit_report(report)


if __name__ == '__main__': unittest.main()
