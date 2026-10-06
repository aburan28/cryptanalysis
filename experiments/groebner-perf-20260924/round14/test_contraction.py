"""Exact descent parity, ABI bounds, independent certificates and fresh state."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
from dataclasses import replace
import random
import sys
import unittest

from native_descent import NativeDescent, DescentPlan, PackedANF, packed_query, Edge, U32, U64, HERE
from descend import GF2n, Curve, descend, sumpoly, make_instance
sys.path.insert(0, str(HERE.parent.parent / 'pdp-scaling'))
from boolean_basis import certify_boolean_basis


class ContractionTests(unittest.TestCase):
    def test_exact_coefficients_and_multiword_boundaries(self):
        rng = random.Random(2026092601)
        shapes = ((5,2,2,1), (7,3,2,3), (11,4,2,1), (31,3,6,1),
                  (63,2,2,7), (64,2,2,1), (65,2,2,3), (83,3,2,1),
                  (127,2,2,1), (128,2,2,5))
        count = 0
        for n, m, ell, b in shapes:
            field = GF2n(n)
            targets = [0, (1 << n)-1, rng.getrandbits(n), 0]
            reference = [descend(sumpoly.load(m+1), field, Curve(field,b), m, ell, x) for x in targets]
            plan = DescentPlan(n, field.mod, b, m, ell)
            self.assertEqual([plan.descend(x) for x in targets], reference)
            for sanitizer in (False, True):
                with NativeDescent(n, field.mod, b, m, ell, sanitizer=sanitizer) as native:
                    packed = [native.descend_packed(x) for x in targets]
                    self.assertEqual([p.to_dict() for p in packed], reference)
                    self.assertEqual([dict(p.items()) for p in packed], reference)
                    for p in packed:
                        self.assertTrue(all(c and not c >> n for _, c in p.items()))
                    count += len(targets)
        print('exact native descent comparisons:', count)

    def test_call_freshness_lifetime_and_shared_concurrency(self):
        field = GF2n(31)
        with NativeDescent(31, field.mod, 1, 3, 3) as native:
            targets = list(range(32))
            expected = [native.descend(x) for x in targets]
            with ThreadPoolExecutor(max_workers=4) as executor:
                outputs = list(executor.map(native.descend_packed, targets))
            self.assertEqual([x.to_dict() for x in outputs], expected)
            for invalid in (-1, 1 << 31, 0.5, '0', None):
                with self.assertRaises(ValueError):
                    native.descend(invalid)
            self.assertEqual(native.descend(targets[0]), expected[0])
        self.assertEqual([x.to_dict() for x in outputs], expected)
        with self.assertRaises(RuntimeError):
            native.descend(0)
        native.close()

    def test_packed_solver_certificate_and_curve_replay(self):
        for n, ell, seed in ((11,2,1), (31,6,101), (83,2,2)):
            original = make_instance(n, 3, ell, seed=seed)
            with NativeDescent(n, original.mod, original.b, 3, ell) as native, \
                    packed_query(3*ell, n) as query:
                anf = native.descend_packed(original.xR)
                self.assertEqual(anf.to_dict(), original.anf)
                result = query.solve(replace(original, anf=anf))
                self.assertTrue(result.get('verified'), result)
                self.assertEqual(original.evaluate(result['assignment']), 0)
                plain = query.solve(original)
                self.assertEqual(result['basis_sha256'], plain['basis_sha256'])
                self.assertEqual(result['assignment'], plain['assignment'])
                basis = query.compute(anf)['basis_terms']
                if original.nvars <= 8:
                    self.assertTrue(certify_boolean_basis(original.nvars, original.equations(), basis)['verified'])
                bad = anf.to_dict()
                bad[0] = bad.get(0, 0) ^ ((1 << n)-1)
                # Certificate must evaluate the supplied changed equations.
                self.assertFalse(query.certify(bad, basis)['verified'])
                mismatch = PackedANF(3*ell-1, n, anf._owners[0], anf._owners[1], len(anf.masks))
                with self.assertRaises(ValueError):
                    query.compute(mismatch)

    def test_abi_validation_failure_recovery_and_cancellation(self):
        field = GF2n(8)
        for sanitizer in (False, True):
            with NativeDescent(8, field.mod, 1, 2, 2, sanitizer=sanitizer) as native:
                lib = native._lib
                sizes = (U32*2)(2,2); offsets = (U32*2)(0,2)
                edges = (Edge*2)(Edge(0,0,0), Edge(1,1,0))
                tables = (U64*256)(*range(256)); masks = (U32*2)(0,1)
                args = [8,2,1,sizes,offsets,edges,2,tables,256,1,masks]
                def rejected(changes):
                    values = args[:]
                    for index, value in changes.items(): values[index] = value
                    self.assertFalse(lib.contraction_create(*values))
                for index, value in ((0,0),(0,129),(1,21),(2,0),(2,5),
                                     (3,None),(4,None),(5,None),(7,None),
                                     (8,255),(9,0),(10,None)):
                    rejected({index:value})
                rejected({3:(U32*2)(0,2)})
                rejected({4:(U32*2)(1,2)})
                rejected({4:(U32*2)(0,3)})
                rejected({5:(Edge*2)(Edge(2,0,0),Edge(1,1,0))})
                rejected({5:(Edge*2)(Edge(0,2,0),Edge(1,1,0))})
                rejected({5:(Edge*2)(Edge(0,0,1),Edge(1,1,0))})
                rejected({10:(U32*2)(1,1)})
                rejected({10:(U32*2)(1,4)})
                tables[2] = 256; rejected({}); tables[2] = 2
                handle = lib.contraction_create(*args)
                self.assertTrue(handle, lib.contraction_error())
                try:
                    initial=(U64*2)(17,0); out=(U32*2)(); coefficients=(U64*2)(); count=U32(99)
                    def compute(words=2, capacity=2, owner=handle):
                        return lib.contraction_compute(owner,initial,words,out,coefficients,capacity,ct.byref(count))
                    self.assertEqual(compute(),0); self.assertEqual(count.value,1)
                    self.assertEqual((out[0],coefficients[0]),(0,17))
                    for words,capacity,owner in ((1,2,handle),(2,1,handle),(2,2,None)):
                        self.assertEqual(compute(words,capacity,owner),1); self.assertEqual(count.value,0)
                    initial[0]=256; self.assertEqual(compute(),1); self.assertEqual(count.value,0)
                    initial[0]=0; self.assertEqual(compute(),0); self.assertEqual(count.value,0)
                    initial[1]=29; self.assertEqual(compute(),0)
                    self.assertEqual((count.value,out[0],coefficients[0]),(1,1,29))
                finally:
                    lib.contraction_destroy(handle)
                # Two identical contraction edges cancel by characteristic two.
                edges[1]=edges[0]
                handle=lib.contraction_create(*args)
                self.assertTrue(handle)
                try:
                    self.assertEqual(lib.contraction_compute(handle,(U64*2)(17,0),2,
                        out,coefficients,2,ct.byref(count)),0)
                    self.assertEqual(count.value,0)
                finally:
                    lib.contraction_destroy(handle)


if __name__ == '__main__':
    unittest.main()
