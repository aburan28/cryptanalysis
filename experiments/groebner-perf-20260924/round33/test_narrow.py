"""Independent mathematical controls and width-boundary/cross-checker replay."""
import importlib.util
import os
import random
import unittest

from narrow import HERE, Producer, Checker, Packed
import sys
sys.path.insert(0, str(HERE.parent/'round32'))
import certified as previous

# Replay the unchanged exhaustive/adversarial certificate suite against the
# new libraries. The reference truth and proof equations stay unchanged.
_spec = importlib.util.spec_from_file_location('narrow_certificate_controls', HERE.parent/'round32/test_certificates.py')
_controls = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_controls)
_controls.Producer, _controls.Checker = Producer, Checker


class NarrowCertificates(_controls.CertificateTests):
    pass


class NarrowMetalCertificates(_controls.MetalCertificateTests):
    pass


class WidthTests(unittest.TestCase):
    def test_equation_boundaries_interleaved_libraries_and_cross_certification(self):
        rng = random.Random(2026092933)
        backends = ['cpu', 'metal'] if os.environ.get('QUADRATIC_TEST_METAL') == '1' else ['cpu']
        for e in (1, 31, 32, 33, 63, 64, 65, 127, 128):
            for backend in backends:
                x, y, q = 4, 3, 6
                with Producer(x, y, e, backend=backend) as new, previous.Producer(x, y, e, backend=backend) as old, Checker(x,y,e) as check, previous.Checker(x,y,e) as old_check:
                    for iteration in range(3):
                        terms = [(m, rng.getrandbits(e)) for m in range(128) if (m>>x).bit_count()<=2 and rng.randrange(2)]
                        p = Packed(x+y, e, terms)
                        a, b = new.produce(p, checker=check), old.produce(p, checker=old_check)
                        for key in ('roots','basis','proof_bytes'):
                            self.assertEqual(a[key],b[key],(e,backend,iteration,key))
                        self.assertTrue(check.certify(p,b['roots'],b['basis'],b['proof_bytes'])['verified'])
                        self.assertTrue(old_check.certify(p,a['roots'],a['basis'],a['proof_bytes'])['verified'])
                        width = 4 if e<=32 else 8 if e<=64 else 16
                        limbs, branches = (e+63)//64, 1<<x
                        gpu = int(backend=='metal' and e<=32)
                        expected = branches*(q+1)*width + branches*limbs*8
                        if gpu: expected += branches*(q+1)*4 + branches*34*4 + 12
                        self.assertEqual(a['stats']['workspace_bytes'],expected)
                        self.assertEqual(a['certificate']['stats']['workspace_bytes'],branches*(q+1)*limbs*(4 if e<=32 else 8))
                        self.assertEqual(new.coefficient_bits,width*8)
                        self.assertEqual(check.coefficient_bits,32 if e<=32 else 64)
                        self.assertEqual(a['stats']['gpu_used'],gpu)
                        self.assertEqual(a['stats']['gpu_shape_fallback'],int(backend=='metal' and e>32))
                        self.assertEqual(a['roots'],_controls.roots(x+y,terms))

    def test_invalid_padding_is_rejected_before_narrowing_and_reuse(self):
        for sanitizer in (False,True):
            for e in (1,31,32,33,63,65,127):
                with Producer(2,2,e,sanitizer=sanitizer) as producer, Checker(2,2,e,sanitizer=sanitizer) as check:
                    p = Packed(4,e,[(1,1)])
                    valid = producer.produce(p,checker=check)
                    limb, invalid = e//64, 1<<(e%64)
                    original = p.coefficients[limb]
                    p.coefficients[limb] |= invalid
                    with self.assertRaises(ValueError): producer.produce(p)
                    with self.assertRaises(ValueError): check.certify(p,valid['roots'],valid['basis'],valid['proof_bytes'])
                    with self.assertRaises(ValueError): check.evaluate(p,0)
                    p.coefficients[limb] = original
                    self.assertEqual(producer.produce(p,checker=check)['roots'],valid['roots'])

    def test_new_capacity_with_independently_known_nonlinear_roots(self):
        for x,y in ((18,9),(18,10)):
            n=x+y
            fixed=0x12345
            items=[(1<<i,1<<i) for i in range(x)]+[(0,fixed)]
            items += [((1<<x)|(1<<(x+1)),1<<x),(0,1<<x)]
            items += [(1<<(x+j),1<<(x+j)) for j in range(1,y)]
            items += [(1<<x,sum(1<<(x+j) for j in range(1,y)))]
            p=Packed(n,n,items)
            with self.assertRaises(ValueError): previous.Producer(x,y,n)
            with self.assertRaises(ValueError): previous.Checker(x,y,n)
            with Producer(x,y,n) as producer, Checker(x,y,n) as check:
                a=producer.produce(p,checker=check)
                self.assertEqual(a['roots'],[fixed|(((1<<y)-1)<<x)])
                self.assertTrue(a['certificate']['verified'])
                self.assertEqual(a['certificate']['stats']['assignments'],1<<y)
                self.assertEqual(a['certificate']['stats']['contradictions'],(1<<x)-1)
                self.assertTrue(_controls.verify_basis(n,items,a['roots'],a['basis'],1))
                self.assertEqual(check.certify(p,[],a['basis'],a['proof_bytes'])['code'],3)


if __name__ == '__main__':
    unittest.main()
