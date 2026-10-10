import unittest

from p256_isogeny_search.registry import load_candidates


class RegistryTests(unittest.TestCase):
    def test_root_and_toy_registries_validate(self):
        root = load_candidates("data/candidates/p256-root.json")[0]
        toy = load_candidates("data/candidates/toy.json")[0]
        self.assertEqual(root.candidate_id, "p256-root")
        self.assertEqual(root.path, ())
        self.assertEqual(toy.n, 9851)


if __name__ == "__main__":
    unittest.main()
