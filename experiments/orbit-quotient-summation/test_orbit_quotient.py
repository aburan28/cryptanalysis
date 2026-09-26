import unittest

from orbit_core import m3_truths, mobius_anf, model, planted_targets, quotient_basis


class OrbitQuotientTests(unittest.TestCase):
    def test_payload_basis_shape(self):
        self.assertEqual(len(quotient_basis(13, 4)), 4)
        self.assertEqual(len(quotient_basis(19, 6)), 6)

    def test_n13_reference(self):
        M = model(13, 4, 5475)
        self.assertEqual(M["r"], 2003)
        self.assertEqual(M["lam"], 89)
        self.assertEqual(len(M["keys"]), 7)
        self.assertEqual(len(M["H"]), 26)

        targets, _ = planted_targets(M, 3, 1, (0, 1, 2), 20260926)
        fixed, fs = m3_truths(M, targets, "fixed")
        orbit, os = m3_truths(M, targets, "orbit")
        self.assertEqual(fs[0]["positive_key_tuples"], 3)
        self.assertEqual(os[0]["positive_key_tuples"], 330)
        self.assertEqual(mobius_anf(fixed[0], 12)["degree"], 12)
        self.assertEqual(mobius_anf(orbit[0], 12)["degree"], 11)


if __name__ == "__main__":
    unittest.main()
