import copy
import json
import unittest
from pathlib import Path

from validate_volcano_manifest import validate_files, validate_records


HERE = Path(__file__).resolve().parent


class VolcanoManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routes = json.loads((HERE / "isogeny_routes.json").read_text())
        cls.profile = json.loads((HERE / "volcano_profiles_20261008.json").read_text())

    def test_pinned_import_and_verified_route(self):
        self.assertEqual(validate_files(HERE / "isogeny_routes.json"),
                         {"curves": 2, "verified_edges": 1, "verified_routes": 1})

    def test_wrong_endomorphism_level_is_refused(self):
        routes = copy.deepcopy(self.routes)
        routes["curve_nodes"][1]["proved_volcano_levels"]["263"] = 0
        with self.assertRaisesRegex(ValueError, "proved levels disagree"):
            validate_records(routes, self.profile)

    def test_unverified_reachability_is_refused(self):
        routes = copy.deepcopy(self.routes)
        routes["curve_nodes"][1]["volcano_position"]["reachable_via"] = "search_l3_ecc2k130"
        with self.assertRaisesRegex(ValueError, "missing verified route"):
            validate_records(routes, self.profile)

    def test_changed_profile_depth_is_refused(self):
        profile = copy.deepcopy(self.profile)
        profile["rungs"]["131"]["f_factorization"]["263"] = 2
        with self.assertRaisesRegex(ValueError, "factorization mismatch"):
            validate_records(self.routes, profile)


if __name__ == "__main__":
    unittest.main()
