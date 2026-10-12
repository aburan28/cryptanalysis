"""Exact traces across sort policies, errors, fresh targets and concurrent calls."""
from concurrent.futures import ThreadPoolExecutor
import subprocess
import unittest
from audit import sorting_check
from common import Context,HERE
from query import Query,ARMS

def trace(value):
    if isinstance(value,dict):return {k:trace(v) for k,v in value.items() if not k.endswith('seconds') and k not in ('monomial_sort_policy','monomial_order','monomial_radix')}
    if isinstance(value,list):return [trace(x) for x in value]
    return value

def check_stats(result,arm):
    sorting_check(result,arm)

class RadixTests(unittest.TestCase):
    def test_native_controls(self):
        for suffix in ('','-ubsan'):subprocess.run([str(HERE/'build'/('radix_controls'+suffix+'.exe'))],check=True)

    def test_budget_boundaries(self):
        for sanitized in (False,True):
            queries={arm:Query(sanitizer=sanitized,arm=arm) for arm in ARMS}
            for budget in (0,1,2,4,8,16,32,64,128,512,2048,100000):
                results=[]
                for arm,q in queries.items():
                    with q.workspace(3,3,[0,1,2,3,4,5,6,7]).borrow_mapping({0:3,1:1,2:2,3:4,4:4}) as original:
                        result=q.compute(original,max_work=budget,export_proof=True)
                    if arm!='baseline':check_stats(result,arm)
                    results.append(trace(result))
                self.assertTrue(all(r==results[0] for r in results))

    def test_other_limits(self):
        for sanitized in (False,True):
            queries={arm:Query(sanitizer=sanitized,arm=arm) for arm in ARMS}
            for limits in ({'max_nodes':1},{'max_nodes':4},{'max_rows':1,'batch':1},{'max_check_work':0},{'max_terms':0}):
                results=[]
                for arm,q in queries.items():
                    with q.workspace(3,3,[0,1,2,3,4]).borrow_mapping({0:3,1:1,2:2,3:4,4:4}) as original:
                        result=q.compute(original,export_proof=True,**limits)
                    if arm!='baseline':check_stats(result,arm)
                    results.append(trace(result))
                self.assertTrue(all(r==results[0] for r in results))

    def test_wide_masks_through_public_api(self):
        for sanitized in (False,True):
            queries={arm:Query(sanitizer=sanitized,arm=arm) for arm in ARMS}
            for bit in (56,57,63):
                high=1<<bit
                coefficients={0:1,1:2,2:4,high:3,high|1:4}
                results={}
                for arm,q in queries.items():
                    with q.workspace(bit+1,3,list(coefficients)).borrow_mapping(coefficients) as original:
                        result=q.compute(original,export_proof=True)
                    self.assertTrue(result['verified'])
                    if arm!='baseline':check_stats(result,arm)
                    results[arm]=result
                self.assertTrue(all(trace(r)==trace(results['baseline']) for r in results.values()))
                if bit>=57:self.assertGreater(results['keys']['monomial_order']['wide_calls'],0)
                else:self.assertEqual(results['keys']['monomial_order']['wide_calls'],0)

    def test_complete_changed_targets(self):
        for sanitized in (False,True):
            ctx=Context(sanitizer=sanitized);old=None
            for name in ('pdp-6-seed-1','pdp-6-seed-3','pdp-6-seed-1'):
                results={a:ctx.run(name,a)['result'] for a in ARMS}
                self.assertTrue(all(trace(r)==trace(results['baseline']) for r in results.values()))
                for arm,result in results.items():
                    self.assertTrue(result['reference_equations_and_curve_replay'])
                    if arm!='baseline':check_stats(result,arm)
                if name=='pdp-6-seed-1':
                    if old is not None:self.assertEqual(old,results['keys']['monomial_order'])
                    old=results['keys']['monomial_order']
                self.assertGreater(results['keys']['monomial_order']['key_calls'],0)

    def test_radix_then_changed_target(self):
        for sanitized in (False,True):
            ctx=Context(sanitizer=sanitized)
            before=ctx.run('pdp-6-seed-1','radix')['result']
            large={a:ctx.run('pdp-12-seed-1',a)['result'] for a in ARMS}
            self.assertTrue(all(trace(r)==trace(large['baseline']) for r in large.values()))
            self.assertGreater(large['radix']['monomial_radix']['radix_calls'],0)
            self.assertGreater(large['tiny']['monomial_radix']['cap_fallbacks'],0)
            for arm in ('radix','tiny'):check_stats(large[arm],arm)
            after=ctx.run('pdp-6-seed-1','radix')['result']
            self.assertEqual(before['monomial_radix'],after['monomial_radix'])
            self.assertEqual(trace(before),trace(after))

    def test_concurrent_state(self):
        for sanitized in (False,True):
            q=Query(sanitizer=sanitized,arm='radix')
            def run(i):
                with q.workspace(3,3,[0,1,2,3,4]).borrow_mapping({0:i%4,1:1,2:2,3:4,4:4}) as original:
                    result=q.compute(original,export_proof=True)
                check_stats(result,'radix');return trace(result),result['monomial_radix']
            expected=[run(i) for i in range(24)]
            with ThreadPoolExecutor(max_workers=4) as pool:actual=list(pool.map(run,range(24)))
            self.assertEqual(actual,expected)

if __name__=='__main__':unittest.main()
