"""Differential proofs, truth sets, budget prefixes and bounded packed rows."""
from concurrent.futures import ThreadPoolExecutor
import random
import gzip
import json
import sys
import unittest
from query import HERE, Query, VARIANTS, anf_from_equations
sys.path.insert(0,str(HERE.parent/'round5'))
from algebraic_certificate import verify
sys.path.insert(0,str(HERE.parent.parent/'pdp-scaling'))
from boolean_basis import certify_boolean_basis

def trace(result):
    value={key:result.get(key) for key in ('status','reason','verified','basis','proof','top_stats','column_stats')}
    value['producer_stats']={k:v for k,v in result['producer_stats'].items() if not k.endswith('_seconds')}
    if 'certificate' in result:
        certificate=result['certificate']
        value['certificate']={k:v for k,v in certificate.items() if k!='stats'}
        value['certificate']['stats']={k:v for k,v in certificate['stats'].items() if not k.endswith('_seconds')}
    return value

class PackedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queries={(v,s):Query(s,variant=v) for v in VARIANTS for s in (False,True)}
    def check(self,n,equations,**limits):
        anf=anf_from_equations(equations)
        answers={key:q.compute(n,len(equations),anf,export_proof=True,**limits) for key,q in self.queries.items()}
        baseline=answers['baseline',False]
        self.assertIn(baseline['status'],('gb','inconclusive'))
        for key,result in answers.items():
            self.assertEqual(trace(result),trace(baseline),key)
        for v in VARIANTS:
            self.assertEqual(answers[v,False]['packed_stats'],answers[v,True]['packed_stats'])
        if baseline['verified']:
            self.assertTrue(verify(n,equations,baseline['basis'],baseline['proof'])['verified'])
            if n<=8:self.assertTrue(certify_boolean_basis(n,equations,baseline['basis'])['verified'])
        return answers
    def test_random_ideals(self):
        rng=random.Random(202610036201)
        for n in range(1,9):
            for _ in range(16):
                equations=[[rng.randrange(1<<n) for _ in range(rng.randrange(1,11))]
                           for _ in range(rng.randrange(1,n+2))]
                self.check(n,equations,max_work=2_000_000,max_nodes=100_000)
    def test_boolean_collisions_empty_units_and_wide_masks(self):
        for n in (3,21,32,63,64):
            high=1<<(n-1)
            for equations in ([],[[]],[[0]],[[3,0]],[[high,0],[1,high]],
                              [[high|1,high,1,0],[high,0]],[[3,3,1,0],[1,0]]):
                self.check(n,equations)
    def test_budget_prefixes(self):
        equations=[[7,0],[25,0],[11,0],[3,4,8]]
        for work in range(513):
            rows=self.check(5,equations,max_work=work)
            self.assertTrue(all(r['producer_stats']['work']<=work for r in rows.values()))
        for nodes in (1,2,5,10,30):self.check(5,equations,max_nodes=nodes)
        for rows in (1,2,3,8):self.check(5,equations,max_rows=rows,batch=1)
        for batch in (1,2,5,64):self.check(5,equations,batch=batch)
    def test_packed_and_bounded_fallback(self):
        cases=json.loads(gzip.decompress((HERE.parent/'round13/results/confirmation.json.gz').read_bytes()))['inputs']
        case=next(c for c in cases if c['name']=='random-8-budget-control')
        answers=self.check(case['nvars'],case['equations'])
        stats={v:answers[v,False]['packed_stats'] for v in VARIANTS}
        self.assertEqual(stats['baseline']['matrices'],0)
        self.assertGreater(stats['packed']['matrices'],0)
        self.assertGreater(stats['packed']['xors'],0)
        self.assertGreater(stats['packed']['peak_width'],1)
        self.assertGreater(stats['tiny']['fallback_matrices'],0)
        self.assertLessEqual(stats['packed']['peak_payload_words'],8388608)
        self.assertLessEqual(stats['tiny']['peak_payload_words'],4)
        answers=self.check(3,[[3,0]])
        self.assertGreater(answers['tiny',False]['packed_stats']['matrices'],0)

    def test_late_work_and_proof_budget_prefixes(self):
        equations=[[7,0],[25,0],[11,0],[3,4,8]]
        baseline=self.check(5,equations)['baseline',False]
        work=baseline['producer_stats']['work']
        for limit in range(max(0,work-64),work+2):self.check(5,equations,max_work=limit)
        # Sweep all emitted-node cutoffs on this small matrix, including those
        # that interrupt an XOR after its numeric merge but before publication.
        nodes=baseline['producer_stats']['nodes']
        for limit in range(1,nodes+2):self.check(5,equations,max_nodes=limit)

    def test_leased_fresh_coefficients_and_many_equations(self):
        rng=random.Random(202610036203)
        q=self.queries['packed',False]
        for equations in (1,64,65,129):
            workspace=q.workspace(5,equations,list(range(32)))
            for _ in range(8):
                anf={m:rng.getrandbits(equations) for m in range(32) if rng.randrange(3)==0}
                baseline=self.queries['baseline',False].compute(5,equations,anf,export_proof=True)
                with workspace.borrow_mapping(anf) as packed:
                    result=q.compute(5,equations,packed,export_proof=True)
                self.assertEqual(trace(result),trace(baseline))
                with workspace.borrow_mapping({}) as packed:
                    self.assertTrue(q.compute(5,equations,packed)['verified'])

    def test_fresh_target_and_thread_reuse(self):
        def task(i):
            q=self.queries['packed',bool(i&1)];n=(5,21,32,64)[i%4]
            equations=[[7,0],[25,0],[11,0],[1<<(n-1),i&1]]
            args=(n,len(equations),anf_from_equations(equations))
            first=q.compute(*args,export_proof=True)
            failed=q.compute(*args,max_work=0)
            self.assertTrue(all(value==0 for value in failed['packed_stats'].values()))
            second=q.compute(*args,export_proof=True)
            self.assertEqual(trace(first),trace(second))
            self.assertEqual(first['packed_stats'],second['packed_stats'])
            self.assertTrue(first['verified'])
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(task,range(32)))

if __name__=='__main__':unittest.main()
