"""Timing admission must fail before target generation, GPU setup or solving."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import benchmark


class AdmissionTests(unittest.TestCase):
    def test_busy_preflight_records_no_work(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'run.json.gz'
            with patch('sys.argv',['benchmark','--output',str(output)]), \
                    patch.object(benchmark.os,'getloadavg',return_value=(15,9,8)), \
                    patch.object(benchmark.os,'cpu_count',return_value=14), \
                    patch.object(benchmark,'NativeDescent') as descent, \
                    patch.object(benchmark,'make_instance') as fixture, \
                    patch.object(benchmark,'query') as query, redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as error: benchmark.main()
            self.assertEqual(error.exception.code,2)
            self.assertFalse(output.exists())
            record=json.loads(output.with_suffix('.gz.admission.json').read_text())
            self.assertFalse(record['admitted']);self.assertEqual(record['timed_attempts'],0)
            for mock in (descent,fixture,query): mock.assert_not_called()

    def test_retained_output_and_admission_cannot_be_overwritten(self):
        for occupied in ('report','admission'):
            with tempfile.TemporaryDirectory() as directory:
                output=Path(directory)/'run.json.gz'
                path=output if occupied=='report' else output.with_suffix('.gz.admission.json')
                path.write_bytes(b'preserve evidence')
                with patch('sys.argv',['benchmark','--output',str(output)]), \
                        redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error: benchmark.main()
                self.assertEqual(error.exception.code,2)
                self.assertEqual(path.read_bytes(),b'preserve evidence')

    def test_busy_measured_groups_and_final_load_disqualify(self):
        report={'admission':{'admitted':True},'rows':[{'load':[14,0,0]}],
                'host':{'load_end':[14,0,0]}}
        self.assertTrue(benchmark.timing_eligible(report,14,1))
        report['rows'][0]['load'][0]=15
        self.assertFalse(benchmark.timing_eligible(report,14,1))
        report['rows'][0]['load'][0]=1;report['host']['load_end'][0]=15
        self.assertFalse(benchmark.timing_eligible(report,14,1))
        report['host']['load_end'][0]=1;report['admission']['admitted']=False
        self.assertFalse(benchmark.timing_eligible(report,14,1))
        report['admission']['admitted']=True;report['rows']=[]
        self.assertFalse(benchmark.timing_eligible(report,14,1))


if __name__=='__main__': unittest.main()
