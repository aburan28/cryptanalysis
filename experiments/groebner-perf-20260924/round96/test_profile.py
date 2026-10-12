"""Instrumentation must preserve fresh solving, exact budgets and witnesses."""
from concurrent.futures import ThreadPoolExecutor
import subprocess
import unittest
from common import Context,HERE
from query import Query,STAGES

def trace(value):
    if isinstance(value,dict):return {k:trace(v) for k,v in value.items() if not k.endswith('seconds') and k not in ('profile','instrumented')}
    if isinstance(value,list):return [trace(x) for x in value]
    return value

def check_profile(result):
    p=result['profile']['work']
    assert set(p['exclusive'])==set(p['inclusive'])==set(p['calls'])==set(STAGES)
    assert sum(p['exclusive'].values())==result['work']
    assert p['overflow']==p['active']==p['depth']==0
    assert all(p['inclusive'][s]>=p['exclusive'][s] for s in STAGES if s!='decode')
    return p

class ProfileTests(unittest.TestCase):
    def test_generated_delta_is_only_instrumentation(self):
        original=(HERE/'build/engine.inc').read_text()
        profiled=(HERE/'build/profiled_engine.inc').read_text()
        restored=''.join(line for line in profiled.splitlines(keepends=True)
            if not line.strip().startswith(('#include "profile.h"','WorkScope ','profile_charge(')))
        self.assertEqual(restored,original)
        original=(HERE/'build/adapter.cpp').read_text()
        profiled=(HERE/'build/profiled_adapter.cpp').read_text()
        prefix=profiled.split('extern "C" uint64_t producer_top_stats_size()',1)[0]
        restored=prefix.replace('profiled_engine.inc','engine.inc').replace('work_profile={};','')
        self.assertEqual(restored.strip(),original.strip())

    def test_native_counter_controls(self):
        for suffix in ('','-ubsan'):
            subprocess.run([str(HERE/'build'/('profile_controls'+suffix+'.exe'))],check=True)

    def test_query_and_budget_trace(self):
        for sanitized in (False,True):
            queries={a:Query(sanitizer=sanitized,arm=a) for a in ('baseline','profiled')}
            for budget in (0,1,2,4,8,32,128,1024,100000):
                results=[]
                for arm,q in queries.items():
                    with q.workspace(3,3,[0,1,2,3,4,5,6,7]).borrow_mapping({0:3,1:1,2:2,3:4,4:4}) as original:
                        result=q.compute(original,max_work=budget,export_proof=True)
                    if arm=='profiled':check_profile(result)
                    results.append(trace(result))
                self.assertEqual(*results)

    def test_node_and_row_exhaustion(self):
        for sanitized in (False,True):
            queries=[Query(sanitizer=sanitized,arm=a) for a in ('baseline','profiled')]
            for limits in ({'max_nodes':1},{'max_rows':1,'batch':1},{'max_check_work':0},{'max_terms':0}):
                results=[]
                for i,q in enumerate(queries):
                    with q.workspace(3,3,[0,1,2,3,4]).borrow_mapping({0:3,1:1,2:2,3:4,4:4}) as original:
                        result=q.compute(original,export_proof=True,**limits)
                    if i:check_profile(result)
                    results.append(trace(result))
                self.assertEqual(*results)

    def test_fresh_complete_queries(self):
        for sanitized in (False,True):
            ctx=Context(sanitizer=sanitized)
            for name in ('pdp-6-seed-1','pdp-6-seed-3','pdp-6-seed-1'):
                a=ctx.run(name,'baseline')['result'];b=ctx.run(name,'profiled')['result']
                self.assertEqual(trace(a),trace(b));check_profile(b)
                self.assertTrue(b['reference_equations_and_curve_replay'])

    def test_thread_local_snapshots_and_reset(self):
        for sanitized in (False,True):
            q=Query(sanitizer=sanitized,arm='profiled')
            def run(i):
                coefficients={1:1,2:2,0:i%4}
                with q.workspace(2,2,[0,1,2]).borrow_mapping(coefficients) as original:
                    result=q.compute(original,export_proof=True)
                check_profile(result);return trace(result),result['profile']
            expected=[run(i) for i in range(12)]
            with ThreadPoolExecutor(max_workers=4) as pool:actual=list(pool.map(run,range(12)))
            self.assertEqual(actual,expected)

if __name__=='__main__':unittest.main()
