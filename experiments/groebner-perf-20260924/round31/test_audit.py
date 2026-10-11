"""Evidence mutations must fail even when an attacker recomputes easy hashes."""
import contextlib
import copy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import measure
from audit import audit, audit_report, audit_sources


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name)/'correctness.json.gz'
        argv = ['measure', '--correctness-only', '--repetitions', '2', '--output', str(cls.path)]
        if os.environ.get('QUADRATIC_TEST_METAL') == '1':
            argv.append('--metal')
        with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()):
            measure.main()
        cls.report = json.loads(gzip.decompress(cls.path.read_bytes()))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_complete_report_and_journal(self):
        summary = audit(self.path)
        self.assertFalse(summary['timing_eligible'])
        self.assertTrue(all(c['all_attempts_verified'] for c in summary['controls']))
        self.assertEqual(summary['unique_exact_basis_proofs'], 9)

    def test_math_device_binary_and_ledger_mutations(self):
        def root(r):
            r['rows'][0]['conditional-quadratic']['result']['basis_certificate']['solutions'].pop()
        def basis(r):
            a = r['rows'][0]['conditional-quadratic']['result']
            a['basis_terms'] = [[0]]
            a['basis_sha256'] = hashlib.sha256(json.dumps(a['basis_terms'], sort_keys=True).encode()).hexdigest()
        def count(r):
            r['rows'][0]['conditional-quadratic']['result']['metrics']['consistent'] -= 1
        def fallback(r):
            r['rows'][0]['conditional-quadratic']['result']['metrics']['fallback_assignments'] += 1
        def binary(r):
            r['rows'][0]['conditional-quadratic']['result']['binary_sha256'] = '0'*64
        def device(r):
            r['rows'][0]['conditional-quadratic']['result']['metrics']['gpu_used'] = 1
        def witness(r):
            r['rows'][0]['conditional-quadratic']['result']['curve_witness']['points'][0]['y'] ^= 1
        def time(r):
            r['rows'][0]['conditional-quadratic']['phases_ns']['public_query'] = -1
        def missing(r):
            r['rows'].pop()
        def load(r):
            r['rows'][0]['load'][0] = float('nan')
        for change in (root, basis, count, fallback, binary, device, witness, time, missing, load):
            report = copy.deepcopy(self.report)
            change(report)
            with self.subTest(change=change.__name__), self.assertRaises(AssertionError):
                audit_report(report, check_sources=False)

    def test_source_and_build_mutations(self):
        for section in ('source_sha256', 'source_snapshot'):
            report = copy.deepcopy(self.report)
            report[section][next(iter(report[section]))] = 'corrupted'
            with self.subTest(section=section), self.assertRaises(AssertionError):
                audit_sources(report)
        report = copy.deepcopy(self.report)
        report['build_receipts']['31']['sources']['round31/producer.cpp'] = '0'*64
        with self.assertRaises(AssertionError):
            audit_sources(report)
        report = copy.deepcopy(self.report)
        report['build_receipts']['31']['generated']['kernel.inc'] = '0'*64
        with self.assertRaises(AssertionError):
            audit_sources(report)

    def test_failures_are_retained_and_disqualify_a_win(self):
        report = copy.deepcopy(self.report)
        report['rows'][0]['conditional-quadratic']['result'] = {'status': 'inconclusive', 'verified': False}
        summary = audit_report(report, check_sources=False)
        control = summary['controls'][0]
        self.assertFalse(control['all_attempts_verified'])
        self.assertFalse(any(control['wins'].values()))
        self.assertEqual(summary['statuses']['conditional-quadratic:inconclusive'], 1)

    def test_admission_boundaries(self):
        r = copy.deepcopy(self.report)
        cpus = r['host']['logical_cpus']
        self.assertFalse(measure.timing_eligible(r, cpus, 1))
        r['correctness_only'], r['admission']['admitted'] = False, True
        r['admission']['load'] = r['host']['load_end'] = [0, 0, 0]
        for row in r['rows']:
            row['load'] = row['load_end'] = [0, 0, 0]
        self.assertTrue(measure.timing_eligible(r, cpus, 1))
        for boundary in ('load', 'load_end'):
            r['rows'][0][boundary] = [cpus+1, 0, 0]
            self.assertFalse(measure.timing_eligible(r, cpus, 1))
            r['rows'][0][boundary] = [0, 0, 0]
        r['status'] = 'INTERRUPTED'
        self.assertFalse(measure.timing_eligible(r, cpus, 1))


if __name__ == '__main__':
    unittest.main()
