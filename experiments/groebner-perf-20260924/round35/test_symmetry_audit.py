"""Evidence mutations must fail even when an attacker recomputes easy hashes."""
import base64
import contextlib
import copy
import gzip
import hashlib
import io
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import measure_symmetry as measure
# Legacy numerical imports prepend several older experiment directories.
# Bind this round's audit explicitly instead of importing their audit.py.
_spec = importlib.util.spec_from_file_location('fixed_block_symmetry_audit', Path(__file__).with_name('audit_symmetry.py'))
_audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_audit)
audit, audit_report, audit_sources = _audit.audit, _audit.audit_report, _audit.audit_sources


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
            r['rows'][0]['quadratic-symmetry-cpu']['result']['basis_certificate']['solutions'].pop()
        def basis(r):
            a = r['rows'][0]['quadratic-symmetry-cpu']['result']
            a['basis_terms'] = [[0]]
            a['basis_sha256'] = hashlib.sha256(json.dumps(a['basis_terms'], sort_keys=True).encode()).hexdigest()
        def count(r):
            r['rows'][0]['quadratic-symmetry-cpu']['result']['metrics']['consistent'] -= 1
        def fallback(r):
            r['rows'][0]['quadratic-symmetry-cpu']['result']['metrics']['fallback_assignments'] += 1
        def binary(r):
            r['rows'][0]['quadratic-symmetry-cpu']['result']['binary_sha256'] = '0'*64
        def device(r):
            r['rows'][0]['quadratic-symmetry-cpu']['result']['metrics']['gpu_used'] = 1
        def width(r):
            r['rows'][0]['quadratic-symmetry-cpu']['result']['producer_coefficient_word_bits'] = 64
        def checker_width(r):
            r['rows'][0]['quadratic-symmetry-cpu']['result']['basis_certificate']['coefficient_word_bits'] = 64
        def workspace(r):
            r['rows'][0]['quadratic-symmetry-cpu']['result']['metrics']['workspace_bytes'] += 4
        def checker_workspace(r):
            r['rows'][0]['quadratic-symmetry-cpu']['result']['basis_certificate']['stats']['workspace_bytes'] += 4
        def witness(r):
            r['rows'][0]['quadratic-symmetry-cpu']['result']['curve_witness']['points'][0]['y'] ^= 1
        def time(r):
            r['rows'][0]['quadratic-symmetry-cpu']['phases_ns']['public_query'] = -1
        def missing(r):
            r['rows'].pop()
        def load(r):
            r['rows'][0]['load'][0] = float('nan')
        for change in (root, basis, count, fallback, binary, device, width, checker_width, workspace, checker_workspace, witness, time, missing, load):
            report = copy.deepcopy(self.report)
            change(report)
            with self.subTest(change=change.__name__), self.assertRaises(AssertionError):
                audit_report(report, check_sources=False)

    def test_proof_mutations_even_with_recomputed_hash(self):
        for kind in ('identity', 'zero', 'extent', 'byteorder', 'stats'):
            report = copy.deepcopy(self.report)
            answer = report['rows'][0]['quadratic-symmetry-cpu']['result']
            old = answer['proof_sha256']
            payload = report['proofs'][old]
            raw = bytearray(base64.b64decode(payload['base64']))
            if kind == 'stats':
                answer['basis_certificate']['stats']['assignments'] += 1
            elif kind == 'byteorder':
                answer['proof_byteorder'] = 'big' if payload['byteorder'] == 'little' else 'little'
            else:
                if kind == 'identity':
                    raw[:] = bytes(len(raw))
                    # One equation cannot certify an actual root branch.
                    root = answer['basis_certificate']['solutions'][0]
                    branch = root & ((1 << 12)-1)
                    raw[branch*8:(branch+1)*8] = (1).to_bytes(8, payload['byteorder'])
                elif kind == 'zero':
                    raw[:] = bytes(len(raw))
                else:
                    del raw[-8:]
                identifier = hashlib.sha256(raw).hexdigest()
                report['proofs'][identifier] = {**payload, 'bytes':len(raw), 'base64':base64.b64encode(raw).decode()}
                answer['proof_sha256'] = identifier
            with self.subTest(kind=kind), self.assertRaises(AssertionError):
                audit_report(report, check_sources=False)

    def test_source_and_build_mutations(self):
        for section in ('source_sha256', 'source_snapshot'):
            report = copy.deepcopy(self.report)
            report[section][next(iter(report[section]))] = 'corrupted'
            with self.subTest(section=section), self.assertRaises(AssertionError):
                audit_sources(report)
        report = copy.deepcopy(self.report)
        report['build_receipts']['35']['sources']['round35/producer.cpp'] = '0'*64
        with self.assertRaises(AssertionError):
            audit_sources(report)
        report = copy.deepcopy(self.report)
        report['build_receipts']['35']['generated']['kernel.inc'] = '0'*64
        with self.assertRaises(AssertionError):
            audit_sources(report)

    def test_failures_are_retained_and_disqualify_a_win(self):
        report = copy.deepcopy(self.report)
        report['rows'][0]['quadratic-symmetry-cpu']['result'] = {'status': 'inconclusive', 'verified': False}
        summary = audit_report(report, check_sources=False)
        control = summary['controls'][0]
        self.assertFalse(control['all_attempts_verified'])
        self.assertFalse(any(control['wins'].values()))
        self.assertEqual(summary['statuses']['quadratic-symmetry-cpu:inconclusive'], 1)

    def test_multiplier_accounting_and_expanded_baseline_flags(self):
        for field in ('attempts','rows','row_xors','word_xors','proof_capacity_words','workspace_bytes'):
            report = copy.deepcopy(self.report)
            report['rows'][0]['quadratic-symmetry-cpu']['result']['multiplier_stats'][field] += 1
            with self.subTest(field=field), self.assertRaises(AssertionError):
                audit_report(report, check_sources=False)
        for field in ('extended_contradictions','multiplier_parities','multiplier_words'):
            report = copy.deepcopy(self.report)
            report['rows'][0]['quadratic-symmetry-cpu']['result']['basis_certificate']['stats'][field] += 1
            with self.subTest(field=field), self.assertRaises(AssertionError):
                audit_report(report, check_sources=False)
        report = copy.deepcopy(self.report)
        report['limits']['multiplier_work_budget'] *= 2
        with self.assertRaises(AssertionError):
            audit_report(report, check_sources=False)
        report = copy.deepcopy(self.report)
        command = next(c for c in report['build_receipts']['34']['commands'] if Path(c[-1]).name.startswith('baseline-checker'))
        command.remove('-DBRANCH_CHECK_ENUMERATION_BUDGET=134217728')
        with self.assertRaises(AssertionError):
            audit_sources(report)

    def test_symmetry_claims_and_actual_work_mutations(self):
        for field in ('enabled','shape_fallback','asymmetric_fallback','compared_pairs','compared_coefficients',
                      'representatives','aliases','constant_copies','affine_copies','affine_copy_words',
                      'copy_budget_skips','copied_roots','rootless_aliases','gpu_linearized_branches','workspace_bytes'):
            report=copy.deepcopy(self.report)
            report['rows'][0]['quadratic-symmetry-cpu']['result']['symmetry_stats'][field]+=1
            with self.subTest(field=field),self.assertRaises(AssertionError):audit_report(report,check_sources=False)
        report=copy.deepcopy(self.report)
        report['limits']['symmetry_copy_words_budget']+=1
        with self.assertRaises(AssertionError):audit_report(report,check_sources=False)

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
