"""Do not begin numerical work on a rejected host or overwrite prior attempts."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import measure


class AdmissionTests(unittest.TestCase):
    def test_busy_host_and_bounded_wait_keep_all_samples(self):
        for wait in (0, 60):
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp)/'run.json.gz'
                clock = [0]
                def sleep(seconds): clock[0] += seconds
                with patch('sys.argv', ['measure', '--output', str(output), '--admission-wait-seconds', str(wait)]), \
                     patch.object(measure.os, 'cpu_count', return_value=14), \
                     patch.object(measure.os, 'getloadavg', return_value=(15, 9, 8)), \
                     patch.object(measure.time, 'monotonic', side_effect=lambda: clock[0]), \
                     patch.object(measure.time, 'sleep', side_effect=sleep), \
                     patch.object(measure, 'PreparedIC') as query, redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as error: measure.main()
                self.assertEqual(error.exception.code, 2)
                query.assert_not_called()
                self.assertFalse(output.exists())
                admission = json.loads(Path(str(output)+'.admission.json').read_text())
                self.assertFalse(admission['admitted'])
                self.assertEqual(admission['timed_attempts'], 0)
                self.assertEqual([r['elapsed_seconds'] for r in admission['samples']], [0] if wait == 0 else [0, 30, 60])

    def test_existing_evidence_and_duplicate_workloads_reject(self):
        for suffix in ('', '.admission.json'):
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp)/'run.json.gz'
                occupied = Path(str(output)+suffix)
                occupied.write_bytes(b'retain')
                with patch('sys.argv', ['measure', '--output', str(output)]), redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit): measure.main()
                self.assertEqual(occupied.read_bytes(), b'retain')
        with patch('sys.argv', ['measure', '--output', '/unused', '--dimensions', '3', '3']), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): measure.main()

    def test_every_timing_gate_is_required(self):
        report = {'status': 'RECORDED', 'correctness_only': False,
            'admission': {'admitted': True, 'load': [0, 0, 0], 'logical_cpus': 14, 'max_load_per_cpu': 1},
            'rows': [{'load_start': [0, 0, 0], 'load_end': [0, 0, 0]}], 'host': {'load_end': [0, 0, 0]}}
        self.assertTrue(measure.eligible(report))
        for values in (report['admission']['load'], report['rows'][0]['load_start'], report['rows'][0]['load_end'], report['host']['load_end']):
            values[0] = 15
            self.assertFalse(measure.eligible(report))
            values[0] = 0
        report['correctness_only'] = True
        self.assertFalse(measure.eligible(report))
        report['correctness_only'] = False
        report['status'] = 'INTERRUPTED'
        self.assertFalse(measure.eligible(report))


if __name__ == '__main__':
    unittest.main()
