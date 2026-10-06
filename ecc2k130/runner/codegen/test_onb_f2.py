import os
import random
import unittest
import cnf
from onb_f2 import Dispatch, cpuReduce


class DispatchTests(unittest.TestCase):
    def test_prime_modulus_refused(self):
        with self.assertRaises(ValueError):
            Dispatch(modulus=680564733841876926932320129493409985129)

    def test_xor_truth_table_preserved(self):
        rng = random.Random(1717)
        for _ in range(20):
            f = cnf.Cnf()
            f.xors = [([rng.randrange(1,7) for _ in range(5)],bool(rng.randrange(2))) for _ in range(7)]
            original = list(f.xors)
            Dispatch().preprocess(f,blockRows=3)
            def satisfied(equations, mask):
                return all(sum((mask>>(v-1))&1 for v in variables)%2 == rhs for variables,rhs in equations)
            for mask in range(64):
                self.assertEqual(satisfied(original,mask),satisfied(f.xors,mask))

    def test_failure_falls_back(self):
        d = Dispatch('auto-cuda','/nonexistent/onb.so')
        self.assertEqual(d.reduce([3,1],2),cpuReduce([3,1],2))
        self.assertEqual(d.stats['failures'],1)

    @unittest.skipUnless(os.environ.get('ONB_F2_LIBRARY'),'native library not configured')
    def test_native_matches_cpu(self):
        rng = random.Random(1721)
        d = Dispatch('auto-cuda',os.environ['ONB_F2_LIBRARY'])
        for n,cols in ((13,65),(128,257),(128,257),(3,131),(129,64)):
            rows = [rng.getrandbits(cols) for _ in range(n)]
            self.assertEqual(d.offload(rows,cols),cpuReduce(rows,cols))
            self.assertEqual(d.reduce(rows,cols),cpuReduce(rows,cols))


if __name__ == '__main__':
    unittest.main()
