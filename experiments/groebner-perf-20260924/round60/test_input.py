"""Fresh coefficients, exact budget prefixes, and storage-lifetime boundaries."""
from concurrent.futures import ThreadPoolExecutor
import random
import threading
import unittest
from common import LegacyQuery,Query,fixtures,make_instance
from input_plan import PackedDescentPlan
from query import anf_from_equations

def trace(result):
    value={k:result.get(k) for k in ('status','reason','verified','basis','proof','top_stats','column_stats')}
    value['producer_stats']={k:v for k,v in result['producer_stats'].items() if not k.endswith('_seconds')}
    if 'certificate' in result:
        certificate=result['certificate'];value['certificate']={k:v for k,v in certificate.items() if k!='stats'}
        value['certificate']['stats']={k:v for k,v in certificate['stats'].items() if not k.endswith('_seconds')}
    return value

class InputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queries={u:Query(u) for u in (False,True)}
        cls.legacy={u:LegacyQuery('indexed',u) for u in (False,True)}
    def compare(self,n,equations,anf,**limits):
        answers=[]
        for sanitizer,q in self.queries.items():
            expected=self.legacy[sanitizer].compute(n,equations,anf,export_proof=True,**limits)
            workspace=q.workspace(n,equations,list(anf))
            addresses=workspace.buffer_addresses
            with workspace.borrow_mapping(anf) as packed:
                self.assertTrue(packed.matches_mapping(anf))
                actual=q.compute(n,equations,packed,export_proof=True,**limits)
            self.assertEqual(trace(actual),trace(expected))
            self.assertEqual(addresses,workspace.buffer_addresses)
            self.assertEqual(workspace._view.terms,0)
            answers.append(actual)
        self.assertEqual(trace(answers[0]),trace(answers[1]))
    def test_random_and_multiword_coefficients(self):
        rng=random.Random(202610036003)
        for n in range(1,9):
            for _ in range(8):
                equations=rng.randrange(1,n+3)
                support=rng.sample(range(1<<n),min(12,1<<n))
                self.compare(n,equations,{m:rng.randrange(1<<equations) for m in support},max_work=2_000_000)
        for equations in (0,1,63,64,65,127,128,129,4096):
            anf={} if not equations else {0:0,1:1,2:1<<(equations-1),3:(1<<equations)-1}
            self.compare(64,equations,anf)
    def test_partial_budget_and_resource_prefixes(self):
        anf={7:1,25:2,11:1<<64,0:(1<<129)|1,3:0,4:1<<127}
        for budget in range(513):self.compare(5,130,anf,max_work=budget)
        for nodes in (1,2,5,20):self.compare(5,130,anf,max_nodes=nodes)
        for rows in (1,2,4):self.compare(5,130,anf,max_rows=rows,batch=1)
    def test_dense_compaction_reuses_arrays_across_targets(self):
        rng=random.Random(202610036004);support=list(range(16));rng.shuffle(support)
        for sanitizer,q in self.queries.items():
            workspace=q.workspace(4,65,support);addresses=workspace.buffer_addresses
            for iteration in range(32):
                values=[rng.getrandbits(65) if rng.randrange(3)==0 else 0 for _ in support]
                if iteration%5==0:values=[0]*len(support)
                anf={m:v for m,v in zip(support,values) if v}
                expected=self.legacy[sanitizer].compute(4,65,anf,export_proof=True)
                with workspace.borrow_dense(values) as packed:
                    self.assertEqual(list(packed.items()),list(anf.items()))
                    actual=q.compute(4,65,packed,export_proof=True)
                    self.assertEqual(trace(actual),trace(expected))
                self.assertEqual(addresses,workspace.buffer_addresses)
    def test_fresh_packed_descent_matches_reference_and_survives_failures(self):
        case=next(c for c in fixtures() if c['name']=='pdp-6-seed-1')
        original=make_instance(case['n'],case['m'],case['ell'],seed=case['seed'])
        for sanitizer,q in self.queries.items():
            plan=PackedDescentPlan(q,original.n,original.mod,original.b,original.m,original.l)
            addresses=plan.workspace.buffer_addresses
            for target in (0,1,original.xR,(1<<original.n)-1,0,original.xR):
                reference=plan.descend(target)
                expected=self.legacy[sanitizer].compute(original.nvars,original.n,reference,export_proof=True)
                with plan.borrow(target) as packed:
                    self.assertEqual(dict(packed.items()),reference)
                    actual=q.compute(original.nvars,original.n,packed,export_proof=True)
                    self.assertEqual(trace(actual),trace(expected))
            with self.assertRaises(ValueError):
                with plan.borrow(1<<original.n):pass
            with plan.borrow(original.xR) as packed:self.assertTrue(packed.matches_mapping(original.anf))
            self.assertEqual(addresses,plan.workspace.buffer_addresses)
    def test_stale_nested_wrong_ring_and_cross_thread_leases(self):
        q=self.queries[False];workspace=q.workspace(3,2,[1,2])
        with workspace.borrow_mapping({1:1,2:2}) as packed:
            iterator=packed.items();next(iterator)
            with self.assertRaises(RuntimeError):
                with workspace.borrow_mapping({}):pass
            with self.assertRaises(ValueError):q.compute(4,2,packed)
            with self.assertRaises(ValueError):q.compute(3,1,packed)
            with self.assertRaises(ValueError):self.queries[True].compute(3,2,packed)
            with ThreadPoolExecutor(max_workers=1) as pool:
                with self.assertRaises(RuntimeError):pool.submit(q.compute,3,2,packed).result(timeout=5)
        with self.assertRaises(RuntimeError):q.compute(3,2,packed)
        with self.assertRaises(RuntimeError):next(iterator)
        with workspace.borrow_mapping({1:1}) as fresh:self.assertTrue(q.compute(3,2,fresh)['verified'])
    def test_failed_fill_and_failed_native_call_do_not_expose_stale_tail(self):
        q=self.queries[False];workspace=q.workspace(3,2,[1,2,3])
        for mapping in ({1:1,2:4},{1:1,4:1},{1:1,2:-1},{1:1,2:True}):
            with self.assertRaises(ValueError):
                with workspace.borrow_mapping(mapping):pass
            self.assertEqual(workspace._view.terms,0)
        with workspace.borrow_mapping({1:1,2:2,3:3}) as packed:
            self.assertFalse(q.compute(3,2,packed,max_work=0)['verified'])
        with workspace.borrow_mapping({}) as packed:
            self.assertEqual(list(packed.items()),[])
            self.assertTrue(q.compute(3,2,packed)['verified'])
        with self.assertRaises(ValueError):q.workspace(3,2,[1,1])
        with self.assertRaises(ValueError):q.workspace(3,0,[1])
        with self.assertRaises(ValueError):q.workspace(3,2,[8])
    def test_shared_workspace_serializes_fresh_inputs(self):
        q=self.queries[False];workspace=q.workspace(4,2,[0,1,2,3])
        def task(index):
            anf={1:1,2:2,0:index%4}
            expected=q.compute(4,2,anf,export_proof=True)
            with workspace.borrow_mapping(anf) as packed:
                actual=q.compute(4,2,packed,export_proof=True)
                self.assertEqual(trace(actual),trace(expected))
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(task,range(32)))

if __name__=='__main__':unittest.main()
