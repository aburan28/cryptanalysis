import concurrent.futures
import ctypes as C
import itertools
import random
import sys
import unittest
from query import HERE,Query,DenseInput,abi,LayoutStats,MatrixStats
sys.path.insert(0,str(HERE.parent.parent/'pdp-scaling'))
from boolean_basis import certify_boolean_basis

def canonical(basis): return sorted(tuple(sorted(row)) for row in basis)
def stats(result):
    return [{k:v for k,v in a['stats'].items() if not k.endswith('seconds')} for a in result['attempts']]

class MatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.queries=[Query(),Query(sanitizer=True)]

    def checked(self,n,rows,result):
        self.assertTrue(result['verified'],result)
        cert=abi.python_verify(n,rows,result['basis'],result['proof'],max_work=100_000_000,max_retained_terms=10_000_000)
        self.assertTrue(cert['verified'],cert)
        if n<=8: self.assertTrue(certify_boolean_basis(n,rows,result['basis'])['verified'])

    def test_ring_only_layout_and_bounds(self):
        for q in self.queries:
            for n in range(1,9):
                for d in range(min(n,3)+1):
                    with q.layout(n,3,d,1) as l:
                        expected=tuple(m for m in range(1<<n) if m.bit_count()<=d)
                        self.assertEqual(l.support,expected)
                        columns=sum(m.bit_count()<=min(n,d+1) for m in range(1<<n))
                        self.assertEqual(l.stats['columns'],columns)
                        self.assertEqual(l.stats['multipliers'],n+1)
                        self.assertEqual(l.stats['payload_bytes'],8*(len(expected)+columns+n+1)+4*len(expected)*(n+1))
                    with q.layout(n,3,d,1,max_bytes=l.stats['payload_bytes']-1) as bad:
                        self.assertEqual(bad.stats['status'],2)
            for shape in ((0,1,0,0),(64,4096,64,64),(64,1,4,0)):
                with q.layout(*shape) as bad:
                    self.assertIn(bad.stats['status'],(1,2))

    def test_full_multiplier_span_random_ideals(self):
        rng=random.Random(920006)
        for n in range(1,7):
            for _ in range(8):
                rows=[[rng.randrange(1<<n) for _ in range(rng.randrange(7))] for _ in range(rng.randrange(n+2))]
                d=max((m.bit_count() for row in rows for m in row),default=0)
                for q in self.queries:
                    with q.layout(n,len(rows),d,n) as l:
                        original=DenseInput(n,rows,l.support)
                        result=q.compute(original,layout=l,fallback=False,max_work=20_000_000,matrix_cap=20_000_000,export_proof=True)
                        self.checked(n,rows,result)
                        self.assertEqual(len(result['attempts']),1)

    def test_nonlinear_coefficient_changes_through_64_variables(self):
        for q in self.queries:
            for n in (2,6,12,21):
                with q.layout(n,(n+1)//2,2,1) as l:
                    for constant in (0,1,0,1):
                        rows=[[3<<i]+([0] if constant else []) for i in range(0,n-1,2)]
                        if n%2: rows.append([1<<(n-1)]+([0] if constant else []))
                        result=q.compute(DenseInput(n,rows,l.support),layout=l,fallback=False,export_proof=True)
                        self.checked(n,rows,result)
            for n in (32,64):
                with q.layout(n,2,1,0) as l:
                    rows=[[1<<(n-1),1],[1,0]]
                    result=q.compute(DenseInput(n,rows,l.support),layout=l,fallback=False,export_proof=True)
                    self.checked(n,rows,result)

    def test_incomplete_field_completion_and_fallback(self):
        for q in self.queries:
            with q.layout(2,1,2,0) as l:
                original=DenseInput(2,[[3,0]],l.support)
                failed=q.compute(original,layout=l,fallback=False)
                self.assertFalse(failed['verified'])
                self.assertIn('field pair',failed['attempts'][0]['certificate']['reason'])
                result=q.compute(original,layout=l,export_proof=True)
                self.checked(2,[[3,0]],result)
                self.assertEqual([a['kind'] for a in result['attempts']],['macaulay','fresh-f4'])

    def test_fresh_and_reused_layout_exact_trace(self):
        for q in self.queries:
            with q.layout(5,3,2,2) as l:
                for rows in ([[3,0],[12],[16,1]],[[3],[12,0],[16,1,0]],[[3,0],[12],[16,1]]):
                    original=DenseInput(5,rows,l.support)
                    a=q.compute(original,layout=l,export_proof=True)
                    b=q.compute(original,fresh_shape=l.shape,export_proof=True)
                    self.assertEqual(a['verified'],b['verified'])
                    self.assertEqual(a.get('basis'),b.get('basis'))
                    self.assertEqual(a.get('proof'),b.get('proof'))
                    self.assertEqual(stats(a),stats(b))

    def test_every_small_work_and_checker_limit(self):
        for q in self.queries:
            with q.layout(2,1,2,1) as l:
                original=DenseInput(2,[[3,0]],l.support)
                full=q.compute(original,layout=l,export_proof=True)
                self.checked(2,[[3,0]],full)
                for kind,maximum in [('max_work',full['work']),('max_check_work',full['check_work'])]:
                    for limit in range(maximum+2):
                        result=q.compute(original,layout=l,export_proof=True,**{kind:limit})
                        self.assertLessEqual(result['work' if kind=='max_work' else 'check_work'],limit)
                        if result['verified']: self.checked(2,[[3,0]],result)
                for cap in (0,1,2,4,8):
                    result=q.compute(original,layout=l,matrix_cap=cap,export_proof=True)
                    self.assertLessEqual(result['attempts'][0]['stats']['work'],cap)
                    if result['verified']: self.checked(2,[[3,0]],result)
                for nodes in (1,2,3,4,5):
                    result=q.compute(original,layout=l,max_nodes=nodes,fallback=False)
                    if not result['verified']: self.assertEqual(result['attempts'][0]['stats']['status'],2)
                self.assertEqual(q.compute(original,layout=l,max_rows=1,batch=1,fallback=False)['status'],'inconclusive')
                self.checked(2,[[3,0]],q.compute(original,layout=l,max_work=(1<<64)-1,matrix_cap=(1<<64)-1,max_check_work=(1<<64)-1,export_proof=True))

    def test_equation_limbs_zero_and_unit(self):
        for q in self.queries:
            for rows in ([],[[]],[[0]],[[1]]*65,[[2,0]]*128,[[1,1],[2]]*65):
                with q.layout(2,len(rows),1,0) as l:
                    self.checked(2,rows,q.compute(DenseInput(2,rows,l.support),layout=l,fallback=False,export_proof=True))

    def test_malformed_then_fresh_and_result_lifetime(self):
        for q in self.queries:
            with q.layout(2,1,1,0) as l:
                for mask,bits in ((99,1),(0,2)):
                    original=DenseInput(2,[[1]],l.support)
                    original.masks[0]=mask;original.coefficients[0]=bits
                    result=q.compute(original,layout=l,fallback=False)
                    self.assertEqual(result['status'],'invalid-input')
                    self.checked(2,[[1]],q.compute(DenseInput(2,[[1]],l.support),layout=l,export_proof=True))
                original=DenseInput(2,[[1]],l.support)
                st=MatrixStats()
                handle=q.lib.macaulay_apply(l._handle,C.byref(original.view),10000,1000,1000,C.byref(st))
                self.assertTrue(handle)
                l.close()
                try: self.assertTrue(q.base._check(original.view,q.lib.macaulay_view(handle).contents,10000,10000)['verified'])
                finally: q.lib.macaulay_result_destroy(handle)
                with self.assertRaises(RuntimeError): q.compute(original,layout=l)
            st=LayoutStats()
            self.assertFalse(q.lib.macaulay_layout_create(65,1,1,0,1000,C.byref(st)))
            self.assertEqual(st.status,1)
            ms=MatrixStats()
            self.assertFalse(q.lib.macaulay_apply(None,None,100,100,100,C.byref(ms)))
            self.assertEqual(ms.status,1)

    def test_concurrent_numeric_calls(self):
        for q in self.queries:
            with q.layout(4,2,2,1) as l:
                def run(seed):
                    rows=[[3]+([0] if seed&1 else []),[12]+([0] if seed&2 else [])]
                    result=q.compute(DenseInput(4,rows,l.support),layout=l,export_proof=True)
                    self.checked(4,rows,result)
                    return result['verified']
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    self.assertTrue(all(pool.map(run,range(24))))

if __name__=='__main__': unittest.main(verbosity=2)
