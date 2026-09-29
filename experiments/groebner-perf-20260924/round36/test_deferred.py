"""Independent original-polynomial identities, truth and exact fallback controls."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
import os
import random
import sys
import unittest

from deferred import Producer, Checker, Packed, HERE, Inconclusive, Unsupported, U64
from quadratic_reference import verify_basis


def truth(n, items):
    roots = []
    for assignment in range(1 << n):
        value = 0
        for mask, coefficient in items:
            if assignment & mask == mask:
                value ^= coefficient
        if not value:
            roots.append(assignment)
    return roots


def check_identities(x, y, e, items, raw):
    """Direct specialization of original terms, no native coefficient tables."""
    words = [int.from_bytes(raw[i:i+8], sys.byteorder) for i in range(0, len(raw), 8)]
    limbs, branches = (e+63)//64, 1 << x
    prefix, entry = branches*limbs, 1+(y+1)*limbs
    assert len(raw)%8 == 0 and len(words)>=prefix and (len(words)-prefix)%entry == 0
    certificates = {}
    for a in range(branches):
        u = sum(words[a*limbs+l] << (64*l) for l in range(limbs))
        if u:
            certificates[a] = [u]+[0]*y
    previous = -1
    for offset in range(prefix, len(words), entry):
        a = words[offset]
        assert previous < a < branches and a not in certificates
        previous = a
        certificates[a] = [sum(words[offset+1+j*limbs+l] << (64*l) for l in range(limbs))
                           for j in range(y+1)]
    for a, coefficients in certificates.items():
        identity = set()
        for j, u in enumerate(coefficients):
            assert 0 <= u < 1 << e
            multiplier = 0 if j == 0 else 1 << (j-1)
            for mask, coefficient in items:
                fixed, residual = mask & (branches-1), mask >> x
                if a & fixed == fixed and (u & coefficient).bit_count()%2:
                    identity.symmetric_difference_update((residual | multiplier,))
        assert identity == {0}
    return len(certificates)


class DeferredTests(unittest.TestCase):
    def backends(self):
        return ('cpu', 'metal') if os.environ.get('QUADRATIC_TEST_METAL') == '1' else ('cpu',)

    def verify(self, x, y, e, items, producer, checker):
        p = Packed(x+y, e, items)
        result = producer.produce(p, checker=checker)
        expected = truth(x+y, items)
        self.assertEqual(result['roots'], expected)
        self.assertTrue(result['certificate']['verified'], result['certificate'])
        self.assertTrue(verify_basis(x+y, items, expected, result['basis'], len(expected)))
        self.assertEqual(check_identities(x, y, e, items, result['proof_bytes']),
                         result['certificate']['stats']['contradictions'])
        stats = result['multiplier_stats']
        self.assertEqual(stats['attempts'], stats['certified_branches']+stats['failed_branches'])
        self.assertEqual(stats['certified_branches']+result['symmetry_stats']['affine_copies'], result['certificate']['stats']['extended_contradictions'])
        self.assertEqual(result['symmetry_stats']['representatives']+result['symmetry_stats']['aliases'],1<<x)
        self.assertEqual(stats['proof_words']*8, len(result['proof_bytes']))
        return result

    def test_affine_identity_and_bounded_fallback(self):
        items = [(2, 1), (4, 2), (6, 4), (0, 4)]
        for backend in self.backends():
            with Producer(1,2,3,backend=backend) as p, Checker(1,2,3) as c:
                r = self.verify(1,2,3,items,p,c)
                self.assertEqual(r['multiplier_stats']['certified_branches'], 2)
                self.assertEqual(r['certificate']['stats']['assignments'], 0)
                self.assertEqual(r['proof_bytes'][:16], bytes(16))
        with Producer(1,2,3,multiplier_budget_test=True) as p, Checker(1,2,3) as c:
            r = self.verify(1,2,3,items,p,c)
            self.assertGreater(r['multiplier_stats']['budget_skips'], 0)
            self.assertGreater(r['certificate']['stats']['assignments'], 0)
            self.assertLessEqual(r['multiplier_stats']['rows']+r['multiplier_stats']['row_xors'], 8)

    def test_incomplete_degree_one_filter_with_independent_dual_witness(self):
        equations = [[0,2,3,5,10], [0,2,3,4,5,6,8,9,10], [0,4,6,12]]
        columns = [m for m in range(16) if m.bit_count()<=3]
        dual = 0x61bf
        self.assertEqual(dual&1, 1)
        for row in equations:
            for multiplier in (0,1,2,4,8):
                product = set()
                for m in row:
                    product.symmetric_difference_update((m|multiplier,))
                self.assertEqual(sum((dual >> columns.index(m)) & 1 for m in product)%2, 0)
        items = [(m<<1,1<<i) for i,row in enumerate(equations) for m in row]
        for backend in self.backends():
            with Producer(1,4,3,backend=backend) as p, Checker(1,4,3) as c:
                r = self.verify(1,4,3,items,p,c)
                self.assertEqual(r['roots'], [])
                self.assertEqual(r['multiplier_stats']['certified_branches'], 0)
                self.assertEqual(r['stats']['fallback_assignments'], 32)
                self.assertEqual(r['certificate']['stats']['assignments'], 32)

    def test_every_three_variable_function(self):
        for backend in self.backends():
            with Producer(2,1,1,backend=backend) as p, Checker(2,1,1) as c:
                for bits in range(256):
                    self.verify(2,1,1,[(m,1) for m in range(8) if bits>>m&1],p,c)

    def test_random_widths_duplicates_sanitizer_and_reuse(self):
        rng = random.Random(2026092934)
        for sanitizer in (False, True):
            for e in (1,3,31,32,33,63,64,65,127,128):
                with Producer(2,3,e,sanitizer=sanitizer) as p, Checker(2,3,e,sanitizer=sanitizer) as c:
                    for _ in range(5):
                        items = [(m,rng.getrandbits(e)) for m in range(32)
                                 if (m>>2).bit_count()<=2 and rng.randrange(2)]
                        items += items[:3]*2 + [(0,0)]
                        self.verify(2,3,e,items,p,c)
                    # The high equation alone must participate in a valid
                    # affine identity, including the 64/65 boundary.
                    if e>=3:
                        self.verify(2,3,e,[(4,1),(8,2),(12,1<<(e-1)),(0,1<<(e-1))],p,c)

    def test_forged_sparse_records_padding_and_original_equations(self):
        items = [(2,1),(4,2),(6,4),(0,4)]
        p = Packed(3,3,items)
        with Producer(1,2,3) as producer, Checker(1,2,3) as checker:
            r = producer.produce(p,checker=checker)
            words = list((U64*(len(r['proof_bytes'])//8)).from_buffer_copy(r['proof_bytes']))
            for kind in ('identity','padding','branch','duplicate','overlap','extent'):
                bad = words[:]
                if kind=='identity': bad[3:6] = [0,0,0]
                elif kind=='padding': bad[3] |= 8
                elif kind=='branch': bad[2] = 2
                elif kind=='duplicate': bad[6] = bad[2]
                elif kind=='overlap': bad[0] = 1
                else: bad.pop()
                proof = (U64*len(bad))(*bad)
                with self.subTest(kind=kind):
                    if kind=='identity': self.assertEqual(checker.certify(p,[],r['basis'],proof)['code'],9)
                    else:
                        with self.assertRaises(ValueError): checker.certify(p,[],r['basis'],proof)
            # A proof from the inconsistent system cannot validate a changed
            # consistent input, even with identical dimensions and support.
            changed = Packed(3,3,[(2,1),(4,2),(6,4)])
            self.assertFalse(checker.certify(changed,[],r['basis'],r['proof_bytes'])['verified'])
            self.assertTrue(producer.produce(p,checker=checker)['certificate']['verified'])

    def test_symmetric_affine_copies_roots_diagonals_and_fresh_fallback(self):
        from multipliers import Producer as Baseline
        for backend in self.backends():
            with Producer(4,2,3,backend=backend) as p, Checker(4,2,3) as c, Baseline(4,2,3,backend=backend) as old:
                # Three residual equations need an affine contradiction. Fixed
                # variables are free, so all unordered representatives qualify.
                impossible=[(16,1),(32,2),(48,4),(0,4)]
                # Symmetric first-block/second-block equality and residual pins.
                roots=[(1,1),(4,1),(2,2),(8,2),(16,4),(32,4)]
                asymmetric=impossible+[(1,1)]
                for items,enabled in ((impossible,1),(asymmetric,0),(roots,1),(impossible,1)):
                    r=self.verify(4,2,3,items,p,c)
                    base=old.produce(Packed(6,3,items),checker=c)
                    self.assertEqual(r['proof_bytes'],base['proof_bytes'])
                    self.assertEqual(r['symmetry_stats']['enabled'],enabled)
                    self.assertEqual(r['symmetry_stats']['asymmetric_fallback'],1-enabled)
                    self.assertEqual(r['symmetry_stats']['representatives'],10 if enabled else 16)
                    self.assertEqual(r['symmetry_stats']['aliases'],6 if enabled else 0)
                    self.assertEqual(r['symmetry_stats']['workspace_bytes'],132)
                r=self.verify(4,2,3,impossible,p,c)
                self.assertEqual(r['multiplier_stats']['certified_branches'],10)
                self.assertEqual(r['symmetry_stats']['affine_copies'],6)
                self.assertEqual(r['symmetry_stats']['affine_copy_words'],24)
                # All fixed pairs are roots at y=0, including diagonals and
                # off-diagonal pairs whose roots must be expanded exactly once.
                r=self.verify(4,2,3,[(16,1),(32,2)],p,c)
                self.assertEqual(r['roots'],list(range(16)))
                self.assertEqual(r['symmetry_stats']['copied_roots'],6)

    def test_copy_budget_fallback_and_root_limit_during_expansion(self):
        items=[(4,1),(8,2),(12,4),(0,4)]
        with Producer(2,2,3,copy_budget_test=True) as p, Checker(2,2,3) as c:
            r=self.verify(2,2,3,items,p,c)
            self.assertEqual(r['symmetry_stats']['copy_budget_skips'],1)
            self.assertEqual(r['symmetry_stats']['affine_copies'],0)
            self.assertEqual(r['certificate']['stats']['assignments'],4)
        # More than 256 roots after representative expansion must never
        # return a partial answer, including repeated calls on this workspace.
        with Producer(8,1,1) as p:
            for _ in range(2):
                with self.assertRaises(Inconclusive) as caught:p.produce(Packed(9,1,[]))
                self.assertGreater(caught.exception.symmetry_stats['aliases'],0)
                self.assertGreater(caught.exception.symmetry_stats['copied_roots'],0)

    def test_concurrent_calls_and_closed_handles(self):
        p = Packed(3,3,[(2,1),(4,2),(6,4),(0,4)])
        with Producer(1,2,3) as producer, Checker(1,2,3) as checker:
            with ThreadPoolExecutor(max_workers=3) as pool:
                answers = list(pool.map(lambda _: producer.produce(p,checker=checker),range(12)))
            self.assertTrue(all(a['certificate']['verified'] for a in answers))
            self.assertTrue(all(a['proof_bytes']==answers[0]['proof_bytes'] for a in answers))
        with self.assertRaises(RuntimeError): producer.produce(p)
        with self.assertRaises(RuntimeError): checker.evaluate(p,0)

# Preserve the previous API's resource, invalid-input, incomplete-root and
# Boolean-basis controls. Only the expected proof accounting changes.
import importlib.util
sys.path.insert(0,str(HERE.parent/'round32'))
_spec=importlib.util.spec_from_file_location('deferred_legacy_controls',HERE.parent/'round32/test_certificates.py')
_controls=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_controls)
_controls.Producer,_controls.Checker=Producer,Checker


class InheritedCertificates(_controls.CertificateTests):
    def check(self,x,y,equations,items,*,backend='cpu',sanitizer=False):
        with Producer(x,y,equations,backend=backend,sanitizer=sanitizer) as p, Checker(x,y,equations,sanitizer=sanitizer) as c:
            a=DeferredTests.verify(self,x,y,equations,items,p,c)
        self.assertEqual(a['certificate']['stats']['contradictions'],
                         (1<<x)-a['stats']['consistent']+a['multiplier_stats']['certified_branches']+a['symmetry_stats']['affine_copies'])
        self.assertEqual(a['certificate']['stats']['assignments'],
                         a['certificate']['stats']['enumerated_branches']*(1<<y))
        return a

    def test_spurious_lift_roots_and_high_nullity_fallback(self):
        a=self.check(1,2,3,[(2,1),(4,2),(6,4),(0,4)])
        self.assertEqual(a['roots'],[])
        self.assertEqual(a['certificate']['stats']['extended_contradictions'],2)
        self.assertEqual(a['certificate']['stats']['assignments'],0)
        a=self.check(2,4,1,[(3,1),(4|8,1)])
        self.assertGreater(a['stats']['fallback_branches'],0)


@unittest.skipUnless(os.environ.get('QUADRATIC_TEST_METAL')=='1','Metal not requested')
class InheritedMetalCertificates(InheritedCertificates):
    def check(self,x,y,equations,items,*,backend='cpu',sanitizer=False):
        if sanitizer:return super().check(x,y,equations,items,sanitizer=True)
        a=super().check(x,y,equations,items,backend='metal')
        self.assertEqual(a['stats']['gpu_used'],int(equations<=32 and y*(y+1)//2<=31))
        return a


if __name__ == '__main__':
    unittest.main()
