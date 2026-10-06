"""Mutations of equations, bases and certificates against exhaustive controls."""
import copy
from pathlib import Path
import random
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'pdp-scaling'))
from boolean_basis import certify_boolean_basis
from native_f4 import compute
from algebraic_certificate import verify


class AdversarialTests(unittest.TestCase):
    def test_false_claims_cannot_pass(self):
        rng=random.Random(2026092511)
        rejected=0
        for n in range(1,8):
            for _ in range(8):
                equations=[[rng.randrange(1 << n) for _ in range(rng.randrange(1,9))]
                           for _ in range(rng.randrange(1,n+2))]
                producer=compute(n,equations)
                self.assertTrue(producer['verified'])
                for _ in range(12):
                    basis=copy.deepcopy(producer['basis'])
                    originals=copy.deepcopy(equations)
                    proof=copy.deepcopy(producer['proof'])
                    arm=rng.randrange(4)
                    if arm==0 and basis:
                        basis[rng.randrange(len(basis))].append(rng.randrange(1 << n))
                    elif arm==1:
                        originals[rng.randrange(len(originals))].append(rng.randrange(1 << n))
                    elif arm==2 and proof['nodes']:
                        i=rng.randrange(len(proof['nodes']))
                        proof['nodes'][i]=['xor',i,i]  # guaranteed forward/self reference
                    else:
                        basis.append([rng.randrange(1 << n)])
                    actual=verify(n,originals,basis,proof)
                    if actual['verified']:
                        self.assertTrue(certify_boolean_basis(n,originals,basis)['verified'],
                                        (n,originals,basis,proof))
                    else:
                        rejected+=1
        self.assertGreater(rejected,500)

    def test_malformed_proof_shapes(self):
        correct={'version':1,'nvars':32,'order':'grevlex-x0-first','nodes':[['input',0]],'outputs':[0]}
        for replacement in (None,[],{'nodes':[]},dict(correct,nodes=None),dict(correct,outputs=None),
                            dict(correct,nodes=[['input',True]]),dict(correct,nodes=[['input','0']]),
                            dict(correct,nodes=[['mul',-1,1]]),dict(correct,nodes=[['mul',0,-1]]),
                            dict(correct,nodes=[['unknown',0]]),dict(correct,outputs=[1 << 32])):
            answer=verify(32,[[1]],[[1]],replacement)
            self.assertEqual(answer['status'],'rejected',answer)


if __name__=='__main__':
    unittest.main()
