"""Valid external tagged records beyond the producer's strict partial-rank path."""
import sys
from pathlib import Path
import unittest

from adapter import producer as candidate
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'round44'))
from tagged_reference import TAG, certify_roots


class ExternalTaggedTests(unittest.TestCase):
    def check_external(self, inconsistent):
        for sanitizer in (False, True):
            for equations, positions in ((4, (0, 1, 2, 3)), (128, (0, 63, 64, 127))):
                witnesses = [1 << bit for bit in positions]
                constant = witnesses[0] | witnesses[2]
                terms = [(4 << i, witnesses[i]) for i in range(3)] + [(0, constant)]
                if inconsistent:
                    terms[-1] = (0, constant | witnesses[3])
                else:
                    witnesses[3] = 0
                packed = candidate.Packed(5, equations, terms)
                limbs = (equations + 63) // 64
                words = [0] * (4 * limbs)
                for branch in range(4):
                    words.append(TAG | branch)
                    for witness in witnesses:
                        words.extend((witness >> (64 * limb)) & ((1 << 64) - 1) for limb in range(limbs))
                raw = bytes((candidate.U64 * len(words))(*words))
                with candidate.Producer(2, 3, equations, sanitizer=sanitizer) as producer, candidate.Checker(2, 3, equations, sanitizer=sanitizer) as checker:
                    answer = producer.produce(packed)
                    checked = checker.certify(packed, answer['roots'], answer['basis'], raw)
                self.assertTrue(checked['verified'], checked)
                expected = [] if inconsistent else [20, 21, 22, 23]
                self.assertEqual(answer['roots'], expected)
                self.assertEqual(checked['partial_stats']['records'], 4)
                self.assertEqual(checked['partial_stats']['rank_sum'], 12)
                self.assertEqual(checked['partial_stats']['inconsistent'], 4 if inconsistent else 0)
                self.assertEqual(checked['stats']['assignments'], 0 if inconsistent else 4)
                reference = certify_roots(2, 3, equations, tuple(tuple(v) for v in terms), raw, sys.byteorder)
                self.assertEqual(list(reference[0]), expected)
                self.assertEqual(sum(row[1] for row in reference[3]), 12)
                self.assertEqual(sum(row[2] for row in reference[3]), 4 if inconsistent else 0)

    def test_full_rank_external_certificate(self):
        self.check_external(False)

    def test_inconsistent_external_certificate(self):
        self.check_external(True)


if __name__ == '__main__':
    unittest.main()
