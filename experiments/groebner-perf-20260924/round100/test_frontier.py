"""Checker equivalence, fresh coefficients, proof storage and process deadlines."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from audit import sorting,trace,proof_bytes
from common import Context,HERE
from query import Query,ARMS
from panel import run_command
from worker import run

class FrontierTests(unittest.TestCase):
    def test_native_controls(self):
        for suffix in ('','-ubsan'):subprocess.run([str(HERE/'build'/('radix_controls'+suffix+'.exe'))],check=True)

    def test_live_checker_matches_legacy(self):
        for sanitized in (False,True):
            for arm in ARMS:
                results=[]
                for checker in ('legacy','release-live'):
                    q=Query(sanitizer=sanitized,arm=arm,checker=checker)
                    with q.workspace(3,3,[0,1,2,3,4]).borrow_mapping({0:3,1:1,2:2,3:4,4:4}) as original:
                        r=q.compute(original,export_proof=True)
                    self.assertTrue(r['verified']);results.append((r['basis'],r['proof'],r['work']))
                self.assertEqual(*results)

    def test_budget_boundaries(self):
        for sanitized in (False,True):
            queries={a:Query(sanitizer=sanitized,arm=a) for a in ARMS}
            for budget in (0,1,2,8,64,512,2048,100000):
                values=[]
                for arm,q in queries.items():
                    with q.workspace(3,3,[0,1,2,3,4]).borrow_mapping({0:3,1:1,2:2,3:4,4:4}) as original:
                        r=q.compute(original,export_proof=True,max_work=budget)
                    if arm!='baseline':sorting.sorting_check(r,arm)
                    values.append(trace(r))
                self.assertTrue(all(v==values[0] for v in values))

    def test_changed_target_and_radix(self):
        for sanitized in (False,True):
            ctx=Context(sanitizer=sanitized);before=None
            for name in ('pdp-6-seed-1','pdp-6-seed-3','pdp-12-seed-1','pdp-6-seed-1'):
                values={a:ctx.run(name,a,limits={'max_work':20000000})['result'] for a in ARMS}
                self.assertTrue(all(trace(r)==trace(values['baseline']) for r in values.values()))
                for arm in ('keys','radix'):sorting.sorting_check(values[arm],arm)
                if name=='pdp-12-seed-1':self.assertGreater(values['radix']['monomial_radix']['radix_calls'],0)
                else:self.assertTrue(values['radix']['reference_equations_and_curve_replay'])
                if name=='pdp-6-seed-1':
                    if before is not None:self.assertEqual(before,trace(values['radix']))
                    before=trace(values['radix'])

    def test_concurrent_reset(self):
        for sanitized in (False,True):
            q=Query(sanitizer=sanitized,arm='radix')
            def call(i):
                with q.workspace(3,3,[0,1,2,3,4]).borrow_mapping({0:i%4,1:1,2:2,3:4,4:4}) as original:
                    r=q.compute(original,export_proof=True)
                sorting.sorting_check(r,'radix');return trace(r),r['monomial_radix']
            expected=[call(i) for i in range(24)]
            with ThreadPoolExecutor(max_workers=4) as pool:actual=list(pool.map(call,range(24)))
            self.assertEqual(expected,actual)

    def test_proof_storage_after_complete_query(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'cells').mkdir()
            for i,arm in enumerate(('baseline','radix')):
                run('pdp-6-seed-1',arm,20000000,output=root/'cells'/f'{i}.json')
            rows=[json.loads((root/'cells'/f'{i}.json').read_text()) for i in range(2)]
            self.assertEqual(rows[0]['result']['proof_sha256'],rows[1]['result']['proof_sha256'])
            self.assertEqual(len(list((root/'proofs').glob('*.json'))),1)
            self.assertTrue(proof_bytes(root,rows[0]['result']['proof_sha256']))
            for row in rows:
                self.assertEqual(row['wall_ns'],sum(row['phases'].values()))
                self.assertTrue(row['result']['reference_equations_and_curve_replay'])

    def test_process_failures_and_deadline(self):
        with tempfile.TemporaryDirectory() as temp:
            log=Path(temp)/'worker.log'
            failed=run_command([sys.executable,'-c','raise SystemExit(7)'],log,5)
            self.assertEqual((failed['execution'],failed['exit_code']),('process-failure',7))
            timed=run_command([sys.executable,'-c','import time; time.sleep(60)'],log,.05)
            self.assertEqual(timed['execution'],'timeout');self.assertNotEqual(timed['exit_code'],0)
            self.assertGreaterEqual(timed['process_elapsed_ns'],50000000)
            self.assertLess(timed['process_elapsed_ns'],5000000000)

if __name__=='__main__':unittest.main()
