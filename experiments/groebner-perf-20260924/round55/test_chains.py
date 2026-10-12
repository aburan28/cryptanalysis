"""Independent ideal/completion checks, exact disabled traces and bounded probes."""
from concurrent.futures import ThreadPoolExecutor
import random
import sys
import unittest
from query import HERE,Query,anf_from_equations
sys.path.insert(0,str(HERE.parent/'round5'))
from algebraic_certificate import verify
sys.path.insert(0,str(HERE.parent.parent/'pdp-scaling'))
from boolean_basis import certify_boolean_basis

def trace(result):
    return {k:result.get(k) for k in ('status','reason','verified','basis','proof')}|{'counters':{k:v for k,v in result['producer_stats'].items() if not k.endswith('_seconds')}}
def accounting(result):
    s=result.get('chain_stats')
    if s is None: return
    assert s['probe_zero']+s['probe_nonzero']+s['probe_soft_limits']+s['probe_aborted']==s['probes']
    assert s['probe_work']+s['overhead_work']<=result['producer_stats']['work']
    assert s['pruned_pairs']+s['represented_pairs_skipped']<=s['candidate_pairs']
    assert s['represented_entries']<=65536 and s['failed_entries']<=65536
    if not s['mode']: assert all(v==0 for v in s.values())

class ChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queries={(mode,ubsan):Query(mode,ubsan) for mode in ('prior','disabled','probe','cached','tiny_probe','tiny_cache') for ubsan in (False,True)}
    def check(self,n,equations,**options):
        anf=anf_from_equations(equations);results={}
        for key,q in self.queries.items():
            result=q.compute(n,len(equations),anf,export_proof=True,**options)
            accounting(result)
            self.assertIn(result['status'],('gb','inconclusive'),(key,result))
            if result['verified']:
                self.assertTrue(verify(n,equations,result['basis'],result['proof'])['verified'],key)
                if n<=8: self.assertTrue(certify_boolean_basis(n,equations,result['basis'])['verified'],key)
            results[key]=result
        self.assertEqual(trace(results['prior',False]),trace(results['disabled',False]))
        for mode in ('prior','disabled','probe','cached','tiny_probe','tiny_cache'):
            self.assertEqual(trace(results[mode,False]),trace(results[mode,True]),mode)
            self.assertEqual(results[mode,False].get('chain_stats'),results[mode,True].get('chain_stats'),mode)
        verified=[r['basis'] for r in results.values() if r['verified']]
        if verified: self.assertTrue(all(g==verified[0] for g in verified))
        return results
    def test_random_independent_ideals_and_disabled_traces(self):
        rng=random.Random(202610035501)
        for n in range(1,8):
            for _ in range(8):
                equations=[[rng.randrange(1<<n) for _ in range(rng.randrange(1,9))] for _ in range(rng.randrange(1,n+2))]
                self.check(n,equations,max_work=2_000_000,max_nodes=100_000)
    def test_confirmed_chain_and_boolean_field_counterexample(self):
        rows=self.check(5,[[7],[25],[11]])
        self.assertGreater(rows['cached',False]['chain_stats']['pruned_pairs'],0)
        self.assertGreater(rows['probe',False]['chain_stats']['field_pairs'],0)
        rows=self.check(5,[[7,0],[25,0],[11,0]])
        self.assertTrue(rows['probe',False]['verified'])
        rows=self.check(3,[[3,0]])
        self.assertEqual(rows['probe',False]['basis'],[[0,1],[0,2]])
        self.assertGreater(rows['probe',False]['chain_stats']['field_pairs'],0)
    def test_zero_unit_wide_masks_and_cancellation(self):
        for n in (3,21,32,63,64):
            high=1<<(n-1)
            for equations in ([],[[]],[[0]],[[3,0]],[[3,3,1,0],[1,0]],[[high|1,high,1,0],[high,0]]):
                self.check(n,equations)
    def test_work_node_row_budgets_and_reuse(self):
        equations=[[7,0],[25,0],[11,0],[3,4,8]]
        for work in range(513):
            rows=self.check(5,equations,max_work=work)
            self.assertTrue(all(r['producer_stats']['work']<=work for r in rows.values()))
        for nodes in (1,2,5,10,30): self.check(5,equations,max_nodes=nodes)
        for rows in (1,2,3,8): self.check(5,equations,max_rows=rows,batch=1)
        for batch in (1,2,5,64): self.check(5,equations,batch=batch)
        self.assertTrue(self.check(5,equations)['probe',False]['verified'])
    def test_thread_local_stats_and_call_local_caches(self):
        def task(i):
            q=self.queries['probe',bool(i&1)];n=(5,21,32,64)[i%4]
            equations=[[7,0],[25,0],[11,0],[1<<(n-1),i&1]]
            anf=anf_from_equations(equations)
            first=q.compute(n,len(equations),anf,export_proof=True)
            q.compute(n,len(equations),anf,max_work=0)
            second=q.compute(n,len(equations),anf,export_proof=True)
            self.assertEqual(trace(first),trace(second))
            self.assertEqual(first['chain_stats'],second['chain_stats'])
            self.assertTrue(first['verified'])
            accounting(first)
        with ThreadPoolExecutor(max_workers=4) as pool: list(pool.map(task,range(32)))

if __name__=='__main__': unittest.main()
