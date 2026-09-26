import json
from pathlib import Path
import random
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'pdp-scaling'))
from boolean_basis import certify_boolean_basis
from native_f4 import compute
from reference_prover import prove


class NativeTests(unittest.TestCase):
    def test_random_differential(self):
        rng = random.Random(2026092509)
        for n in range(1,9):
            for _ in range(12):
                equations = [[rng.randrange(1 << n) for _ in range(rng.randrange(1,9))]
                             for _ in range(rng.randrange(1,n+2))]
                answers = [compute(n,equations,binary=HERE/'build'/name)
                           for name in ('native-f4','native-f4-ubsan')]
                for result in answers:
                    self.assertTrue(result['verified'],(n,equations,result))
                    self.assertTrue(certify_boolean_basis(n,equations,result['basis'])['verified'])
                self.assertEqual(answers[0]['basis'],answers[1]['basis'])
                untraced = compute(n,equations,record=False,check=False)
                self.assertEqual(untraced['basis'],answers[0]['basis'])
                self.assertFalse(untraced['verified'])
                self.assertIsNone(untraced['proof'])

    def test_wide_inputs(self):
        for n in (21,31,32,63,64):
            equations = [[(1 << i)|(1 << (i+1)),0] for i in range(0,n-1,2)]
            equations += [[1 << (n-1),0]]
            for name in ('native-f4','native-f4-ubsan'):
                answer = compute(n,equations,binary=HERE/'build'/name)
                self.assertTrue(answer['verified'],answer)
                self.assertEqual(answer['basis'],[[0,1 << i] for i in range(n)])
                self.assertGreater(answer['stats']['matrices'],0)

    def test_zero_unit_and_field_pairs(self):
        for n,equations in ((64,[]),(64,[[]]),(64,[[0]]),(32,[[3,0]]),
                            (32,[[3,4]]),(5,[[1,1],[2,2]]),(5,[[]]*64+[[0]])):
            answer = compute(n,equations)
            self.assertTrue(answer['verified'],answer)
            self.assertEqual(answer['basis'],prove(n,equations)['basis'])

    def test_bounded_failures_and_retry(self):
        equations = [[3,0],[12,0]]
        for options in ({'max_work':0},{'max_nodes':1},{'max_rows':1,'batch':1},
                        {'max_check_work':0},{'max_retained_terms':0}):
            answer = compute(4,equations,**options)
            self.assertEqual(answer['status'],'inconclusive',answer)
            self.assertFalse(answer['complete'])
        self.assertTrue(compute(4,equations)['verified'])
        self.assertEqual(compute(65,equations)['status'],'unsupported')

    def test_native_parser(self):
        for name in ('native-f4','native-f4-ubsan'):
            binary = HERE/'build'/name
            for text in ('', '65 0 100 100 100 64 1\n',
                         '3 1 100 100 100 64 1\n1 8\n',
                         '3 1 100 100 100 64 1\n1 -1\n',
                         '64 1 100 100 100 64 1\n1 -1\n',
                         '64 1 100 100 100 64 1\n1 18446744073709551616\n',
                         '64 0 -1 100 100 64 1\n',
                         '3 1 100 100 100 64 1\n2 1\n',
                         '3 0 100 100 100 64 1\nextra\n'):
                run = subprocess.run([str(binary)],input=text,text=True,capture_output=True,timeout=10)
                self.assertEqual(run.returncode,2,(text,run.stdout,run.stderr))
                self.assertEqual(json.loads(run.stdout)['status'],'invalid-input')


if __name__ == '__main__':
    unittest.main()
