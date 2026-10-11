"""A busy host must not start numerical work or overwrite retained evidence."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import benchmark


class AdmissionTests(unittest.TestCase):
    def test_busy_host_stops_before_fixture_or_query(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run.json.gz'
            with patch('sys.argv', ['benchmark', '--output', str(output)]), \
                    patch.object(benchmark.os, 'getloadavg', return_value=(15, 9, 8)), \
                    patch.object(benchmark.os, 'cpu_count', return_value=14), \
                    patch.object(benchmark, 'TruthQuery') as query, \
                    patch.object(benchmark, 'make_instance') as fixture, redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    benchmark.main()
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(output.exists())
            record = json.loads(output.with_suffix('.gz.admission.json').read_text())
            self.assertFalse(record['admitted'])
            self.assertEqual(record['timed_attempts'], 0)
            query.assert_not_called()
            fixture.assert_not_called()

    def test_reports_and_admissions_are_preserved(self):
        for suffix in ('', '.admission.json'):
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'run.json.gz'
                occupied = Path(str(output) + suffix)
                occupied.write_bytes(b'preserve evidence')
                with patch('sys.argv', ['benchmark', '--output', str(output)]), redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        benchmark.main()
                self.assertEqual(occupied.read_bytes(), b'preserve evidence')

    def test_overload_disqualifies_without_discarding_rows(self):
        report = {'status': 'RECORDED', 'admission': {'admitted': True}, 'rows': [{'load': [14, 0, 0]}],
                  'host': {'load_end': [14, 0, 0]}}
        self.assertTrue(benchmark.timing_eligible(report, 14, 1))
        report['rows'][0]['load'][0] = 15
        self.assertFalse(benchmark.timing_eligible(report, 14, 1))
        self.assertEqual(len(report['rows']), 1)
        report['rows'][0]['load'][0] = 1
        report['host']['load_end'][0] = 15
        self.assertFalse(benchmark.timing_eligible(report, 14, 1))
        report['host']['load_end'][0] = 1
        report['status'] = 'INTERRUPTED'
        self.assertFalse(benchmark.timing_eligible(report, 14, 1))


if __name__ == '__main__':
    unittest.main()
