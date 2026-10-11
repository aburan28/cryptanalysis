"""Audit corruption controls on actual toy executions, never timing claims."""
import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ic_query import HERE
from audit import audit_report
from measure import eligible


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)/'trace.json.gz'
            subprocess.run([sys.executable, str(HERE/'measure.py'), '--correctness-only',
                            '--dimensions','3','--repetitions','2','--output',str(out)], check=True)
            cls.report = json.loads(gzip.decompress(out.read_bytes()))

    def test_independent_real_report(self):
        audit = audit_report(self.report)
        self.assertFalse(audit['timing_admission_eligible'])
        self.assertGreater(audit['independent_unique_basis_proofs'], 0)
        self.assertTrue(all(w['all_attempts_verified'] and not w['qualified_comparison'] for w in audit['workloads']))

    def test_corrupted_evidence_rejected(self):
        mutations = {
            'source': lambda r: r['source_sha256'].update({'invented':'0'*64}),
            'omitted_run': lambda r: r['rows'].pop(),
            'false_admission': lambda r: r.update(timing_admission_eligible=True),
            'native_binary': lambda r: r['rows'][0]['receipts']['packed']['selected_binary_sha256'].update(certificate='0'*64),
            'rank': lambda r: r['rows'][0]['receipts']['baseline']['preparation']['attempts'][0].update(rank=1),
            'column_log': lambda r: r['rows'][0]['receipts']['baseline']['preparation']['column_logs'].__setitem__(0,0),
            'false_roots': lambda r: next(a for a in r['rows'][0]['receipts']['baseline']['preparation']['attempts'] if a['relations'])['basis']['basis_certificate'].update(solutions=[]),
            'unaccounted_attempt': lambda r: r['rows'][0]['receipts']['baseline']['counts'].update(descent_attempts=999),
            'phase_total': lambda r: r['rows'][0]['receipts']['baseline']['preparation']['phase_wall_ns'].update(pdp=0),
            'basis': lambda r: r['rows'][0]['receipts']['baseline']['preparation']['attempts'][0]['basis'].update(basis_terms=[[1]]),
            'bad_curve_witness': lambda r: next(a for a in r['rows'][0]['receipts']['baseline']['preparation']['attempts'] if a['relations'])['relations'][0]['witness']['points'][0].update(y=0),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                bad = copy.deepcopy(self.report)
                mutate(bad)
                with self.assertRaises(ValueError): audit_report(bad)

    def test_load_gate_on_synthetic_report(self):
        # Synthetic gate-only fixture, not a measured result.
        r = {'status':'RECORDED','correctness_only':False,
             'admission':{'admitted':True,'logical_cpus':2,'max_load_per_cpu':1,'load':[1,1,1]},
             'rows':[{'load_start':[1,1,1],'load_end':[1,1,1]}], 'host':{'load_end':[1,1,1]}}
        self.assertTrue(eligible(r))
        for mutate in (lambda x:x.update(correctness_only=True),
                       lambda x:x.update(status='INTERRUPTED'),
                       lambda x:x['admission'].update(admitted=False),
                       lambda x:x['rows'][0].update(load_end=[3,1,1]),
                       lambda x:x['host'].update(load_end=[3,1,1])):
            bad = copy.deepcopy(r)
            mutate(bad)
            self.assertFalse(eligible(bad))


if __name__ == '__main__': unittest.main()
