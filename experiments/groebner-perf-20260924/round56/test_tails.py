"""Check exact ideals and completion, including unreduced Boolean tails."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import random
import sys
import unittest
from query import HERE,Query,VARIANTS,anf_from_equations
sys.path.insert(0,str(HERE.parent/'round5'))
from algebraic_certificate import verify
sys.path.insert(0,str(HERE.parent.parent/'pdp-scaling'))
from boolean_basis import certify_boolean_basis

def trace(result):
    return {k:result.get(k) for k in ('status','reason','verified','basis','proof')}|{'counters':{k:v for k,v in result['producer_stats'].items() if not k.endswith('_seconds')}}

class TailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queries={(mode,ubsan):Query(mode,ubsan) for mode in VARIANTS for ubsan in (False,True)}
        spec=importlib.util.spec_from_file_location('previous_chain_query',HERE.parent/'round55/query.py')
        cls.previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.previous)
    def check(self,n,equations,**options):
        anf=anf_from_equations(equations);results={}
        for key,q in self.queries.items():
            result=q.compute(n,len(equations),anf,export_proof=True,**options)
            self.assertIn(result['status'],('gb','inconclusive'),(key,result))
            if result['verified']:
                self.assertTrue(verify(n,equations,result['basis'],result['proof'])['verified'],key)
                if n<=8: self.assertTrue(certify_boolean_basis(n,equations,result['basis'])['verified'],key)
            results[key]=result
        for mode in VARIANTS:
            self.assertEqual(trace(results[mode,False]),trace(results[mode,True]),mode)
            self.assertEqual(results[mode,False]['top_stats'],results[mode,True]['top_stats'],mode)
        solved=[r['basis'] for r in results.values() if r['verified']]
        if solved: self.assertTrue(all(g==solved[0] for g in solved))
        return results
    def test_random_independent_ideals(self):
        rng=random.Random(202610035601)
        for n in range(1,9):
            for _ in range(16):
                equations=[[rng.randrange(1<<n) for _ in range(rng.randrange(1,11))] for _ in range(rng.randrange(1,n+2))]
                self.check(n,equations,max_work=2_000_000,max_nodes=100_000)
    def test_unchanged_baselines(self):
        for mode,old in (('prior','prior'),('chain','probe')):
            for n,equations in ((5,[[7],[25],[11]]),(5,[[7,0],[25,0],[11,0]]),(5,[[3,0],[6,0]])):
                for work in (0,100,2_000_000):
                    args=(n,len(equations),anf_from_equations(equations))
                    a=self.queries[mode,False].compute(*args,export_proof=True,max_work=work)
                    b=self.previous.Query(old).compute(*args,export_proof=True,max_work=work)
                    self.assertEqual(trace(a),trace(b))
                    self.assertTrue(all(v==0 for v in a['top_stats'].values()))
    def test_deferred_tails_field_pairs_and_wide_masks(self):
        for n in (3,21,32,63,64):
            high=1<<(n-1)
            for equations in ([],[[]],[[0]],[[3,0]],[[high,0],[1,high]],[[high|1,high,1,0],[high,0]],[[3,3,1,0],[1,0]]):
                self.check(n,equations)
        result=self.check(3,[[4,0],[1,4]])
        self.assertGreater(result['top_all',False]['top_stats']['deferred_terms'],0)
        result=self.check(3,[[3,0]])
        self.assertEqual(result['top_all',False]['basis'],[[0,1],[0,2]])
        self.assertGreater(result['filter',False]['top_stats']['skipped_reducer_pivots'],0)
    def test_budgets_and_fresh_reuse(self):
        equations=[[7,0],[25,0],[11,0],[3,4,8]]
        for work in range(513):
            rows=self.check(5,equations,max_work=work)
            self.assertTrue(all(r['producer_stats']['work']<=work for r in rows.values()))
        for nodes in (1,2,5,10,30): self.check(5,equations,max_nodes=nodes)
        for rows in (1,2,3,8): self.check(5,equations,max_rows=rows,batch=1)
        for batch in (1,2,5,64): self.check(5,equations,batch=batch)
        self.assertTrue(self.check(5,equations)['top_all',False]['verified'])
    def test_thread_local_fresh_calls(self):
        def task(i):
            q=self.queries['chain_top_all',bool(i&1)];n=(5,21,32,64)[i%4]
            equations=[[7,0],[25,0],[11,0],[1<<(n-1),i&1]]
            args=(n,len(equations),anf_from_equations(equations))
            first=q.compute(*args,export_proof=True)
            q.compute(*args,max_work=0)
            second=q.compute(*args,export_proof=True)
            self.assertEqual(trace(first),trace(second))
            self.assertEqual(first['top_stats'],second['top_stats'])
            self.assertTrue(first['verified'])
        with ThreadPoolExecutor(max_workers=4) as pool: list(pool.map(task,range(32)))

if __name__=='__main__': unittest.main()
