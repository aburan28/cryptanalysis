"""Integrity gates for the generated proposal catalog and isogeny links."""

import copy
import unittest

import generate


class CatalogTests(unittest.TestCase):
    def test_exact_count_and_no_unearned_results(self):
        profiles = generate.load_json("profiles.json")["profiles"]
        routes = generate.validate_routes(generate.load_json("isogeny_routes.json"))
        generate.validate_profiles(profiles, routes)
        rows = generate.proposals(profiles, routes)
        self.assertEqual(len(rows), 1000)
        self.assertEqual(sum(row["isogeny_route_ref"] != "none" for row in rows), 200)
        self.assertTrue(all(row["candidate_id"] is None and row["measured_cost"] is None
                            for row in rows))
        self.assertTrue(all("explicit_isogeny_map_missing" in row["activation_blockers"]
                            for row in rows if row["isogeny_route_ref"] != "none"))

    def test_search_record_cannot_masquerade_as_verified_route(self):
        graph = generate.load_json("isogeny_routes.json")
        forged = copy.deepcopy(graph)
        route = next(r for r in forged["routes"] if r["id"] == "search_l2_ecc2k130")
        route["status"] = "verified"
        with self.assertRaises(AssertionError):
            generate.validate_routes(forged)

    def test_verified_route_requires_map_and_contiguous_edges(self):
        graph = generate.load_json("isogeny_routes.json")
        graph["curve_nodes"].extend([{"ref": "middle"}, {"ref": "target"}])
        graph["edges"] = [
            {"id": "e1", "status": "verified", "source_curve_ref": "ecc2k130/polynomial-basis-131",
             "target_curve_ref": "middle", "degree": 2, "explicit_map_sha256": "a" * 64,
             "map_artifact_ref": "map1", "kernel_certificate_sha256": "b" * 64,
             "subgroup_transport_certificate_sha256": "c" * 64},
            {"id": "e2", "status": "verified", "source_curve_ref": "middle",
             "target_curve_ref": "target", "degree": 3, "explicit_map_sha256": "d" * 64,
             "map_artifact_ref": "map2", "kernel_certificate_sha256": "e" * 64,
             "subgroup_transport_certificate_sha256": "f" * 64},
        ]
        graph["routes"].append({"id": "tested", "status": "verified",
                                "source_curve_ref": "ecc2k130/polynomial-basis-131",
                                "target_curve_ref": "target", "edge_ids": ["e1", "e2"],
                                "search_prime": None})
        generate.validate_routes(graph)
        graph["edges"][1]["source_curve_ref"] = "ecc2k130/polynomial-basis-131"
        with self.assertRaises(AssertionError):
            generate.validate_routes(graph)


if __name__ == "__main__":
    unittest.main()
