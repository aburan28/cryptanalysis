"""Independent mathematical and checkpoint audit on actual complete toy runs."""
import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from first_query import HERE
from first_audit import audit, audit_report


class FirstAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'trace.json.gz'
            subprocess.run([sys.executable,str(HERE/'first_measure.py'),'--correctness-only',
                            '--dimensions','3','--repetitions','2','--output',str(out)],check=True)
            cls.summary = audit(out)
            cls.report = json.loads(gzip.decompress(out.read_bytes()))

    def test_actual_basis_relation_recovery_and_journal(self):
        self.assertFalse(self.summary['timing_admission_eligible'])
        self.assertTrue(all(w['all_attempts_verified'] for w in self.summary['workloads']))
        self.assertGreater(self.summary['independent_unique_basis_proofs'],0)

    def test_corrupt_partial_root_trace_is_rejected(self):
        def chosen(r):
            return next(a for a in r['rows'][0]['results']['first-usable']['answer']['attempts'] if a['relations'])
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
                r['rows'][0]['receipts']['first-usable']['target_result'] = r['rows'][0]['results']['first-usable']['answer']
                with self.assertRaises(ValueError): audit_report(r)


if __name__ == '__main__': unittest.main()
