import gzip
import importlib.util
import json
from pathlib import Path
import unittest

from algebraic_certificate import verify
from reference_prover import prove

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('unpruned_certificate',HERE/'baseline/algebraic_certificate.py')
baseline=importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


class ProductCriterionTests(unittest.TestCase):
    def test_identical_claims_on_saved_certificates(self):
        report=json.loads(gzip.decompress((HERE/'results/proof-benchmark-before-product.json.gz').read_bytes()))
        for case in report['certificates'].values():
            old=baseline.verify(case['nvars'],case['equations'],case['basis'],case['proof'])
            new=verify(case['nvars'],case['equations'],case['basis'],case['proof'])
            self.assertTrue(old['verified'])
            self.assertTrue(new['verified'])
            self.assertEqual(old['ideal_equality'],new['ideal_equality'])
            self.assertEqual(old['reduced_groebner_basis'],new['reduced_groebner_basis'])

    def test_shared_leads_still_require_reduction(self):
        result=prove(32,[[3,4]])
        answer=verify(32,[[3,4]],result['basis'],result['proof'])
        self.assertTrue(answer['verified'])
        self.assertGreater(answer['stats']['basis_pairs']-answer['stats']['product_pairs_skipped'],0)


if __name__=='__main__':
    unittest.main()
