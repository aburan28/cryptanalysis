import copy
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent.parent.parent/'pdp-scaling'))
from boolean_basis import certify_boolean_basis
from algebraic_certificate import verify
from reference_prover import prove


class AlgebraicTests(unittest.TestCase):
    def test_small_random_against_enumeration(self):
        rng = random.Random(2026092508)
        for n in range(1,8):
            for _ in range(20):
                equations = [[rng.randrange(1 << n) for _ in range(rng.randrange(1,8))]
                             for _ in range(rng.randrange(1,n+1))]
                result = prove(n,equations,max_work=10_000_000)
                answer = verify(n,equations,result['basis'],result['proof'])
                self.assertTrue(answer['verified'],answer)
                oracle = certify_boolean_basis(n,equations,result['basis'])
                self.assertTrue(oracle['verified'],oracle)

    def test_128_variables_without_enumeration(self):
        # All variables occur in nonlinear inputs. Pair products forced to one
        # have a compact linear GB, but no 2^128 enumeration is feasible.
        equations = [[(1 << i) | (1 << (i+1)),0] for i in range(0,128,2)]
        result = prove(128,equations)
        self.assertEqual(len(result['basis']),128)
        answer = verify(128,equations,result['basis'],result['proof'])
        self.assertTrue(answer['verified'],answer)
        self.assertIsNone(answer['root_count'])
        self.assertGreater(answer['stats']['field_pairs'],0)

    def test_free_variables_and_zero_ideal(self):
        for n, equations in ((65,[]),(96,[[3,0]]),(32,[[0]])):
            result = prove(n,equations)
            self.assertTrue(verify(n,equations,result['basis'],result['proof'])['verified'])

    def test_implicit_field_pairs_are_required(self):
        # A singleton would pass a checker that only tests ordinary G/G pairs.
        for row in ([3,0],[3,4]):
            proof = {'version':1,'nvars':32,'order':'grevlex-x0-first',
                     'nodes':[['input',0]],'outputs':[0]}
            answer = verify(32,[row],[row],proof)
            self.assertFalse(answer['verified'])
            self.assertIn('field pair',answer['reason'])

    def test_membership_and_reverse_inclusion(self):
        proof = {'version':1,'nvars':32,'order':'grevlex-x0-first',
                 'nodes':[['input',0]],'outputs':[0]}
        self.assertFalse(verify(32,[[1]],[[0]],proof)['verified'])
        self.assertFalse(verify(32,[[1],[2]],[[1]],proof)['verified'])

    def test_basis_critical_pair_is_required(self):
        # x(y+1), y(z+1) are individually closed under field pairs, but
        # their mutual S-polynomial leaves xz+x as a nonzero remainder.
        equations = [[3,1],[6,2]]
        proof = {'version':1,'nvars':32,'order':'grevlex-x0-first',
                 'nodes':[['input',0],['input',1]],'outputs':[0,1]}
        answer = verify(32,equations,equations,proof)
        self.assertFalse(answer['verified'])
        self.assertIn('basis critical pair',answer['reason'])

    def test_corrupted_graphs_and_budgets(self):
        equations = [[3,0]]
        result = prove(32,equations)
        proof = result['proof']
        for mutate in (lambda p:p.update(nvars=31),lambda p:p.update(order='lex'),
                       lambda p:p['nodes'].__setitem__(0,['input',-1]),
                       lambda p:p['nodes'].__setitem__(0,['xor',0,0]),
                       lambda p:p['nodes'].__setitem__(0,['mul',0,1 << 32]),
                       lambda p:p.update(outputs=[0]*len(p['outputs']))):
            corrupt = copy.deepcopy(proof)
            mutate(corrupt)
            self.assertEqual(verify(32,equations,result['basis'],corrupt)['status'],'rejected')
        for limits in ({'max_work':0},{'max_retained_terms':0}):
            answer = verify(32,equations,result['basis'],proof,**limits)
            self.assertEqual(answer['status'],'inconclusive')
            self.assertFalse(answer['verified'])


if __name__ == '__main__':
    unittest.main()
