"""Independent arithmetic/oracle checks, false claims, ABI validation and budgets."""
import copy
import ctypes as C
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import random
import sys
import unittest

from packed_proof import PackedProof,InputOwner,ProofOwner,anf_from_equations,HERE
from algebraic_certificate import verify
from native_f4 import compute as baseline
sys.path.insert(0,str(HERE.parent.parent/'pdp-scaling'))
from boolean_basis import certify_boolean_basis


class PackedProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.libraries=[PackedProof(),PackedProof(sanitizer=True)]
        cls.random_verified=0
        cls.random_inconclusive=0

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({'random_controls_verified':cls.random_verified,
                          'random_controls_inconclusive':cls.random_inconclusive}))

    def test_small_random_against_independent_oracles(self):
        rng=random.Random(2026092514)
        for n in range(1,9):
            for _ in range(12):
                equations=[[rng.randrange(1<<n) for _ in range(rng.randrange(1,9))]
                           for _ in range(rng.randrange(1,n+2))]
                anf=anf_from_equations(equations)
                expected=baseline(n,equations)
                if not expected['verified']:
                    # Keep difficult controls at the declared budget. A failed
                    # baseline is not a speedup and is not a certificate.
                    self.assertEqual(expected['status'],'inconclusive',expected)
                    for query in self.libraries:
                        result=query.compute(n,len(equations),anf)
                        self.assertEqual(result['status'],'inconclusive',result)
                        self.assertFalse(result['verified'])
                    type(self).random_inconclusive+=1
                    continue
                type(self).random_verified+=1
                for query in self.libraries:
                    result=query.compute(n,len(equations),anf,export_proof=True)
                    self.assertTrue(result['verified'],result)
                    self.assertEqual(result['basis'],expected['basis'])
                    self.assertTrue(verify(n,equations,result['basis'],result['proof'])['verified'])
                    self.assertTrue(certify_boolean_basis(n,equations,result['basis'])['verified'])

    def test_wide_inputs_and_multi_limb_equations(self):
        for n in (21,31,32,63,64):
            equations=[[3<<i,0] for i in range(0,n-1,2)]+[[1<<(n-1),0]]
            for query in self.libraries:
                result=query.compute(n,len(equations),anf_from_equations(equations),export_proof=True)
                self.assertTrue(result['verified'],result)
                self.assertEqual(result['basis'],[[0,1<<i] for i in range(n)])
                self.assertTrue(verify(n,equations,result['basis'],result['proof'])['verified'])
        for size in (0,1,63,64,65,127,128,129,4096):
            equations=[[] for _ in range(size)]
            if size:equations[-1]=[1<<63,0]
            for query in self.libraries:
                result=query.compute(64,size,anf_from_equations(equations),export_proof=True)
                self.assertTrue(result['verified'],result)
                self.assertTrue(verify(64,equations,result['basis'],result['proof'])['verified'])

    def test_required_math_checks(self):
        cases=[([[3,0]],[[3,0]],'field pair'),([[3,4]],[[3,4]],'field pair'),
               ([[1]],[[0]],'witnessed'),([[1],[2]],[[1]],'input generator'),
               ([[3,1],[6,2]],[[3,1],[6,2]],'basis critical pair'),
               ([[1],[2]],[[1],[2],[1,2]],'reduced')]
        for equations,basis,reason in cases:
            nodes=[['input',i] for i in range(len(equations))]
            outputs=list(range(len(basis)))
            if reason=='reduced':nodes.append(['xor',0,1])
            proof={'version':1,'nvars':32,'order':'grevlex-x0-first','nodes':nodes,'outputs':outputs}
            for query in self.libraries:
                result=query.verify(32,len(equations),anf_from_equations(equations),basis,proof)
                self.assertEqual(result['status'],'rejected',result)
                self.assertIn(reason,result['reason'])

    def test_adversarial_mutations(self):
        rng=random.Random(2026092515);accepted=0;rejected=0
        for n in range(1,8):
            for _ in range(8):
                equations=[[rng.randrange(1<<n) for _ in range(rng.randrange(1,9))]
                           for _ in range(rng.randrange(1,n+2))]
                produced=self.libraries[0].compute(n,len(equations),anf_from_equations(equations),export_proof=True)
                self.assertTrue(produced['verified'],produced)
                for _ in range(12):
                    originals=copy.deepcopy(equations);basis=copy.deepcopy(produced['basis']);proof=copy.deepcopy(produced['proof'])
                    arm=rng.randrange(4)
                    if arm==0 and basis:basis[rng.randrange(len(basis))].append(rng.randrange(1<<n))
                    elif arm==1:originals[rng.randrange(len(originals))].append(rng.randrange(1<<n))
                    elif arm==2 and proof['nodes']:
                        index=rng.randrange(len(proof['nodes']));proof['nodes'][index]=['xor',index,index]
                    else:basis.append([rng.randrange(1<<n)])
                    expected=verify(n,originals,basis,proof)
                    for query in self.libraries:
                        actual=query.verify(n,len(originals),anf_from_equations(originals),basis,proof)
                        self.assertEqual(actual['verified'],expected['verified'],(actual,expected))
                        if actual['verified']:
                            self.assertTrue(certify_boolean_basis(n,originals,basis)['verified']);accepted+=1
                        else:rejected+=1
        self.assertEqual(accepted+rejected,1344)
        self.assertGreater(rejected,1000)

    def test_native_abi_rejects_malformed_proofs(self):
        original=InputOwner(32,1,{1:1})
        proof={'version':1,'nvars':32,'order':'grevlex-x0-first','nodes':[['input',0]],'outputs':[0]}
        mutations=[lambda p:setattr(p.view,'version',2),lambda p:setattr(p.view,'nvars',31),
            lambda p:setattr(p.view,'order',0),lambda p:setattr(p.view,'reserved',1),
            lambda p:p.offsets.__setitem__(0,1),lambda p:p.offsets.__setitem__(1,0),
            lambda p:setattr(p.nodes[0],'op',3),lambda p:setattr(p.nodes[0],'a',1),
            lambda p:setattr(p.nodes[0],'b',1),lambda p:p.outputs.__setitem__(0,1),
            lambda p:p.terms.__setitem__(0,1<<32)]
        for mutate in mutations:
            for query in self.libraries:
                owner=ProofOwner(32,[[1]],proof);mutate(owner)
                result=query._check(original.view,owner.view,20_000_000,2_000_000)
                self.assertEqual(result['status'],'rejected',result)
        for query in self.libraries:
            owner=ProofOwner(32,[[1]],proof)
            original.coefficients[0]=2
            self.assertEqual(query._check(original.view,owner.view,20_000_000,2_000_000)['status'],'rejected')
            original.coefficients[0]=1

    def test_invalid_python_values_and_budgets(self):
        query=self.libraries[0]
        for n,eq,anf in [(0,1,{1:1}),(65,1,{1:1}),(64,0,{1:0}),
                          (3,1,{8:1}),(64,1,{-1:1}),(64,1,{1:-1}),(64,1,{1:2}),(64,1,{True:1})]:
            with self.assertRaises(ValueError):query.compute(n,eq,anf)
        for options in ({'max_work':0},{'max_nodes':1},{'max_rows':1,'batch':1},
                        {'max_check_work':0},{'max_retained_terms':0}):
            for query in self.libraries:
                result=query.compute(4,2,{0:3,3:1,12:2},**options)
                self.assertEqual(result['status'],'inconclusive',result)
                self.assertFalse(result['complete'])
                self.assertTrue(query.compute(4,2,{0:3,3:1,12:2})['verified'])

    def test_saved_certificates_and_concurrency(self):
        report=json.loads(gzip.decompress((HERE.parent/'round5/results/proof-benchmark.json.gz').read_bytes()))
        for case in report['certificates'].values():
            for query in self.libraries:
                result=query.verify(case['nvars'],len(case['equations']),anf_from_equations(case['equations']),case['basis'],case['proof'])
                self.assertTrue(result['verified'],result)
        def task(i):
            query=self.libraries[i%2]
            n=(5,21,32,64)[i%4]
            answer=query.compute(n,2,{3:1,0:1,(1<<(n-1)):2})
            self.assertTrue(answer['verified'],answer)
            with self.assertRaises(ValueError):query.compute(n,1,{1:2})
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(task,range(64)))


if __name__=='__main__':
    unittest.main()
