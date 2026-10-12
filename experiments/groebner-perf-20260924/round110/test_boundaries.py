"""Packed-input limb boundaries and independently rejected forged seed math."""
import ctypes as C
import unittest
from native import Native, SeededStats, abi
from query import Query


class BoundaryTests(unittest.TestCase):
    def test_zero_duplicate_multi_limb_and_invalid_padding(self):
        for sanitized in (False, True):
            native, checker = Native(sanitized), Query(sanitizer=sanitized, arm='f4-quotient')
            seed = abi.ProofOwner(64, [], dict(version=1, nvars=64, order='grevlex-x0-first', nodes=[], outputs=[]))
            # Equations 0 and 64 are x63+1. Duplicate x0 coefficients cancel;
            # the zero column must still consume raw-scan work.
            masks = (abi.U64*5)(0, 1 << 63, 1, 1, 2)
            bits = (abi.U64*10)(1, 1, 1, 1, 1, 0, 1, 0, 0, 0)
            packed = abi.PackedInput(64, 65, 5, masks, bits)
            stats = SeededStats()
            handle = native.lib.seeded_produce(C.byref(packed), C.byref(seed.view), 1000000, 10000, 100, 8, 0, C.byref(stats))
            try:
                self.assertTrue(handle)
                self.assertEqual(stats.status, 0)
                self.assertEqual(stats.scan_work, 65+5*3+2*6)
                cert = checker._check(packed, native.lib.seeded_view(handle).contents, 1000000, 10000)
                self.assertTrue(cert['verified'])
            finally:
                if handle: native.lib.seeded_destroy(handle)
            bits[1] = 2 # Invalid padding beyond equation 64.
            stats = SeededStats()
            handle = native.lib.seeded_produce(C.byref(packed), C.byref(seed.view), 1000000, 10000, 100, 8, 0, C.byref(stats))
            self.assertFalse(handle)
            self.assertEqual(stats.status, 1)
            self.assertGreater(stats.scan_work, 0)

    def test_forged_seed_candidate_rejected_and_borrowed_inputs_survive(self):
        for sanitized in (False, True):
            native, checker = Native(sanitized), Query(sanitizer=sanitized, arm='f4-quotient')
            packed = abi.InputOwner(2, 1, {1: 1})
            # Claims that the constant one is the original polynomial x0.
            seed = abi.ProofOwner(2, [[0]], dict(version=1, nvars=2, order='grevlex-x0-first', nodes=[['input', 0]], outputs=[0]))
            before = bytes(packed.masks), bytes(packed.coefficients), bytes(seed.nodes), bytes(seed.terms)
            stats = SeededStats()
            handle = native.lib.seeded_produce(C.byref(packed.view), C.byref(seed.view), 100000, 1000, 100, 8, 0, C.byref(stats))
            try:
                self.assertTrue(handle)
                self.assertEqual(stats.status, 0) # Candidate production is not certification.
                cert = checker._check(packed.view, native.lib.seeded_view(handle).contents, 1000000, 10000)
                self.assertFalse(cert['verified'])
            finally:
                if handle: native.lib.seeded_destroy(handle)
            self.assertEqual(before, (bytes(packed.masks), bytes(packed.coefficients), bytes(seed.nodes), bytes(seed.terms)))


if __name__ == '__main__':
    unittest.main()
