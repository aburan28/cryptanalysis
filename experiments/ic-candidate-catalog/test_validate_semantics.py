"""Negative controls for the metadata identity gate."""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

import validate_semantics as gate


DIRECTORY = Path(gate.__file__).resolve().parent
ROOT = DIRECTORY.parents[1] if DIRECTORY.name == "ic-candidate-catalog" else DIRECTORY.parents[2]
IS_CRYPTANALYSIS = DIRECTORY.name == "ic-candidate-catalog"


class SemanticValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "registry"
        (self.directory / "curve-links").mkdir(parents=True)
        for name in gate.PINNED:
            target = self.directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(DIRECTORY / name, target)

    def data(self):
        return yaml.safe_load((self.directory / "curves.yaml").read_text())

    def write_data(self, data):
        (self.directory / "curves.yaml").write_text(yaml.safe_dump(data, sort_keys=False))

    def test_committed_metadata_passes(self):
        self.assertEqual(gate.validate(ROOT), [])

    def test_curve_uid_must_match_exact_preimage(self):
        data = self.data()
        data["curves"]["toy13_kb1"]["curve"]["coefficients"]["a6"] = 0
        self.write_data(data)
        errors = []
        gate.validate_registry(self.directory, errors)
        self.assertTrue(any("EC1 curve ID does not match" in error for error in errors))
        self.assertTrue(any("full curve UID does not match" in error for error in errors))

    def test_unknown_trait_cannot_claim_zero(self):
        data = self.data()
        data["curves"]["ecc2k130_pb"]["trait_status"]["volcano_total_depth"]["value"] = 0
        self.write_data(data)
        errors = []
        gate.validate_registry(self.directory, errors)
        self.assertTrue(any("unmeasured needs value: null" in error for error in errors))

    def test_unverified_endomorphism_action_cannot_claim_eigenvalue(self):
        data = self.data()
        entry = data["curves"]["toy13_kb1"]
        entry["endomorphism"]["actions_status"] = "partial"
        entry["endomorphism"]["actions"]["tau"] = {
            "status": "proposed", "kind": "frobenius", "map_rule": "(x,y)->(x^2,y^2)",
            "map_artifact_ref": None, "map_sha256": None,
            "subgroup_eigenvalue_mod_r": 1, "proof_ref": None, "verification_ref": None}
        errors = []
        gate.check_endomorphism_actions(entry, ROOT, errors, "toy13")
        self.assertTrue(any("unverified action must have null" in error for error in errors))

    def test_verified_endomorphism_action_needs_proof_and_subgroup_action(self):
        data = self.data()
        entry = data["curves"]["toy13_kb1"]
        entry["endomorphism"]["actions_status"] = "partial"
        entry["endomorphism"]["actions"]["tau"] = {
            "status": "verified", "kind": "frobenius", "map_rule": "(x,y)->(x^2,y^2)",
            "map_artifact_ref": None, "map_sha256": None,
            "subgroup_eigenvalue_mod_r": entry["curve"]["r"],
            "proof_ref": None, "verification_ref": None}
        errors = []
        gate.check_endomorphism_actions(entry, ROOT, errors, "toy13")
        self.assertTrue(any("eigenvalue modulo" in error for error in errors))
        self.assertTrue(any("existing proof_ref" in error for error in errors))

    def scalar_item(self):
        data = yaml.safe_load((DIRECTORY / "curves.yaml").read_text())
        entry = data["curves"]["toy13_kb1"]
        sha = "a" * 64
        item = {"field": entry["field"], "curve": entry["curve"],
                "implementation": {"sources_sha256": {"reference": sha}},
                "scalar_multiplication": {
                    "schema_version": 1, "coverage": "all_executed_scalar_multiplications",
                    "uses": [{
                        "role": "relation_query", "point_kind": "fixed_base",
                        "method": "double_and_add", "algorithm_ref": "reference binary method",
                        "endomorphism_action_ref": None,
                        "recoding": {"kind": "binary", "window": None,
                                     "decomposition_ref": None, "parameters": {}},
                        "arithmetic": {"coordinates": "affine", "field_backend": "reference",
                                       "inversion_rule": "per group addition"},
                        "precomputation": {"scope": "none", "table_entries": 0,
                                           "cache_key_rule": None},
                        "selection": {"mode": "explicit", "curve_uid": entry["curve_uid"],
                                      "subgroup_order": entry["curve"]["r"],
                                      "eligibility_rule": "all subgroup scalars",
                                      "resolved_backend_required": True},
                        "fallback": "none",
                        "implementation": {"entry_point": "reference", "source_sha256": sha,
                                           "flags": []},
                        "timing_behavior": "variable_time", "timing_evidence_sha256": None
                    }]}}
        return item, {entry["curve_uid"]: entry}

    @unittest.skipUnless(IS_CRYPTANALYSIS, "IC1 candidates live in cryptanalysis")
    def test_scalar_policy_accepts_exact_unaccelerated_method(self):
        item, by_uid = self.scalar_item()
        errors = []
        gate.validate_scalar_multiplication(item, ROOT, by_uid, errors, "candidate")
        self.assertEqual(errors, [])

    @unittest.skipUnless(IS_CRYPTANALYSIS, "IC1 candidates live in cryptanalysis")
    def test_scalar_policy_rejects_unproved_endomorphism_and_wrong_subgroup(self):
        item, by_uid = self.scalar_item()
        use = item["scalar_multiplication"]["uses"][0]
        use["method"] = "tau_adic"
        use["endomorphism_action_ref"] = "tau"
        use["selection"]["subgroup_order"] += 1
        errors = []
        gate.validate_scalar_multiplication(item, ROOT, by_uid, errors, "candidate")
        self.assertTrue(any("exact curve and subgroup" in error for error in errors))
        self.assertTrue(any("verified action" in error for error in errors))
        self.assertTrue(any("decomposition rule" in error for error in errors))
        self.assertTrue(any("window of at least two" in error for error in errors))

    @unittest.skipUnless(IS_CRYPTANALYSIS, "IC1 candidates live in cryptanalysis")
    def test_runtime_dispatch_must_report_resolved_backend(self):
        item, by_uid = self.scalar_item()
        use = item["scalar_multiplication"]["uses"][0]
        use["selection"]["mode"] = "runtime_dispatch"
        use["selection"]["resolved_backend_required"] = False
        errors = []
        gate.validate_scalar_multiplication(item, ROOT, by_uid, errors, "candidate")
        self.assertTrue(any("resolved backend" in error for error in errors))
        self.assertTrue(any("portable fallback" in error for error in errors))

    @unittest.skipUnless(IS_CRYPTANALYSIS, "IC1 candidates live in cryptanalysis")
    def test_fallback_cannot_hide_unproved_endomorphism_method(self):
        item, by_uid = self.scalar_item()
        item["scalar_multiplication"]["uses"][0]["fallback"] = {
            "method": "glv", "trigger": "backend unavailable",
            "implementation_sha256": "a" * 64}
        errors = []
        gate.validate_scalar_multiplication(item, ROOT, by_uid, errors, "candidate")
        self.assertTrue(any("/fallback:" in error for error in errors))

    def test_verified_link_needs_real_endpoint_and_map(self):
        data = self.data()
        errors = []
        by_uid, _, _ = gate.validate_registry(self.directory, errors)
        uid = next(iter(by_uid))
        link = {"schema_version": 1, "kind": "twist", "status": "verified",
                "source_curve_uid": uid, "target_curve_uid": None,
                "map_artifact_ref": None, "map_sha256": None, "proof_refs": [],
                "subgroup_transport": {"status": "unknown", "evidence_ref": None},
                "twist": {"twist_kind": "quadratic", "twist_parameter": None,
                          "extension_degree": None, "extension_isomorphism_ref": None}}
        (self.directory / "curve-links" / ("0" * 64 + ".json")).write_text(json.dumps(link))
        gate.validate_links(self.directory, by_uid, errors)
        self.assertTrue(any("verified link needs target curve UID" in error for error in errors))
        self.assertTrue(any("verified link needs map and proof" in error for error in errors))

    def test_proposed_link_has_stable_content_address(self):
        data = self.data()
        entry = data["curves"]["toy13_kb1"]
        link = {"schema_version": 1, "kind": "twist", "status": "proposed",
                "source_curve_uid": entry["curve_uid"], "target_curve_uid": None,
                "map_artifact_ref": None, "map_sha256": None, "proof_refs": [],
                "subgroup_transport": {"status": "unknown", "evidence_ref": None},
                "twist": {"twist_kind": "quadratic", "twist_parameter": "0x3",
                          "extension_degree": 2, "extension_isomorphism_ref": None}}
        name = gate.digest(gate.link_identity_record(link)) + ".json"
        (self.directory / "curve-links" / name).write_text(json.dumps(link))
        entry["representation_links"]["twists"] = {
            "status": "partial", "scope": "one proposed quadratic class", "links": [name]}
        self.write_data(data)
        errors = []
        by_uid, _, _ = gate.validate_registry(self.directory, errors)
        gate.validate_links(self.directory, by_uid, errors)
        self.assertEqual(errors, [])
        link["twist"]["twist_parameter"] = "0x4"
        (self.directory / "curve-links" / name).write_text(json.dumps(link))
        errors = []
        gate.validate_links(self.directory, by_uid, errors)
        self.assertTrue(any("link filename disagrees" in error for error in errors))

    def test_peer_mirror_mismatch_fails(self):
        peer = Path(self.temp.name) / "peer"
        relative = "docs/curves/ic" if IS_CRYPTANALYSIS else "experiments/ic-candidate-catalog"
        for name in gate.PEER_FILES:
            target = peer / relative / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(DIRECTORY / name, target)
        (peer / relative / "curves.yaml").write_bytes(b"different")
        self.assertTrue(any("peer repository mirror differs" in error for error in gate.validate(ROOT, peer)))

    def test_evidence_path_cannot_escape_checkout(self):
        self.assertIsNone(gate.repo_artifact(ROOT, "../outside.json"))
        self.assertIsNone(gate.repo_artifact(ROOT, "/etc/passwd"))

    @unittest.skipUnless(IS_CRYPTANALYSIS, "isogeny graph and IC1 archives live in cryptanalysis")
    def test_wrong_volcano_direction_fails(self):
        errors = []
        _, by_ref, _ = gate.validate_registry(self.directory, errors)
        graph = json.loads((DIRECTORY / "isogeny_routes.json").read_text())
        graph["edges"][0]["direction"] = "ascending"
        (self.directory / "isogeny_routes.json").write_text(json.dumps(graph))
        gate.validate_routes(self.directory, by_ref, errors)
        self.assertTrue(any("direction disagrees with proved volcano levels" in error for error in errors))

    @unittest.skipUnless(IS_CRYPTANALYSIS, "IC1 archives live in cryptanalysis")
    def test_nominal_or_changed_base_count_cannot_keep_ic1_name(self):
        root = Path(self.temp.name) / "repo"
        candidate_dir = root / "experiments/ic-bench/candidates"
        candidate_dir.mkdir(parents=True)
        source = next((ROOT / "experiments/ic-bench/candidates").glob("IC1*.json"))
        candidate = copy.deepcopy(json.loads(source.read_text()))
        candidate["factor_base"]["actual_usable_point_count"] += 1
        (candidate_dir / source.name).write_text(json.dumps(candidate))
        archive = root / "experiments/fb-archive/index.csv"
        archive.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "experiments/fb-archive/index.csv", archive)
        errors = []
        gate.validate_candidates(root, {}, {}, errors)
        self.assertTrue(any("factor base is absent from archive" in error for error in errors))
        self.assertTrue(any("IC1 name disagrees" in error for error in errors))

    @unittest.skipUnless(IS_CRYPTANALYSIS, "IC1 archives live in cryptanalysis")
    def test_new_candidate_cannot_reuse_legacy_schema(self):
        root = Path(self.temp.name) / "repo"
        candidate_dir = root / "experiments/ic-bench/candidates"
        candidate_dir.mkdir(parents=True)
        source = next((ROOT / "experiments/ic-bench/candidates").glob("IC1*.json"))
        (candidate_dir / "new.json").write_bytes(source.read_bytes())
        errors = []
        gate.validate_candidates(root, {}, {}, errors)
        self.assertTrue(any("ic-candidate/1 is frozen" in error for error in errors))

    @unittest.skipUnless(IS_CRYPTANALYSIS, "IC1 archives live in cryptanalysis")
    def test_v2_candidate_policy_participates_in_identity(self):
        root = Path(self.temp.name) / "repo"
        candidate_dir = root / "experiments/ic-bench/candidates"
        candidate_dir.mkdir(parents=True)
        catalog = root / "experiments/ic-candidate-catalog"
        catalog.mkdir(parents=True)
        shutil.copyfile(DIRECTORY / "scalar-multiplication.schema.json",
                        catalog / "scalar-multiplication.schema.json")
        source = next((ROOT / "experiments/ic-bench/candidates").glob("IC1N13*.json"))
        candidate = json.loads(source.read_text())
        scalar_item, by_uid = self.scalar_item()
        candidate["schema"] = "ic-candidate/2"
        candidate["field"] = scalar_item["field"]
        candidate["curve"] = dict(scalar_item["curve"])
        candidate["curve"]["curve_id"] = next(iter(by_uid.values()))["curve_id"]
        candidate["scalar_multiplication"] = scalar_item["scalar_multiplication"]
        candidate["implementation"]["sources_sha256"]["reference"] = "a" * 64
        base = candidate["factor_base"]
        base["curve_id"] = candidate["curve"]["curve_id"]
        base["enumerated_set_sha256"] = "b" * 64
        archive = root / "experiments/fb-archive/index.csv"
        archive.parent.mkdir(parents=True)
        archive.write_text("curve_id,enumerated_set_sha256,fb_points\n"
                           f"{base['curve_id']},{base['enumerated_set_sha256']},"
                           f"{base['actual_usable_point_count']}\n")
        stem = (f"IC1N13Ckb1fb{base['actual_usable_point_count']}"
                f"PDP3xlRCsampleLAgaussTDpdpISO0h{gate.digest(candidate)[:12]}")
        path = candidate_dir / f"{stem}.json"
        path.write_text(json.dumps(candidate))
        errors = []
        gate.validate_candidates(root, {}, by_uid, errors)
        self.assertEqual(errors, [])
        candidate["scalar_multiplication"]["uses"][0]["recoding"]["kind"] = "wnaf"
        path.write_text(json.dumps(candidate))
        errors = []
        gate.validate_candidates(root, {}, by_uid, errors)
        self.assertTrue(any("IC1 name disagrees" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
