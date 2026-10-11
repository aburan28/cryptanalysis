"""Reject altered proofs, pairing, stage identities and omitted charged work."""
import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from conditional_ic import HERE
from conditional_audit import audit, audit_report


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'trace.json.gz'
            subprocess.run([sys.executable,str(HERE/'conditional_measure.py'),
                '--correctness-only','--dimensions','3','--repetitions','2','--output',str(output)],check=True)
            cls.summary = audit(output)
            cls.report = json.loads(gzip.decompress(output.read_bytes()))

    def test_independent_proofs_and_journal(self):
        self.assertFalse(self.summary['timing_admission_eligible'])
        self.assertTrue(all(w['all_attempts_verified'] for w in self.summary['workloads']))
        self.assertGreater(self.summary['independent_unique_basis_proofs'],0)

    def test_corrupt_trace_and_pairing_reject(self):
        def basis(r):
            return next(a['basis'] for a in r['rows'][0]['receipts']['two-conditional']['preparation']['attempts']
                        if a['basis']['status']=='gb' and a['basis']['basis_certificate']['root_count'])
        def attempt(r):
            return next(a for a in r['rows'][0]['results']['two-conditional']['answer']['attempts'] if a['relations'])
        mutations = {
            'missing_roots':lambda r:basis(r)['basis_certificate'].update(solutions=[]),
            'wrong_basis':lambda r:basis(r)['basis_terms'].append([0]),
            'wrong_binary':lambda r:basis(r).update(verifier_binary_sha256='wrong'),
            'false_conditional_count':lambda r:basis(r)['basis_certificate']['stats'].update(roots=999),
            'wrong_method':lambda r:basis(r)['basis_certificate'].update(backend='producer'),
            'missing_prefix':lambda r:attempt(r).update(root_checks=[]),
            'bad_exclusion':lambda r:r['inputs'][0]['workload']['excluded_points_by_arm'].update({'two-conditional':'wrong'}),
            'wrong_rho_target':lambda r:r['rows'][0]['results']['rho']['answer']['target'].update(x=1),
            'unbound_native_sources':lambda r:r['build_receipts']['27']['sources'].clear(),
            'wrong_arithmetic':lambda r:r['rows'][0]['results']['two-conditional']['answer']['independent_arithmetic'].update(inversion='producer'),
            'omitted_online_cost':lambda r:r['rows'][0]['results']['two-conditional']['answer'].update(online_wall_ns=1),
            'duplicate_run':lambda r:r['rows'].append(copy.deepcopy(r['rows'][0])),
            'missing_run':lambda r:r['rows'].pop(),
        }
        for name,mutation in mutations.items():
            with self.subTest(name=name):
                report = copy.deepcopy(self.report)
                mutation(report)
                # Maintain the duplicate bindings for checks of the underlying
                # mathematical and accounting records, not just equality.
                row = report['rows'][0]
                row['receipts']['two-conditional']['target_result'] = row['results']['two-conditional']['answer']
                with self.assertRaises(ValueError):audit_report(report)


if __name__ == '__main__':unittest.main()
