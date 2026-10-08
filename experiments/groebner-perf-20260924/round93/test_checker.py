import concurrent.futures
import ctypes as C
import json
import unittest
from query import HERE,Query,DenseInput,MatrixStats,abi

def logical(result):
    return {k:({n:v for n,v in value.items() if not n.endswith('seconds')} if k=='stats' else value)
        for k,value in result.items() if k!='schedule'}

def proof(n,nodes,outputs):
    return dict(version=1,nvars=n,order='grevlex-x0-first',nodes=nodes,outputs=outputs)

class CheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.variants=[[Query(sanitizer=s,checker_order=o) for o in ('legacy','proof-first','completion-first')] for s in (False,True)]

    def check(self,q,n,rows,basis,p,**kw):
        return q.base.verify(n,len(rows),abi.anf_from_equations(rows),basis,p,**kw)

    def test_legacy_order_exact_valid_and_invalid_controls(self):
        cases=[(2,[[1]],[[1]],proof(2,[['input',0]],[0])),
               (2,[[3,0]],[[3,0]],proof(2,[['input',0]],[0])),
               (2,[[1],[2]],[[1]],proof(2,[['input',0]],[0])),
               (2,[[1],[2]],[[1],[2],[1,2]],proof(2,[['input',0],['input',1],['xor',0,1]],[0,1,2])),
               (2,[],[],proof(2,[],[]))]
        for variants in self.variants:
            for case in cases:
                a,b,c=[self.check(q,*case) for q in variants]
                self.assertEqual(logical(a),logical(b))
                self.assertEqual(a['verified'],c['verified'])
                if a['verified']:self.assertEqual(logical(a),logical(c))
                for limit in range(0,min(a['stats']['work']+2,350)):
                    aa,bb=[self.check(q,*case,max_work=limit) for q in variants[:2]]
                    self.assertEqual(logical(aa),logical(bb))
                    cc=self.check(variants[2],*case,max_work=limit)
                    self.assertLessEqual(cc['stats']['work'],limit)
                    if cc['verified']: self.assertTrue(a['verified'])

    def test_success_budget_boundary_and_wide_rings(self):
        for variants in self.variants:
            for n in (2,21,32,64):
                rows=[[1<<(n-1),1],[1,0]]
                anf=abi.anf_from_equations(rows)
                solved=variants[0].base.compute(n,2,anf,export_proof=True)
                self.assertTrue(solved['verified'])
                case=(n,rows,solved['basis'],solved['proof'])
                records=[self.check(q,*case) for q in variants]
                self.assertTrue(all(r['verified'] for r in records))
                self.assertTrue(all(logical(r)==logical(records[0]) for r in records))
                full=records[0]['stats']
                for q in variants:
                    for delta in (-1,0,1):
                        r=self.check(q,*case,max_work=full['work']+delta)
                        self.assertEqual(r['verified'],delta>=0)
                        r=self.check(q,*case,max_retained_terms=full['retained_terms']+delta)
                        self.assertEqual(r['verified'],delta>=0)

    def test_bad_derivations_after_all_other_checks_pass(self):
        valid=proof(2,[['input',0]],[0])
        bad=[proof(2,[['input',1]],[0]),proof(2,[['xor',0,0]],[0]),proof(2,[['mul',0,1]],[0]),
             proof(2,[['input',0],['xor',0,0]],[1]),proof(2,[['input',0]],[1])]
        for variants in self.variants:
            for q in variants:
                for p in bad:
                    r=self.check(q,2,[[1]],[[1]],p)
                    self.assertFalse(r['verified'],r)
                    self.assertEqual(r['status'],'rejected')
                    self.assertTrue(self.check(q,2,[[1]],[[1]],valid)['verified'])
                # Direct ABI corruptions bypass the strict Python proof constructor.
                for kind in ('op','input-extra','mask','output','version','reserved','order','offset','null-graph','null-output'):
                    original=abi.InputOwner(2,1,{1:1});owner=abi.ProofOwner(2,[[1]],valid)
                    if kind=='op':owner.nodes[0].op=3
                    elif kind=='input-extra':owner.nodes[0].b=1
                    elif kind=='mask':owner.terms[0]=4
                    elif kind=='output':owner.outputs[0]=4
                    elif kind=='version':owner.view.version=2
                    elif kind=='reserved':owner.view.reserved=1
                    elif kind=='order':owner.view.order=2
                    elif kind=='offset':owner.offsets[1]=2
                    elif kind=='null-graph':owner.view.graph=C.POINTER(abi.Node)()
                    elif kind=='null-output':owner.view.outputs=abi.P32()
                    r=q.base._check(original.view,owner.view,10000,10000)
                    self.assertEqual(r['status'],'rejected',(kind,r))

    def test_early_field_reverse_and_minimality_rejections(self):
        cases=[(2,[[3,0]],[[3,0]],proof(2,[['input',0]],[0]),'field pair'),
               (2,[[1],[2]],[[1]],proof(2,[['input',0]],[0]),'input generator'),
               (2,[[1],[2]],[[1],[2],[1,2]],proof(2,[['input',0],['input',1],['xor',0,1]],[0,1,2]),'reduced/minimal')]
        for variants in self.variants:
            for *case,reason in cases:
                r=self.check(variants[2],*case)
                self.assertEqual(r['status'],'rejected')
                self.assertIn(reason,r['reason'])
                self.assertEqual(r['stats']['proof_nodes'],0)
                self.assertEqual(r['stats']['retained_terms'],0)
                self.assertEqual(r['stats']['derivation_seconds'],0)
                self.assertGreater(self.check(variants[0],*case)['stats']['proof_nodes'],0)

    def test_frozen_dense_candidates_reject_without_derivation(self):
        from boolean_basis import certify_boolean_basis
        plan=json.loads((HERE/'panel.json').read_text())
        for variants in self.variants:
            legacy,_,ordered=variants
            for family in plan['families']:
                if family['name'] not in ('planted-dense-mq-12','planted-dense-mq-16'):continue
                n=family['nvars']
                with legacy.layout(n,len(family['training']),family['degree_bound'],1) as layout:
                    for rows in family['targets']:
                        original=DenseInput(n,rows,layout.support);stats=MatrixStats()
                        handle=legacy.lib.macaulay_apply(layout._handle,C.byref(original.view),1_000_000,1_000_000,10000,C.byref(stats))
                        self.assertTrue(handle)
                        try:
                            view=legacy.lib.macaulay_view(handle).contents
                            result=ordered.base._check(original.view,view,20_000_000,2_000_000)
                            self.assertEqual(result['status'],'rejected',result)
                            self.assertEqual(result['stats']['proof_nodes'],0)
                            self.assertEqual(result['stats']['retained_terms'],0)
                            basis,_=abi.export(view)
                            oracle=certify_boolean_basis(n,rows,basis,monomial_cache=n<=12)
                            self.assertFalse(oracle['verified'],oracle)
                        finally:legacy.lib.macaulay_result_destroy(handle)

    def test_schedule_validation_and_thread_local_errors(self):
        with self.assertRaises(ValueError):Query(checker_order='unknown')
        for variants in self.variants:
            q=variants[2];original=abi.InputOwner(2,1,{1:1});owner=abi.ProofOwner(2,[[1]],proof(2,[['input',0]],[0]))
            st=abi.CheckStats()
            self.assertEqual(q.ordered.check_packed_ordered(C.byref(original.view),C.byref(owner.view),100,100,2,C.byref(st)),1)
            self.assertEqual(st.work,0)
            self.assertEqual(q.ordered.check_packed_ordered(None,None,100,100,1,C.byref(st)),1)
            self.assertEqual(q.ordered.check_packed_ordered(None,None,100,100,1,None),1)
            def run(i):
                p=proof(2,[['input',0]],[0 if i%2 else 1])
                r=self.check(q,2,[[1]],[[1]],p)
                self.assertEqual(r['verified'],bool(i%2))
                if not r['verified']:self.assertIn('witnessed input combination',r['reason'])
                return True
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                self.assertTrue(all(pool.map(run,range(48))))

if __name__=='__main__':unittest.main(verbosity=2)
