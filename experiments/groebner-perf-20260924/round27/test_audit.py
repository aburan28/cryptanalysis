import contextlib
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import branch_measure
from branch_audit import audit, audit_report, audit_sources
from branch_measure import timing_eligible


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/'correctness.json.gz'
        with patch.object(sys,'argv',['measure','--correctness-only','--repetitions','2',
                                      '--output',str(cls.path)]), contextlib.redirect_stdout(io.StringIO()):
            branch_measure.main()
        cls.report=json.loads(gzip.decompress(cls.path.read_bytes()))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_complete_report_and_journal(self):
        summary=audit(self.path)
        self.assertFalse(summary['timing_eligible'])
        self.assertTrue(all(s['all_attempts_verified'] for s in summary['controls']))
        self.assertEqual(summary['unique_exact_basis_proofs'],9)

    def test_math_receipt_mutations(self):
        def bad_root(r):
            cert=r['rows'][0]['conditional-linear']['result']['basis_certificate']
            cert['solutions']=cert['solutions'][1:]
        def bad_basis(r):
            a=r['rows'][0]['conditional-linear']['result']
            a['basis_terms']=[[0]]
            a['basis_sha256']=hashlib.sha256(json.dumps(a['basis_terms'],sort_keys=True).encode()).hexdigest()
        def bad_count(r):
            r['rows'][0]['conditional-linear']['result']['basis_certificate']['stats']['branches']-=1
        def bad_binary(r):
            r['rows'][0]['conditional-linear']['result']['binary_sha256']='0'*64
        def bad_witness(r):
            r['rows'][0]['conditional-linear']['result']['curve_witness']['points'][0]['y']^=1
        def bad_time(r):
            r['rows'][0]['conditional-linear']['phases_ns']['public_query']=-1
        def missing(r):
            r['rows'].pop()
        for change in (bad_root,bad_basis,bad_count,bad_binary,bad_witness,bad_time,missing):
            report=copy.deepcopy(self.report)
            change(report)
            with self.subTest(change=change.__name__), self.assertRaises(AssertionError):
                audit_report(report,check_sources=False)

    def test_source_and_build_mutations(self):
        report=copy.deepcopy(self.report)
        report['source_sha256'][next(iter(report['source_sha256']))]='0'*64
        with self.assertRaises(AssertionError): audit_sources(report)
        report=copy.deepcopy(self.report)
        report['build_receipts']['27']['sources']['checker.cpp']='0'*64
        with self.assertRaises(AssertionError): audit_sources(report)

    def test_load_and_correctness_admission(self):
        r=copy.deepcopy(self.report)
        cpus=r['host']['logical_cpus']
        self.assertFalse(timing_eligible(r,cpus,1))
        r['correctness_only']=False
        r['admission']['admitted']=True
        r['admission']['load']=[0,0,0]
        r['host']['load_end']=[0,0,0]
        for row in r['rows']:
            row['load']=row['load_end']=[0,0,0]
        self.assertTrue(timing_eligible(r,cpus,1))
        for boundary in ('load','load_end'):
            r['rows'][0][boundary]=[cpus+1,0,0]
            self.assertFalse(timing_eligible(r,cpus,1))
            r['rows'][0][boundary]=[0,0,0]
        r['status']='INTERRUPTED'
        self.assertFalse(timing_eligible(r,cpus,1))


if __name__=='__main__':
    unittest.main()
