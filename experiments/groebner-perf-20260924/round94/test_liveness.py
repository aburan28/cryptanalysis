import concurrent.futures
import ctypes as C
import random
import unittest
from query import Query,abi,LiveStats

POLICIES=('baseline','keep','release-cumulative','release-live')
def certificate(n,nodes,outputs):return dict(version=1,nvars=n,order='grevlex-x0-first',nodes=nodes,outputs=outputs)
def clean(result):
    return {k:({n:v for n,v in value.items() if not n.endswith('seconds')} if k=='stats' else value)
        for k,value in result.items() if k not in ('schedule','retention_policy','liveness')}

def expected_liveness(rows,nodes,outputs):
    # Independent set-based lifetime simulation over the public DAG encoding.
    uses=[0]*len(nodes)
    for node in nodes:
        if node[0]=='mul':uses[node[1]]+=1
        if node[0]=='xor':uses[node[1]]+=1;uses[node[2]]+=1
    for i in outputs:uses[i]+=1
    values={};live=peak=total=released=freed=0
    def canonical(terms):
        result=set()
        for term in terms:result.symmetric_difference_update([term])
        return result
    def release(i):
        nonlocal live,released,freed
        size=len(values.pop(i));live-=size;released+=size;freed+=1
    def consume(i):
        uses[i]-=1
        if not uses[i]:release(i)
    for i,node in enumerate(nodes):
        if node[0]=='input':value=canonical(rows[node[1]])
        elif node[0]=='mul':value=canonical(term|node[2] for term in values[node[1]])
        else:value=values[node[1]]^values[node[2]]
        values[i]=value;live+=len(value);total+=len(value);peak=max(peak,live)
        if node[0]=='mul':consume(node[1])
        if node[0]=='xor':consume(node[1]);consume(node[2])
        if not uses[i]:release(i)
    for i in outputs:consume(i)
    return dict(planning_work=len(nodes)+len(outputs),metadata_bytes=4*len(nodes),live_terms=live,
        peak_terms=peak,released_terms=released,released_nodes=freed),total

class LivenessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.groups=[[Query(sanitizer=s,checker_order='proof-first',retention=p) for p in POLICIES] for s in (False,True)]
    def verify(self,q,n,rows,basis,proof,**kwargs):
        return q.base.verify(n,len(rows),abi.anf_from_equations(rows),basis,proof,**kwargs)

    def test_instrumented_keep_is_exact_reference(self):
        fixtures=[(2,[[1]],[[1]],certificate(2,[['input',0]],[0])),
            (2,[[3,0]],[[3,0]],certificate(2,[['input',0]],[0])),
            (2,[[1]],[[1]],certificate(2,[['input',0],['xor',0,0]],[1])),
            (2,[],[],certificate(2,[],[]))]
        for group in self.groups:
            for case in fixtures:
                for work in list(range(100))+[1000000]:
                    a,b=[self.verify(q,*case,max_work=work) for q in group[:2]]
                    self.assertEqual(clean(a),clean(b))
                    self.assertEqual(b['liveness']['planning_work'],0)
                    self.assertEqual(b['liveness']['live_terms'],b['stats']['retained_terms'])

    def test_shared_duplicate_unused_nodes_and_oracle(self):
        rng=random.Random(940001)
        for n in (1,2,8,21,64):
            rows=[[1<<(n-1)]]
            for _ in range(8):
                nodes=[['input',0]]
                current=0
                for i in range(20):
                    a=rng.randrange(len(nodes))
                    nodes.append(['xor',a,a]);zero=len(nodes)-1
                    nodes.append(['xor',current,zero]);current=len(nodes)-1
                    if i%3==0:nodes.append(['mul',a,0])  # Unused but checked.
                p=certificate(n,nodes,[current]);expected,total=expected_liveness(rows,nodes,[current])
                self.assertTrue(abi.python_verify(n,rows,rows,p)['verified'])
                for group in self.groups:
                    base=self.verify(group[0],n,rows,rows,p);self.assertTrue(base['verified'])
                    for q in group[2:]:
                        result=self.verify(q,n,rows,rows,p);self.assertTrue(result['verified'],result)
                        self.assertEqual(result['liveness'],expected)
                        self.assertEqual(result['stats']['retained_terms'],total)
                        adjusted=clean(result);adjusted['stats']['work']-=expected['planning_work']
                        self.assertEqual(adjusted,clean(base))

    def test_live_budget_is_explicit_and_counts_result_before_release(self):
        n=64;row=[1<<i for i in range(n)];nodes=[['input',0]]
        for i in range(1,1025):nodes.append(['mul',i-1,0])
        p=certificate(n,nodes,[len(nodes)-1]);expected,total=expected_liveness([row],nodes,p['outputs'])
        self.assertEqual(expected['peak_terms'],128);self.assertEqual(total,65600)
        self.assertTrue(abi.python_verify(n,[row],[row],p,max_work=100000000,max_retained_terms=100000)['verified'])
        for group in self.groups:
            for q in group:
                result=self.verify(q,n,[row],[row],p,max_retained_terms=128)
                self.assertEqual(result['verified'],q.retention=='release-live',result)
                if not result['verified']:self.assertEqual(result['status'],'inconclusive')
            for cap in (0,63,64,127,128,129):
                result=self.verify(group[3],n,[row],[row],p,max_retained_terms=cap)
                self.assertEqual(result['verified'],cap>=128)
                self.assertLessEqual(result['liveness']['live_terms'],cap)
            self.assertEqual(self.verify(group[3],n,[row],[row],p)['liveness'],expected)

    def test_all_work_boundaries_and_recovery(self):
        rows=[[1]];nodes=[['input',0],['mul',0,0],['xor',0,1],['xor',1,2]];p=certificate(2,nodes,[3])
        for group in self.groups:
            for q in group:
                full=self.verify(q,2,rows,rows,p);self.assertTrue(full['verified'])
                for limit in range(full['stats']['work']+2):
                    result=self.verify(q,2,rows,rows,p,max_work=limit)
                    self.assertLessEqual(result['stats']['work'],limit)
                    self.assertEqual(result['verified'],limit>=full['stats']['work'])
                self.assertTrue(self.verify(q,2,rows,rows,p,max_work=(1<<64)-1,max_retained_terms=(1<<64)-1)['verified'])

    def test_unused_invalid_nodes_outputs_and_native_errors(self):
        bad=[certificate(2,[['input',0],['input',1]],[0]),
             certificate(2,[['input',0],['xor',1,1]],[0]),
             certificate(2,[['input',0],['mul',0,4]],[0]),
             certificate(2,[['input',0]],[1]),
             certificate(2,[['input',0],['xor',0,0]],[1])]
        for group in self.groups:
            for q in group:
                for p in bad:
                    if p['nodes'][-1]==['mul',0,4]:
                        original=abi.InputOwner(2,1,{1:1});owner=abi.ProofOwner(2,[[1]],certificate(2,[['input',0],['mul',0,0]],[0]));owner.nodes[1].b=4
                        result=q.base._check(original.view,owner.view,10000,10000)
                    else:result=self.verify(q,2,[[1]],[[1]],p)
                    self.assertEqual(result['status'],'rejected',result)
                # Duplicate outputs must retain the shared value until both checks.
                p=certificate(2,[['input',0]],[0,0])
                result=self.verify(q,2,[[1]],[[1],[1]],p)
                self.assertEqual(result['status'],'rejected')
                if q.retention.startswith('release'):
                    self.assertEqual(result['liveness']['released_nodes'],1)
                    self.assertEqual(result['liveness']['live_terms'],0)
            q=group[3];st=abi.CheckStats();live=LiveStats()
            self.assertEqual(q.live.check_packed_live(None,None,100,100,0,3,C.byref(st),C.byref(live)),1)
            self.assertEqual(q.live.check_packed_live(None,None,100,100,0,2,None,C.byref(live)),1)
            self.assertEqual(q.live.check_packed_live(None,None,100,100,0,2,C.byref(st),None),1)
        with self.assertRaises(ValueError):Query(retention='unknown')

    def test_concurrent_independent_lifetimes(self):
        for group in self.groups:
            q=group[3]
            def call(i):
                nodes=[['input',0]]+[ ['mul',j,0] for j in range(i+1)]
                p=certificate(21,nodes,[len(nodes)-1]);rows=[[1<<20]]
                result=self.verify(q,21,rows,rows,p,max_retained_terms=2)
                self.assertTrue(result['verified'],result)
                self.assertEqual(result['liveness'],expected_liveness(rows,nodes,p['outputs'])[0])
                return True
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                self.assertTrue(all(pool.map(call,range(48))))

if __name__=='__main__':unittest.main(verbosity=2)
