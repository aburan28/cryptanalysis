"""Exact public arithmetic tests, with explicit backend selection."""
import os
import unittest
import numpy as np
from sage.all import EllipticCurve, GF, PolynomialRing, set_random_seed
from sage.schemes.elliptic_curves.binary_batch import frobenius_points
from load_hardware import FrobeniusPlan

BACKENDS=os.environ.get('SAGE_BINARY_BACKENDS','cpu').split(',')


def integer(value, degree):
    return int(value) if degree==1 else int(value.to_integer())


class HardwareTests(unittest.TestCase):
    def setUp(self):
        set_random_seed(2026092300)

    def test_exhaustive_field_maps(self):
        for degree in range(1,9):
            F=GF(2**degree,'z')
            E=EllipticCurve(F,[1,1,0,0,1])
            values=list(F)
            data=np.array([[integer(v,degree)] for v in values],dtype=np.uint32)
            for power in (0,1,degree-1,-1):
                expected=np.array([[integer(v if not power%degree else v.frobenius(power%degree),degree)]
                                   for v in values],dtype=np.uint32)
                for backend in BACKENDS:
                    with FrobeniusPlan(E,power,backend) as plan:
                        np.testing.assert_array_equal(plan.apply_words(data),expected)

    def test_exhaustive_small_curve_points(self):
        for degree in (1,2,3,4,5):
            F=GF(2**degree,'z')
            for a in (0,1):
                E=EllipticCurve(F,[1,a,0,0,1])
                points=list(E)
                for power in (0,1,-1,degree+1):
                    expected=frobenius_points(E,points,power)
                    for backend in BACKENDS:
                        with FrobeniusPlan(E,power,backend) as plan:
                            self.assertEqual(plan.apply(iter(points)),expected)

    def test_large_fields_and_boundaries(self):
        for degree in (19,31,32,33,63,64,65,67,127,128,129,131,255,256):
            F=GF(2**degree,'z')
            E=EllipticCurve(F,[1,degree%2,0,0,1])
            points=[E.random_point() for _ in range(17)]
            points += [E(0),E(0,1),points[0],-points[0]]
            for power in (1,7,-1):
                expected=frobenius_points(E,points,power)
                for backend in BACKENDS:
                    with FrobeniusPlan(E,power,backend) as plan:
                        actual=plan.apply(points)
                        self.assertEqual(actual,expected)
                        self.assertTrue(all(P.curve() is E for P in actual))
                        self.assertEqual(plan.apply([]),[])
                        self.assertEqual(plan.apply(points[:1]),expected[:1])

    def test_modulus_and_codec_roundtrip(self):
        ring=PolynomialRing(GF(2),'t');t=ring.gen()
        first=ring.irreducible_element(19,algorithm='random')
        second=first.reverse()
        self.assertNotEqual(first,second)
        self.assertTrue(second.is_irreducible())
        for modulus in (first,second):
            F=GF(2**19,'z',modulus=modulus)
            E=EllipticCurve(F,[1,1,0,0,1])
            points=[E.random_point() for _ in range(31)]+[E(0),E(0,1)]
            for backend in BACKENDS:
                with FrobeniusPlan(E,7,backend) as plan:
                    native, flags=plan.pack_points(points)
                    native_codec=plan.codec
                    plan.codec='python'
                    reference, reference_flags=plan.pack_points(points)
                    np.testing.assert_array_equal(native,reference)
                    np.testing.assert_array_equal(flags,reference_flags)
                    self.assertEqual(plan._unpack_points(native,flags),points)
                    plan.codec=native_codec
                    self.assertEqual(plan._unpack_points(reference,flags),points)
                    self.assertEqual(plan.apply(points),frobenius_points(E,points,7))

    def test_validation_and_resource_lifetime(self):
        F=GF(2**19,'z');E=EllipticCurve(F,[1,1,0,0,1])
        other=EllipticCurve(F,[1,0,0,0,1])
        for backend in BACKENDS:
            plan=FrobeniusPlan(E,1,backend)
            with self.assertRaises(ValueError): plan.apply([other(0)])
            with self.assertRaises(ValueError): plan.apply([0])
            with self.assertRaises(ValueError): plan.apply_words(np.zeros((3,1),dtype=np.float64))
            with self.assertRaises(ValueError): plan.apply_words(np.zeros((3,2),dtype=np.uint32))
            with self.assertRaises(ValueError): plan.apply_words(np.zeros((8,1),dtype=np.uint32)[::2])
            with self.assertRaises(ValueError): plan.apply_words(np.array([[1<<19]],dtype=np.uint32))
            plan.close();plan.close()
            with self.assertRaises(RuntimeError): plan.apply([])
            with self.assertRaises(RuntimeError): plan.apply_words(np.zeros((0,1),dtype=np.uint32))
        with self.assertRaises(ValueError): FrobeniusPlan(E,backend='invalid')
        with self.assertRaises(ValueError): FrobeniusPlan(E,backend='cpu',cpu_threads=0)
        with self.assertRaises(ValueError): FrobeniusPlan(E,backend='cpu',device=-1)
        with self.assertRaises(ValueError): FrobeniusPlan(EllipticCurve(F,[1,F.gen(),0,0,1]))

    def test_sage_fallback_and_cpu_threads(self):
        F=GF(2**131,'z');E=EllipticCurve(F,[1,1,0,0,1])
        points=[E.random_point() for _ in range(257)]
        expected=frobenius_points(E,points,65)
        for backend in ('sage','auto','cpu'):
            with FrobeniusPlan(E,65,backend,cpu_threads=3) as plan:
                self.assertEqual(plan.apply(points),expected)
                if backend=='auto': self.assertEqual(plan.backend,'sage')


if __name__=='__main__':
    unittest.main()
