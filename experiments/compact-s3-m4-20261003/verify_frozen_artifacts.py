#!/usr/bin/env python3
"""Check source, solver logs, and gzip XCNF archives against frozen receipts."""

import base64
import gzip
import hashlib
import json
import math
from pathlib import Path

from run_probe import HERE, sha, field


def verify():
    protocol_digest = sha(HERE / "protocol.json")
    rows = []
    for n in (53, 83):
        for kind in ("planted", "ordinary"):
            baseline_path = HERE / "runs" / f"n{n}_{kind}_frozen.json"
            for variant in ("frozen", "factored", "multitarget"):
                stem = f"n{n}_{kind}_{variant}"
                receipt_path = HERE / "runs" / f"{stem}.json"
                receipt = json.loads(receipt_path.read_text())
                assert receipt["protocol_sha256"] == protocol_digest
                assert len(receipt["attempts"]) == 1
                if variant == "frozen":
                    assert receipt["solver_source_sha256"] == sha(
                        HERE / "chain_s3.py")
                    assert receipt["runner_source_sha256"] == sha(
                        HERE / "run_probe.py")
                elif variant == "factored":
                    assert receipt["matched_baseline_receipt_sha256"] == sha(
                        baseline_path)
                    assert receipt["core_formula_source_sha256"] == sha(
                        HERE / "chain_s3.py")
                    assert receipt["solver_source_sha256"] == sha(
                        HERE / "chain_s3_factored.py")
                    assert receipt["wrapper_source_sha256"] == sha(
                        HERE / "run_factored_probe.py")
                else:
                    coset_path = HERE / "runs" / (
                        f"n{n}_{kind}_raw_preimages.json")
                    assert receipt["matched_baseline_receipt_sha256"] == sha(
                        baseline_path)
                    assert receipt["raw_preimage_receipt_sha256"] == sha(
                        coset_path)
                    assert receipt["multitarget_source_sha256"] == sha(
                        HERE / "chain_s3_multitarget.py")
                    assert receipt["factored_source_sha256"] == sha(
                        HERE / "chain_s3_factored.py")
                    assert receipt["core_source_sha256"] == sha(
                        HERE / "chain_s3.py")
                    assert receipt["runner_source_sha256"] == sha(
                        HERE / "run_multitarget_probe.py")
                formula_digest = hashlib.sha256()
                formula_bytes = 0
                with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
                    for chunk in iter(lambda: stream.read(1 << 20), b""):
                        formula_digest.update(chunk)
                        formula_bytes += len(chunk)
                assert formula_digest.hexdigest() == receipt["xcnf_sha256"]
                assert formula_bytes == receipt["xcnf_bytes"]
                for attempt in receipt["attempts"]:
                    index = attempt["index"]
                    assert sha(HERE / "runs" / f"{stem}.attempt{index}.stdout.txt") == (
                        attempt["solver_stdout_sha256"])
                    assert sha(HERE / "runs" / f"{stem}.attempt{index}.stderr.txt") == (
                        attempt["solver_stderr_sha256"])
                    if variant == "multitarget":
                        assert attempt["xcnf_sha256"] == receipt["xcnf_sha256"]
                rows.append({"n": n, "kind": kind, "variant": variant,
                             "receipt_sha256": sha(receipt_path),
                             "formula_sha256": formula_digest.hexdigest(),
                             "formula_bytes": formula_bytes,
                             "attempt_count": len(receipt["attempts"])})
    for stem, source in (("n53_ordinary_multitarget_extended",
                          "run_extended_multitarget.py"),
                         ("n83_ordinary_multitarget_conflict_meter",
                          "meter_n83_multitarget.py")):
        path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(path.read_text())
        assert receipt["runner_source_sha256"] == sha(HERE / source)
        assert receipt["stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.stdout.txt")
        assert receipt["stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.stderr.txt")
        rows.append({"variant": stem, "receipt_sha256": sha(path),
                     "formula_sha256": receipt["formula_sha256"]})
    for kind in ("planted", "ordinary"):
        stem = f"n53_{kind}_rational"
        path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(path.read_text())
        support_path = HERE / "bases/n53_weight3_nonrational_supports.json.gz"
        with gzip.open(support_path, "rt") as stream:
            support = json.load(stream)
        assert support["source_sha256"] == sha(
            HERE / "enumerate_rational_supports.py")
        packed_supports = base64.b64decode(
            support["nonrational_supports_base64"], validate=True)
        assert hashlib.sha256(packed_supports).hexdigest() == support[
            "nonrational_supports_sha256"]
        assert receipt["proposal_id"] == "Q1308"
        assert receipt["protocol_sha256"] == protocol_digest
        assert receipt["rational_filter_source_sha256"] == sha(
            HERE / "chain_s3_rational.py")
        assert receipt["rational_support_archive_sha256"] == sha(support_path)
        assert receipt["wrapper_source_sha256"] == sha(
            HERE / "run_rational_probe.py")
        assert receipt["runner_source_sha256"] == sha(
            HERE / "run_multitarget_probe.py")
        formula_digest = hashlib.sha256()
        formula_bytes = 0
        with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                formula_digest.update(chunk)
                formula_bytes += len(chunk)
        assert formula_digest.hexdigest() == receipt["xcnf_sha256"]
        assert formula_bytes == receipt["xcnf_bytes"]
        assert len(receipt["attempts"]) == 1
        attempt = receipt["attempts"][0]
        assert sha(HERE / "runs" / f"{stem}.attempt0.stdout.txt") == (
            attempt["solver_stdout_sha256"])
        assert sha(HERE / "runs" / f"{stem}.attempt0.stderr.txt") == (
            attempt["solver_stderr_sha256"])
        rows.append({"variant": stem, "receipt_sha256": sha(path),
                     "formula_sha256": formula_digest.hexdigest(),
                     "formula_bytes": formula_bytes})
    rational_control_path = HERE / "runs/n53_ordinary_rational_locked_verify.json"
    rational_control = json.loads(rational_control_path.read_text())
    assert rational_control["source_sha256"] == sha(
        HERE / "verify_rational_witness.py")
    assert rational_control["stage_receipt_sha256"] == sha(
        HERE / "runs/n53_ordinary_rational.json")
    assert rational_control["relation"] is not None
    rows.append({"variant": "n53_ordinary_rational_locked_verify",
                 "receipt_sha256": sha(rational_control_path)})
    for stem in ("n53_planted_multitarget_locked_verify",
                 "n53_ordinary_multitarget_locked_verify",
                 "n83_planted_multitarget_locked_verify"):
        path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(path.read_text())
        assert receipt["source_sha256"] == sha(
            HERE / "verify_multitarget_witness.py")
        assert receipt["relation"] is not None
        rows.append({"variant": stem, "receipt_sha256": sha(path)})
    for n in (53, 83):
        for kind in ("planted", "ordinary"):
            baseline_path = HERE / "runs" / f"n{n}_{kind}_frozen.json"
            coset_path = HERE / "runs" / f"n{n}_{kind}_raw_preimages.json"
            for variant in ("orbit", "ordered"):
                stem = f"n{n}_{kind}_{variant}"
                path = HERE / "runs" / f"{stem}.json"
                receipt = json.loads(path.read_text())
                assert receipt["protocol_sha256"] == protocol_digest
                assert receipt["matched_baseline_receipt_sha256"] == sha(
                    baseline_path)
                assert receipt["raw_preimage_receipt_sha256"] == sha(
                    coset_path)
                assert receipt["target_orbit_x_count"] == (
                    receipt["cofactor"] * n)
                assert receipt["orbit_source_sha256"] == sha(
                    HERE / "chain_s3_orbit.py")
                assert receipt["multitarget_source_sha256"] == sha(
                    HERE / "chain_s3_multitarget.py")
                assert receipt["factored_source_sha256"] == sha(
                    HERE / "chain_s3_factored.py")
                assert receipt["core_source_sha256"] == sha(
                    HERE / "chain_s3.py")
                runner = ("run_orbit_probe.py" if variant == "orbit"
                          else "run_ordered_probe.py")
                assert receipt["runner_source_sha256"] == sha(HERE / runner)
                if variant == "ordered":
                    assert receipt["ordered_source_sha256"] == sha(
                        HERE / "chain_s3_ordered.py")
                assert len(receipt["attempts"]) == 1
                assert receipt["verified_relation"] is None
                digest = hashlib.sha256()
                size = 0
                with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
                    for chunk in iter(lambda: stream.read(1 << 20), b""):
                        digest.update(chunk)
                        size += len(chunk)
                assert digest.hexdigest() == receipt["xcnf_sha256"]
                assert size == receipt["xcnf_bytes"]
                for attempt in receipt["attempts"]:
                    index = attempt["index"]
                    assert attempt["xcnf_sha256"] == receipt["xcnf_sha256"]
                    assert sha(HERE / "runs" / f"{stem}.attempt{index}.stdout.txt") == (
                        attempt["solver_stdout_sha256"])
                    assert sha(HERE / "runs" / f"{stem}.attempt{index}.stderr.txt") == (
                        attempt["solver_stderr_sha256"])
                rows.append({"variant": stem, "receipt_sha256": sha(path),
                             "formula_sha256": digest.hexdigest(),
                             "formula_bytes": size})
    extended_path = HERE / "runs/n53_ordinary_orbit_extended.json"
    extended = json.loads(extended_path.read_text())
    assert extended["runner_source_sha256"] == sha(
        HERE / "run_extended_orbit.py")
    assert extended["matched_stage_receipt_sha256"] == sha(
        HERE / "runs/n53_ordinary_orbit.json")
    assert extended["formula_sha256"] == json.loads(
        (HERE / "runs/n53_ordinary_orbit.json").read_text())["xcnf_sha256"]
    assert extended["stdout_sha256"] == sha(
        HERE / "runs/n53_ordinary_orbit_extended.stdout.txt")
    assert extended["stderr_sha256"] == sha(
        HERE / "runs/n53_ordinary_orbit_extended.stderr.txt")
    assert extended["verified_relation"] is None
    rows.append({"variant": "n53_ordinary_orbit_extended",
                 "receipt_sha256": sha(extended_path)})
    for variant in ("orbit", "ordered"):
        source = ("verify_orbit_witness.py" if variant == "orbit"
                  else "verify_ordered_witness.py")
        for n, kind in ((53, "ordinary"), (53, "planted"), (83, "planted")):
            stem = f"n{n}_{kind}_{variant}_locked_verify"
            path = HERE / "runs" / f"{stem}.json"
            receipt = json.loads(path.read_text())
            assert receipt["source_sha256"] == sha(HERE / source)
            assert receipt["matched_" + variant + "_receipt_sha256"] == sha(
                HERE / "runs" / f"n{n}_{kind}_{variant}.json")
            assert receipt["status"] == "verified_locked_sat_relation_mapped_back"
            assert receipt["frobenius_shift"] == 1
            rows.append({"variant": stem, "receipt_sha256": sha(path)})
    for stem in ("n53_ordinary_known_preimage_fixed",
                 "n83_planted_raw_target_fixed"):
        path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(path.read_text())
        n = receipt["n"]
        kind = "ordinary" if n == 53 else "planted"
        assert receipt["candidate_id"] is None
        assert receipt["workload_id"] is None
        assert receipt["is_natural_relation_yield_measurement"] is False
        assert receipt["oracle_assisted_raw_target_selection"] == (n == 53)
        assert receipt["baseline_receipt_sha256"] == sha(
            HERE / "runs" / f"n{n}_{kind}_frozen.json")
        assert receipt["coset_receipt_sha256"] == sha(
            HERE / "runs" / f"n{n}_{kind}_raw_preimages.json")
        witness = ("n53_ordinary_raw_pair_witness.json" if n == 53
                   else f"n{n}_{kind}_frozen.json")
        assert receipt["witness_receipt_sha256"] == sha(
            HERE / "runs" / witness)
        assert receipt["runtime_info_sha256"] == sha(
            HERE / "fixed_sage_runtime_info.json")
        assert receipt["core_source_sha256"] == sha(HERE / "chain_s3.py")
        assert receipt["factored_source_sha256"] == sha(
            HERE / "chain_s3_factored.py")
        assert receipt["runner_source_sha256"] == sha(
            HERE / "run_fixed_witness_target.py")
        assert receipt["solver_binary_sha256"] == sha(
            Path("/opt/homebrew/bin/cryptominisat5"))
        assert receipt["stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.stdout.txt")
        assert receipt["stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.stderr.txt")
        assert receipt["status"] == "censored"
        assert receipt["verified_relation"] is None
        assert receipt["locked_control"]["status"] == (
            "locked_sat_verified_relation")
        assert receipt["locked_control"]["relation"] is not None
        digest = hashlib.sha256()
        size = 0
        with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
                size += len(chunk)
        assert digest.hexdigest() == receipt["xcnf_sha256"]
        assert size == receipt["xcnf_bytes"]
        rows.append({"variant": stem, "receipt_sha256": sha(path),
                     "formula_sha256": digest.hexdigest(),
                     "formula_bytes": size})
    for n, kind in ((53, "ordinary"), (83, "planted"),
                    (83, "ordinary")):
        stem = f"n{n}_{kind}_exact_base_orbit"
        path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(path.read_text())
        baseline_path = HERE / "runs" / f"n{n}_{kind}_frozen.json"
        baseline = json.loads(baseline_path.read_text())
        archive_path = HERE / "bases" / (
            f"n{n}_weight{3 if n == 53 else 4}_orbits.json.gz")
        assert receipt["proposal_id"] == ("Q1315" if n == 53 else "Q1316")
        assert receipt["candidate_id"] is None
        assert receipt["run_id"] is None
        assert receipt["complete_solve_work_log2"] is None
        assert receipt["workload_id"] == baseline["workload_id"]
        assert receipt["curve_id"] == baseline["curve_id"]
        assert receipt["public_target"] == baseline["public_subgroup_target"]
        assert receipt["factor_base_actual_B"] == baseline[
            "factor_base_actual_B"]
        assert receipt["factor_base_folded_columns"] == baseline[
            "factor_base_folded_columns"]
        assert receipt["factor_base_enumerated_set_sha256"] == baseline[
            "factor_base_enumerated_set_sha256"]
        assert receipt["base_archive_sha256"] == sha(archive_path)
        assert receipt["baseline_receipt_sha256"] == sha(baseline_path)
        assert receipt["protocol_sha256"] == protocol_digest
        assert receipt["runtime_info_sha256"] == sha(
            HERE / "base_orbit_sage_runtime_info.json")
        for key, source in (("core_source_sha256", "chain_s3.py"),
                            ("factored_source_sha256", "chain_s3_factored.py"),
                            ("orbit_source_sha256", "chain_s3_orbit.py"),
                            ("ordered_source_sha256", "chain_s3_ordered.py"),
                            ("base_orbit_source_sha256", "chain_s3_base_orbit.py"),
                            ("runner_source_sha256", "run_base_orbit_probe.py")):
            assert receipt[key] == sha(HERE / source)
        assert receipt["solver_binary_sha256"] == sha(
            Path(receipt["solver_command"][0]))
        assert receipt["solver_stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.stderr.txt")
        assert receipt["status"] in ("censored", "external_timeout", "sat")
        assert receipt["observed_verified_relation_count"] == int(
            receipt["verified_relation"] is not None)
        control = receipt["locked_control"]
        if kind == "planted" or n == 53:
            assert control["status"] == "locked_sat_verified_public_relation"
            assert control["relation"] is not None
            witness = ("n53_ordinary_matched_pair_table.json" if n == 53
                       else "n83_planted_frozen.json")
            assert control["witness_receipt_sha256"] == sha(
                HERE / "runs" / witness)
        else:
            assert control is None
        digest = hashlib.sha256()
        size = 0
        with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
                size += len(chunk)
        assert digest.hexdigest() == receipt["xcnf_sha256"]
        assert size == receipt["xcnf_bytes"]
        rows.append({"variant": stem, "receipt_sha256": sha(path),
                     "formula_sha256": digest.hexdigest(),
                     "formula_bytes": size,
                     "observed_verified_relation_count": receipt[
                         "observed_verified_relation_count"]})
    for kind in ("planted", "ordinary"):
        stem = f"n83_{kind}_projected_sparse"
        path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(path.read_text())
        baseline_path = HERE / "runs" / f"n83_{kind}_frozen.json"
        baseline = json.loads(baseline_path.read_text())
        archive_path = HERE / "bases/n83_weight4_orbits.json.gz"
        assert receipt["proposal_id"] == "Q1317"
        assert receipt["candidate_id"] is None
        assert receipt["run_id"] is None
        assert receipt["complete_solve_work_log2"] is None
        assert receipt["workload_id"] == baseline["workload_id"]
        assert receipt["curve_id"] == baseline["curve_id"]
        assert receipt["public_target"] == baseline["public_subgroup_target"]
        assert receipt["factor_base_actual_B"] == baseline[
            "factor_base_actual_B"]
        assert receipt["factor_base_folded_columns"] == baseline[
            "factor_base_folded_columns"]
        assert receipt["factor_base_enumerated_set_sha256"] == baseline[
            "factor_base_enumerated_set_sha256"]
        assert receipt["base_archive_sha256"] == sha(archive_path)
        assert receipt["baseline_receipt_sha256"] == sha(baseline_path)
        assert receipt["protocol_sha256"] == protocol_digest
        assert receipt["runtime_info_sha256"] == sha(
            HERE / "projected_sparse_sage_runtime_info.json")
        for key, source in (("core_source_sha256", "chain_s3.py"),
                            ("factored_source_sha256", "chain_s3_factored.py"),
                            ("projected_source_sha256",
                             "chain_s3_projected_sparse.py"),
                            ("base_probe_source_sha256",
                             "run_base_orbit_probe.py"),
                            ("runner_source_sha256",
                             "run_projected_sparse_probe.py")):
            assert receipt[key] == sha(HERE / source)
        assert receipt["solver_binary_sha256"] == sha(
            Path(receipt["solver_command"][0]))
        assert receipt["solver_stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.stderr.txt")
        assert receipt["status"] in ("censored", "external_timeout", "sat")
        assert receipt["observed_verified_relation_count"] == int(
            receipt["verified_relation"] is not None)
        control = receipt["locked_control"]
        if kind == "planted":
            assert control["status"] == "locked_sat_verified_public_relation"
            assert control["relation"] is not None
            assert control["witness_receipt_sha256"] == sha(
                HERE / "runs/n83_planted_frozen.json")
        else:
            assert control is None
        digest = hashlib.sha256()
        size = 0
        with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
                size += len(chunk)
        assert digest.hexdigest() == receipt["xcnf_sha256"]
        assert size == receipt["xcnf_bytes"]
        rows.append({"variant": stem, "receipt_sha256": sha(path),
                     "formula_sha256": digest.hexdigest(),
                     "formula_bytes": size,
                     "observed_verified_relation_count": receipt[
                         "observed_verified_relation_count"]})
    pin_variants = (
        ("n83_planted_projected_sparse_rawpin4", 0, "censored"),
        ("n83_planted_projected_sparse_leaf_x_pin", 0, "censored"),
        ("n83_planted_projected_sparse_leaf_x_mid1_pin", 1, "sat"),
        ("n83_planted_projected_sparse_full_pin", 2, "sat"),
    )
    for stem, mids_pinned, expected_status in pin_variants:
        path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(path.read_text())
        assert receipt["proposal_id"] == "Q1317"
        assert receipt["candidate_id"] is None
        assert receipt["workload_id"] is None
        assert receipt["run_id"] is None
        assert receipt["is_natural_relation_yield_measurement"] is False
        assert receipt["status"] == expected_status
        assert receipt["complete_solve_work_log2"] is None
        assert receipt["curve_id"] == json.loads((
            HERE / "runs/n83_planted_frozen.json").read_text())["curve_id"]
        assert receipt["baseline_receipt_sha256"] == sha(
            HERE / "runs/n83_planted_frozen.json")
        assert receipt["base_archive_sha256"] == sha(
            HERE / "bases/n83_weight4_orbits.json.gz")
        assert receipt["matched_unassisted_receipt_sha256"] == sha(
            HERE / "runs/n83_planted_projected_sparse.json")
        assert receipt["protocol_sha256"] == protocol_digest
        assert receipt["runtime_info_sha256"] == sha(
            HERE / "projected_sparse_sage_runtime_info.json")
        for key, source in (("core_source_sha256", "chain_s3.py"),
                            ("factored_source_sha256", "chain_s3_factored.py"),
                            ("projected_source_sha256",
                             "chain_s3_projected_sparse.py"),
                            ("base_probe_source_sha256",
                             "run_base_orbit_probe.py"),
                            ("stage_probe_source_sha256",
                             "run_projected_sparse_probe.py")):
            assert receipt[key] == sha(HERE / source)
        if stem.endswith("rawpin4"):
            assert receipt["pin_count"] == 4
            assert receipt["intermediate_x_coordinates_pinned"] is False
            assert receipt["projected_x_coordinates_pinned"] is False
            assert receipt["oracle_assisted_raw_leaf_choices"] is True
            source = "run_projected_sparse_pin.py"
        else:
            assert receipt["raw_leaf_count_pinned"] == 4
            assert receipt["projected_leaf_count_pinned"] == 4
            assert receipt["intermediate_x_count_pinned"] == mids_pinned
            assert receipt["oracle_assisted_raw_and_projected_leaves"] is True
            assert receipt["witness_receipt_sha256"] == sha(
                HERE / "runs/n83_planted_frozen.json")
            source = "run_projected_sparse_midfree.py"
        assert receipt["source_sha256"] == sha(HERE / source)
        assert receipt["solver_binary_sha256"] == sha(
            Path(receipt["solver_command"][0]))
        assert receipt["solver_stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.stderr.txt")
        assert (receipt["verified_relation"] is not None) == (
            expected_status == "sat")
        digest = hashlib.sha256()
        size = 0
        with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
                size += len(chunk)
        assert digest.hexdigest() == receipt["xcnf_sha256"]
        assert size == receipt["xcnf_bytes"]
        rows.append({"variant": stem, "receipt_sha256": sha(path),
                     "formula_sha256": digest.hexdigest(),
                     "formula_bytes": size})
    for stem, kind, links, pinned in (
            ("n83_planted_rooted1_rawpin4", "planted", 1, True),
            ("n83_planted_rooted2_rawpin4", "planted", 2, True),
            ("n83_ordinary_rooted2", "ordinary", 2, False)):
        path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(path.read_text())
        baseline_path = HERE / "runs" / f"n83_{kind}_frozen.json"
        baseline = json.loads(baseline_path.read_text())
        assert receipt["proposal_id"] == "Q1319"
        assert receipt["candidate_id"] is None
        assert receipt["run_id"] is None
        assert receipt["workload_id"] == (
            None if pinned else baseline["workload_id"])
        assert receipt["is_natural_relation_yield_measurement"] == (
            kind == "ordinary" and not pinned)
        assert receipt["oracle_assisted_raw_leaf_choices"] == pinned
        assert receipt["rooted_links"] == links
        assert receipt["curve_id"] == baseline["curve_id"]
        assert receipt["public_target"] == baseline["public_subgroup_target"]
        assert receipt["factor_base_actual_B"] == baseline[
            "factor_base_actual_B"]
        assert receipt["factor_base_folded_columns"] == baseline[
            "factor_base_folded_columns"]
        assert receipt["factor_base_enumerated_set_sha256"] == baseline[
            "factor_base_enumerated_set_sha256"]
        assert receipt["base_archive_sha256"] == sha(
            HERE / "bases/n83_weight4_orbits.json.gz")
        assert receipt["baseline_receipt_sha256"] == sha(baseline_path)
        assert receipt["protocol_sha256"] == protocol_digest
        assert receipt["runtime_info_sha256"] == sha(
            HERE / "projected_sparse_sage_runtime_info.json")
        assert receipt["complete_solve_work_log2"] is None
        assert receipt["observed_verified_relation_count"] == int(
            receipt["verified_relation"] is not None)
        for key, source in (("core_source_sha256", "chain_s3.py"),
                            ("factored_source_sha256", "chain_s3_factored.py"),
                            ("projected_source_sha256",
                             "chain_s3_projected_sparse.py"),
                            ("oracle_source_sha256", "s3_root_oracle.py"),
                            ("rooted_source_sha256", "chain_s3_rooted.py"),
                            ("base_probe_source_sha256",
                             "run_base_orbit_probe.py"),
                            ("stage_probe_source_sha256",
                             "run_projected_sparse_probe.py"),
                            ("runner_source_sha256", "run_rooted_probe.py")):
            assert receipt[key] == sha(HERE / source)
        assert receipt["solver_binary_sha256"] == sha(
            Path(receipt["solver_command"][0]))
        assert receipt["solver_stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.stderr.txt")
        if pinned:
            assert receipt["status"] == "censored"
            assert receipt["verified_relation"] is None
            control = receipt["locked_control"]
            assert control["status"] == "locked_sat_verified_public_relation"
            assert control["relation"] is not None
            assert control["witness_receipt_sha256"] == sha(baseline_path)
        else:
            assert receipt["locked_control"] is None
            assert receipt["status"] in ("censored", "external_timeout", "sat")
        digest = hashlib.sha256()
        size = 0
        with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
                size += len(chunk)
        assert digest.hexdigest() == receipt["xcnf_sha256"]
        assert size == receipt["xcnf_bytes"]
        rows.append({"variant": stem, "receipt_sha256": sha(path),
                     "formula_sha256": digest.hexdigest(),
                     "formula_bytes": size,
                     "observed_verified_relation_count": receipt[
                         "observed_verified_relation_count"]})
    for n, kind in ((53, "ordinary"), (83, "planted"),
                    (83, "ordinary")):
        stem = f"n{n}_{kind}_group_add"
        path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(path.read_text())
        baseline_path = HERE / "runs" / f"n{n}_{kind}_frozen.json"
        baseline = json.loads(baseline_path.read_text())
        archive_path = HERE / "bases" / (
            f"n{n}_weight{3 if n == 53 else 4}_orbits.json.gz")
        assert receipt["proposal_id"] == ("Q1320" if n == 53 else "Q1321")
        assert receipt["candidate_id"] is None
        assert receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["complete_solve_work_log2"] is None
        assert receipt["workload_id"] == baseline["workload_id"]
        assert receipt["curve_id"] == baseline["curve_id"]
        assert receipt["public_target"] == baseline["public_subgroup_target"]
        assert receipt["factor_base_actual_B"] == baseline[
            "factor_base_actual_B"]
        assert receipt["factor_base_folded_columns"] == baseline[
            "factor_base_folded_columns"]
        assert receipt["factor_base_enumerated_set_sha256"] == baseline[
            "factor_base_enumerated_set_sha256"]
        assert receipt["base_archive_sha256"] == sha(archive_path)
        assert receipt["baseline_receipt_sha256"] == sha(baseline_path)
        assert receipt["protocol_sha256"] == protocol_digest
        assert receipt["runtime_info_sha256"] == sha(
            HERE / "group_add_sage_runtime_info.json")
        for key, source in (("core_source_sha256", "chain_s3.py"),
                            ("group_add_source_sha256", "chain_group_add.py"),
                            ("base_orbit_source_sha256",
                             "chain_s3_base_orbit.py"),
                            ("base_probe_source_sha256",
                             "run_base_orbit_probe.py"),
                            ("probe_source_sha256", "run_probe.py"),
                            ("runner_source_sha256",
                             "run_group_add_probe.py")):
            assert receipt[key] == sha(HERE / source)
        if n == 83:
            assert receipt["projected_source_sha256"] == sha(
                HERE / "chain_s3_projected_sparse.py")
        else:
            assert receipt["projected_source_sha256"] is None
        assert receipt["solver_binary_sha256"] == sha(
            Path(receipt["solver_command"][0]))
        assert receipt["solver_stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.stderr.txt")
        assert receipt["status"] == "external_timeout"
        assert receipt["verified_relation"] is None
        assert receipt["observed_verified_relation_count"] == 0
        assert receipt["target_pdp_wall_seconds"] >= 120
        digest = hashlib.sha256()
        size = 0
        with gzip.open(HERE / "runs" / receipt["xcnf_archive"], "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
                size += len(chunk)
        assert digest.hexdigest() == receipt["xcnf_sha256"]
        assert size == receipt["xcnf_bytes"]
        control = receipt["control"]
        if kind == "planted" or n == 53:
            assert control["status"] == "known_witness_sat_verified"
            assert control["verified_relation"] is not None
            assert control["witness_receipt_sha256"] == sha(
                HERE / "runs" / ("n53_ordinary_matched_pair_table.json"
                                  if n == 53 else "n83_planted_frozen.json"))
            assert control["solver_stdout_sha256"] == sha(
                HERE / "runs" / f"{stem}.locked.stdout.txt")
            assert control["solver_stderr_sha256"] == sha(
                HERE / "runs" / f"{stem}.locked.stderr.txt")
            locked_digest = hashlib.sha256()
            locked_size = 0
            with gzip.open(HERE / "runs" / control["xcnf_archive"],
                           "rb") as stream:
                for chunk in iter(lambda: stream.read(1 << 20), b""):
                    locked_digest.update(chunk)
                    locked_size += len(chunk)
            assert locked_digest.hexdigest() == control["xcnf_sha256"]
            assert locked_size == control["xcnf_bytes"]
        else:
            assert control is None
        rows.append({"variant": stem, "receipt_sha256": sha(path),
                     "formula_sha256": digest.hexdigest(),
                     "formula_bytes": size,
                     "observed_verified_relation_count": 0})
    incomplete_path = HERE / "runs/n83_planted_group_add_incomplete.json"
    incomplete = json.loads(incomplete_path.read_text())
    assert incomplete["status"] == "artifact_write_failure"
    assert incomplete["candidate_id"] is None
    assert incomplete["target_pdp_wall_seconds"] is None
    assert incomplete["source_sha256"] == sha(
        HERE / "run_group_add_probe.py")
    assert incomplete["group_add_source_sha256"] == sha(
        HERE / "chain_group_add.py")
    assert incomplete["runtime_info_sha256"] == sha(
        HERE / "group_add_sage_runtime_info.json")
    assert incomplete["primary_solver_stdout_sha256"] == sha(
        HERE / "runs" / incomplete["primary_solver_stdout_file"])
    assert incomplete["primary_solver_stderr_sha256"] == sha(
        HERE / "runs" / incomplete["primary_solver_stderr_file"])
    digest = hashlib.sha256()
    size = 0
    with gzip.open(HERE / "runs" /
                   incomplete["primary_formula_archive"], "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    assert digest.hexdigest() == incomplete["primary_formula_sha256"]
    assert size == incomplete["primary_formula_bytes"]
    rows.append({"variant": "n83_planted_group_add_incomplete",
                 "receipt_sha256": sha(incomplete_path),
                 "formula_sha256": digest.hexdigest(),
                 "formula_bytes": size})
    forward_pin_path = HERE / "runs/n53_ordinary_group_add_forward_pin3.json"
    forward_pin = json.loads(forward_pin_path.read_text())
    assert forward_pin["proposal_id"] == "Q1320"
    assert forward_pin["candidate_id"] is None
    assert forward_pin["workload_id"] is None
    assert forward_pin["pin_leaves"] == 3
    assert forward_pin["oracle_assisted"] is True
    assert forward_pin["status"] == "external_timeout"
    assert forward_pin["verified_relation"] is None
    assert forward_pin["target_pdp_wall_seconds"] is None
    assert forward_pin["oracle_diagnostic_wall_seconds"] >= 20
    assert forward_pin["curve_id"] == json.loads((
        HERE / "runs/n53_ordinary_frozen.json").read_text())["curve_id"]
    assert forward_pin["baseline_receipt_sha256"] == sha(
        HERE / "runs/n53_ordinary_frozen.json")
    assert forward_pin["known_witness_receipt_sha256"] == sha(
        HERE / "runs/n53_ordinary_matched_pair_table.json")
    assert forward_pin["runtime_info_sha256"] == sha(
        HERE / "group_add_reverse_sage_runtime_info.json")
    for key, source in (("core_source_sha256", "chain_s3.py"),
                        ("group_add_source_sha256", "chain_group_add.py"),
                        ("base_orbit_source_sha256",
                         "chain_s3_base_orbit.py"),
                        ("base_probe_source_sha256",
                         "run_base_orbit_probe.py"),
                        ("group_probe_source_sha256",
                         "run_group_add_probe.py"),
                        ("reverse_probe_source_sha256",
                         "run_group_add_reverse_probe.py"),
                        ("runner_source_sha256",
                         "run_group_add_forward_pin3.py")):
        assert forward_pin[key] == sha(HERE / source)
    assert forward_pin["solver_binary_sha256"] == sha(
        Path(forward_pin["solver_command"][0]))
    assert forward_pin["solver_stdout_sha256"] == sha(
        HERE / "runs/n53_ordinary_group_add_forward_pin3.stdout.txt")
    assert forward_pin["solver_stderr_sha256"] == sha(
        HERE / "runs/n53_ordinary_group_add_forward_pin3.stderr.txt")
    digest = hashlib.sha256()
    size = 0
    with gzip.open(HERE / "runs" / forward_pin["xcnf_archive"],
                   "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    assert digest.hexdigest() == forward_pin["xcnf_sha256"]
    assert size == forward_pin["xcnf_bytes"]
    rows.append({"variant": "n53_ordinary_group_add_forward_pin3",
                 "receipt_sha256": sha(forward_pin_path),
                 "formula_sha256": digest.hexdigest(),
                 "formula_bytes": size})
    for n, kind, pinned, expected_status in (
            (53, "ordinary", 3, "sat"),
            (53, "ordinary", 2, "external_timeout"),
            (53, "ordinary", 0, "external_timeout"),
            (83, "planted", 3, "external_timeout"),
            (83, "ordinary", 0, "external_timeout")):
        stem = f"n{n}_{kind}_group_add_reverse_pin{pinned}"
        path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(path.read_text())
        baseline_path = HERE / "runs" / f"n{n}_{kind}_frozen.json"
        baseline = json.loads(baseline_path.read_text())
        archive_path = HERE / "bases" / (
            f"n{n}_weight{3 if n == 53 else 4}_orbits.json.gz")
        assert receipt["proposal_id"] == ("Q1322" if n == 53 else "Q1323")
        assert receipt["candidate_id"] is None
        assert receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["complete_solve_work_log2"] is None
        assert receipt["pin_leaves"] == pinned
        assert receipt["oracle_assisted"] == (pinned > 0)
        assert receipt["workload_id"] == (
            None if pinned else baseline["workload_id"])
        assert receipt["curve_id"] == baseline["curve_id"]
        assert receipt["public_target"] == baseline["public_subgroup_target"]
        assert receipt["factor_base_actual_B"] == baseline[
            "factor_base_actual_B"]
        assert receipt["factor_base_folded_columns"] == baseline[
            "factor_base_folded_columns"]
        assert receipt["factor_base_enumerated_set_sha256"] == baseline[
            "factor_base_enumerated_set_sha256"]
        assert receipt["base_archive_sha256"] == sha(archive_path)
        assert receipt["baseline_receipt_sha256"] == sha(baseline_path)
        assert receipt["protocol_sha256"] == protocol_digest
        assert receipt["runtime_info_sha256"] == sha(
            HERE / "group_add_reverse_sage_runtime_info.json")
        for key, source in (("core_source_sha256", "chain_s3.py"),
                            ("group_add_source_sha256", "chain_group_add.py"),
                            ("reverse_source_sha256",
                             "chain_group_add_reverse.py"),
                            ("base_orbit_source_sha256",
                             "chain_s3_base_orbit.py"),
                            ("base_probe_source_sha256",
                             "run_base_orbit_probe.py"),
                            ("group_probe_source_sha256",
                             "run_group_add_probe.py"),
                            ("probe_source_sha256", "run_probe.py"),
                            ("runner_source_sha256",
                             "run_group_add_reverse_probe.py")):
            assert receipt[key] == sha(HERE / source)
        if n == 83:
            assert receipt["projected_source_sha256"] == sha(
                HERE / "chain_s3_projected_sparse.py")
        else:
            assert receipt["projected_source_sha256"] is None
        assert receipt["solver_binary_sha256"] == sha(
            Path(receipt["solver_command"][0]))
        assert receipt["solver_stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.stderr.txt")
        assert receipt["status"] == expected_status
        assert receipt["observed_verified_relation_count"] == int(
            expected_status == "sat")
        if expected_status == "sat":
            assert receipt["verified_relation"] is not None
            assert receipt["verified_relation"]["verified_public_sum"] == (
                list(map(int, baseline["public_subgroup_target"])))
        else:
            assert receipt["verified_relation"] is None
        if pinned:
            assert receipt["known_witness_receipt_sha256"] == sha(
                HERE / "runs" / ("n53_ordinary_matched_pair_table.json"
                                  if n == 53 else "n83_planted_frozen.json"))
            assert receipt["target_pdp_wall_seconds"] is None
            assert receipt["oracle_diagnostic_wall_seconds"] > 0
        else:
            assert receipt["known_witness_receipt_sha256"] is None
            assert receipt["target_pdp_wall_seconds"] > 0
        digest = hashlib.sha256()
        size = 0
        with gzip.open(HERE / "runs" / receipt["xcnf_archive"], "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
                size += len(chunk)
        assert digest.hexdigest() == receipt["xcnf_sha256"]
        assert size == receipt["xcnf_bytes"]
        rows.append({"variant": stem, "receipt_sha256": sha(path),
                     "formula_sha256": digest.hexdigest(),
                     "formula_bytes": size,
                     "observed_verified_relation_count": receipt[
                         "observed_verified_relation_count"]})
    geometry_path = HERE / "runs/n131_projected_sparse_geometry.json"
    geometry = json.loads(geometry_path.read_text())
    assert geometry["proposal_id"] == "Q1318"
    assert geometry["candidate_id"] is None
    assert geometry["workload_id"] is None
    assert geometry["run_id"] is None
    assert geometry["exact_full_base_B"] is None
    assert geometry["exact_full_base_digest"] is None
    assert geometry["solver_invoked"] is False
    assert geometry["verified_relation"] is None
    assert geometry["complete_solve_work_log2"] is None
    assert geometry["group_control_count"] == 40
    assert geometry["protocol_sha256"] == protocol_digest
    assert geometry["n131_base_sample_receipt_sha256"] == sha(
        HERE / "runs/n131_weight6_stratified_sample.json")
    assert geometry["n131_base_replay_receipt_sha256"] == sha(
        HERE / "runs/n131_weight6_sage_independent_replay.json")
    assert geometry["runtime_info_sha256"] == sha(
        HERE / "projected_sparse_sage_runtime_info.json")
    for key, source in (("core_source_sha256", "chain_s3.py"),
                        ("factored_source_sha256", "chain_s3_factored.py"),
                        ("projected_source_sha256",
                         "chain_s3_projected_sparse.py"),
                        ("source_sha256",
                         "screen_n131_projected_sparse.py")):
        assert geometry[key] == sha(HERE / source)
    rows.append({"variant": "n131_projected_sparse_geometry",
                 "receipt_sha256": sha(geometry_path)})
    projected_replay_path = HERE / (
        "runs/n131_projected_sparse_sage_replay.json")
    projected_replay = json.loads(projected_replay_path.read_text())
    assert projected_replay["proposal_id"] == "Q1318"
    assert projected_replay["curve_id"] == geometry["curve_id"]
    assert projected_replay["status"] == "PASS"
    assert projected_replay["control_masks_checked"] == 40
    assert projected_replay[
        "both_lifts_projected_and_subgroup_checked"] == 40
    assert projected_replay["screen_receipt_sha256"] == sha(geometry_path)
    assert projected_replay["protocol_sha256"] == protocol_digest
    assert projected_replay["runtime_info_sha256"] == sha(
        HERE / "projected_sparse_sage_runtime_info.json")
    assert projected_replay["source_sha256"] == sha(
        HERE / "replay_n131_projected_sparse_sage.py")
    assert projected_replay["complete_solve_work_log2"] is None
    rows.append({"variant": "n131_projected_sparse_sage_replay",
                 "receipt_sha256": sha(projected_replay_path)})
    sample_path = HERE / "runs/n131_weight6_stratified_sample.json"
    sample = json.loads(sample_path.read_text())
    runtime = HERE / "n131_sample_sage_runtime_info.json"
    assert sample["protocol_sha256"] == protocol_digest
    assert sample["proposal_id"] == "Q1303"
    assert sample["candidate_id"] is None
    assert sample["complete_solve_work_log2"] is None
    assert sample["runtime_info_sha256"] == sha(runtime)
    assert sample["source_sha256"] == sha(
        HERE / "estimate_n131_weight6_base.py")
    assert sample["field_source_sha256"] == sha(
        HERE.parent.parent / "ecc2k130/codegen/field.py")
    assert sample["curve_source_sha256"] == sha(
        HERE.parent.parent / "ecc2k130/codegen/curves.py")
    assert len(sample["strata"]) == 6
    assert sum(row["sample_size"] for row in sample["strata"]) == 208646
    assert sample["exact_weight_at_most_two_projected_B"] == 8384
    assert sample["exact_weight_at_most_two_folded_columns"] == 32
    assert sample["uniform_subset_sum_planning_heuristic"][
        "is_complete_solve_projection"] is False
    rows.append({"variant": "n131_weight6_stratified_sample",
                 "receipt_sha256": sha(sample_path)})
    replay_path = HERE / "runs/n131_weight6_sage_independent_replay.json"
    replay = json.loads(replay_path.read_text())
    assert replay["status"] == "PASS"
    assert replay["protocol_sha256"] == protocol_digest
    assert replay["sample_receipt_sha256"] == sha(sample_path)
    assert replay["runtime_info_sha256"] == sha(runtime)
    assert replay["source_sha256"] == sha(
        HERE / "replay_n131_weight6_sample_sage.py")
    assert replay["normal_basis_gamma_squaring_checks"] == 131
    assert replay["exact_rational_x_counts_weights_one_two"] == {
        "1": sample["strata"][0]["rational_x_count_in_sample"],
        "2": sample["strata"][1]["rational_x_count_in_sample"],
    }
    assert replay["distinct_weight_two_control_projected_points"] == 16
    assert replay["producer_exact_weight_at_most_two_projected_B"] == (
        sample["exact_weight_at_most_two_projected_B"])
    assert replay["producer_w2_projected_B_exhaustively_replayed"] is False
    rows.append({"variant": "n131_weight6_sage_independent_replay",
                 "receipt_sha256": sha(replay_path)})
    pair_screen_path = HERE / "runs/n131_weight6_pure_pair_index_screen.json"
    pair_screen = json.loads(pair_screen_path.read_text())
    assert pair_screen["proposal_id"] == "Q1303"
    assert pair_screen["candidate_id"] is None
    assert pair_screen["isogeny"] == "none"
    assert pair_screen["curve_id"] == sample["curve_id"]
    assert pair_screen["factor_base_exact_B"] is None
    assert pair_screen["factor_base_exact_digest"] is None
    assert pair_screen["protocol_sha256"] == protocol_digest
    assert pair_screen["base_sample_receipt_sha256"] == sha(sample_path)
    assert pair_screen["independent_replay_receipt_sha256"] == sha(
        replay_path)
    assert pair_screen["source_sha256"] == sha(
        HERE / "screen_n131_weight6_pair_index.py")
    assert pair_screen["is_empirical_relation_yield"] is False
    assert pair_screen["is_complete_solve_projection"] is False
    assert pair_screen["challenge_dispatch_allowed"] is False
    estimate = pair_screen["estimate"]
    assert estimate["conditional_B"] == sample["conditional_B_estimate"]
    assert estimate["conditional_folded_columns_K"] == sample[
        "conditional_folded_columns_estimate"]
    assert math.isclose(estimate["index_states"], 131 * estimate[
        "conditional_folded_columns_K"] ** 2, rel_tol=1e-14)
    assert estimate["K_rank_rows_pair_probes"] > 2 ** 89
    assert pair_screen["optimistic_total_pair_actions_log2"] > 89
    rows.append({"variant": "n131_weight6_pure_pair_index_screen",
                 "receipt_sha256": sha(pair_screen_path)})
    from q1324_inputs import frozen_protocol, read_inputs
    support_path = HERE / "runs/n83_four_point_support_screen.json"
    support = json.loads(support_path.read_text())
    assert support["source_sha256"] == sha(
        HERE / "screen_n83_four_point_support.py")
    assert support["protocol_sha256"] == protocol_digest
    assert support["status"] == (
        "exact_count_bound_plus_separately_labeled_heuristic")
    q1324_protocol_path = HERE / "q1324_protocol.json"
    q1324_protocol = json.loads(q1324_protocol_path.read_text())
    assert q1324_protocol == frozen_protocol()
    (q1041_path, q1041, point_key_path, baseline_path, baseline, xkeys,
     x_digest) = read_inputs()
    base_replay_path = HERE / "runs/n83_q1324_q1041_full_base_verification.json"
    base_replay = json.loads(base_replay_path.read_text())
    assert base_replay["status"] == "PASS"
    assert base_replay["proposal_id"] == "Q1324"
    assert base_replay["candidate_id"] is None
    assert base_replay["curve_id"] == baseline["curve_id"]
    assert base_replay["actual_usable_points_B_before_folding"] == 4000102
    assert base_replay["signed_frobenius_columns"] == 24097
    assert base_replay["verified_projected_representatives"] == 24097
    assert base_replay["factor_base_enumerated_set_sha256"] == q1041[
        "factor_base"]["enumerated_set_sha256"]
    assert base_replay["derived_representative_x_sha256"] == x_digest
    assert base_replay["base_receipt_sha256"] == sha(q1041_path)
    assert base_replay["point_key_file_sha256"] == sha(point_key_path)
    assert base_replay["q1041_verifier_source_sha256"] == sha(
        q1041_path.parent.parent / "verify_n83_base.py")
    assert base_replay["q1324_input_source_sha256"] == sha(
        HERE / "q1324_inputs.py")
    assert base_replay["runtime_info_sha256"] == sha(
        HERE / "q1324_sage_runtime_info.json")
    assert base_replay["source_sha256"] == sha(HERE / "verify_q1324_base.py")
    rows.append({"variant": "n83_q1324_q1041_full_base_verification",
                 "receipt_sha256": sha(base_replay_path)})
    for row, b, digest in zip(support["profiles"],
                              (24062, 1934066, 4000102),
                              (json.loads((HERE / "protocol.json").read_text())[
                                  "profiles"][0]["factor_base"][
                                      "enumerated_set_sha256"],
                               baseline["factor_base_enumerated_set_sha256"],
                               q1041["factor_base"]["enumerated_set_sha256"])):
        r = row["subgroup_order_r"]
        assert row["actual_usable_points_B_before_folding"] == b
        assert row["factor_base_enumerated_set_sha256"] == digest
        assert row["distinct_unordered_four_subsets"] == str(math.comb(b, 4))
        assert row["four_multisets_allowing_repeated_leaves"] == str(
            math.comb(b + 3, 4))
        assert math.isclose(row[
            "uniform_nonidentity_target_coverage_upper_bound"], min(
                1.0, math.comb(b + 3, 4) / (r - 1)), rel_tol=1e-14)
    assert support["profiles"][1][
        "uniform_nonidentity_target_coverage_upper_bound"] < 0.242
    assert support["q1041_receipt_sha256"] == sha(q1041_path)
    assert support["q1041_point_key_sha256"] == sha(point_key_path)
    rows.append({"variant": "n83_four_point_support_screen",
                 "receipt_sha256": sha(support_path)})

    from run_probe import curves, field
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    order = q1041["curve_identity_record"]["curve"]["subgroup_order"]
    for mode in ("planted_locked", "ordinary"):
        stem = f"n83_q1324_{mode}"
        receipt_path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["proposal_id"] == "Q1324"
        assert receipt["candidate_id"] is None and receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["curve_id"] == baseline["curve_id"]
        assert receipt["mode"] == mode
        assert receipt["oracle_assisted"] == (mode == "planted_locked")
        assert receipt["workload_id"] == (
            baseline["workload_id"] if mode == "ordinary" else None)
        assert receipt["factor_base_actual_B"] == 4000102
        assert receipt["factor_base_folded_columns"] == 24097
        assert receipt["factor_base_enumerated_set_sha256"] == q1041[
            "factor_base"]["enumerated_set_sha256"]
        assert receipt["derived_representative_x_sha256"] == x_digest
        assert receipt["base_receipt_sha256"] == sha(q1041_path)
        assert receipt["base_point_key_file_sha256"] == sha(point_key_path)
        assert receipt["ordinary_target_receipt_sha256"] == sha(baseline_path)
        assert receipt["protocol_sha256"] == sha(q1324_protocol_path)
        assert receipt["runtime_info_sha256"] == sha(
            HERE / "q1324_sage_runtime_info.json")
        assert receipt["runner_source_sha256"] == sha(
            HERE / "run_q1324_weight5_probe.py")
        assert receipt["base_selector_source_sha256"] == sha(
            HERE / "chain_s3_base_orbit.py")
        assert receipt["solver_binary_sha256"] == sha(
            Path(receipt["solver_command"][0]))
        assert receipt["solver_stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.stderr.txt")
        digest = hashlib.sha256()
        size = 0
        with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
                size += len(chunk)
        assert digest.hexdigest() == receipt["xcnf_sha256"]
        assert size == receipt["xcnf_bytes"]
        relation = receipt["verified_relation"]
        assert receipt["observed_verified_relation_count"] == int(
            relation is not None)
        assert receipt["field_operations"] is None
        assert receipt["complete_solve_work_log2"] is None
        if relation is not None:
            target = tuple(map(int, receipt["public_target"]))
            points = [tuple(map(int, point)) for point in relation[
                "leaf_points"]]
            assert len(points) == 4
            total = None
            for point, sign in zip(points, relation["signs"]):
                assert curve.onCurve(point) and curve.mul(point, order) is None
                assert sign in (1, -1)
                total = curve.add(total, point if sign == 1 else
                                  curve.neg(point))
            assert total == target
            for point, (index, shift) in zip(points, receipt[
                    "chosen_orbit_choices"]):
                expected = onb.frob(onb.fromCoords(xkeys[index]), shift)
                assert point[0] == expected
        if mode == "planted_locked":
            assert receipt["status"] == "sat" and relation is not None
            assert receipt["target_pdp_wall_seconds"] is None
            assert receipt["oracle_control_wall_seconds"] > 0
        else:
            assert receipt["target_pdp_wall_seconds"] > 0
            assert receipt["oracle_control_wall_seconds"] is None
            assert receipt["public_target"] == list(map(
                int, baseline["public_subgroup_target"]))
        rows.append({"variant": stem, "receipt_sha256": sha(receipt_path),
                     "formula_sha256": digest.hexdigest(),
                     "formula_bytes": size,
                     "observed_verified_relation_count": receipt[
                         "observed_verified_relation_count"]})
    from q1325_inputs import frozen_protocol as q1325_frozen_protocol
    from q1325_inputs import read_inputs as q1325_read_inputs
    q1325_protocol_path = HERE / "q1325_protocol.json"
    q1325_protocol = json.loads(q1325_protocol_path.read_text())
    assert q1325_protocol == q1325_frozen_protocol()
    (q1325_base_path, q1325_base, q1325_key_path, q1325_keys,
     q1325_baseline_path, q1325_baseline) = q1325_read_inputs()
    q1325_fb = q1325_base["factor_base"]
    assert q1325_base["source_sha256"] == sha(
        HERE / "enumerate_n83_weight5_full.py")
    assert q1325_base["runtime_info_sha256"] == sha(
        HERE / "q1325_sage_runtime_info.json")
    assert q1325_base["field_source_sha256"] == sha(
        HERE.parent.parent / "ecc2k130/codegen/field.py")
    assert q1325_base["curve_source_sha256"] == sha(
        HERE.parent.parent / "ecc2k130/codegen/curves.py")
    assert q1325_fb["actual_usable_points_B_before_folding"] == 30977592
    assert q1325_fb["signed_frobenius_columns"] == 186612
    assert q1325_fb["enumerated_set_sha256"] == sha(q1325_key_path)
    assert q1325_fb["duplicate_projection_orbits"] == 0
    assert q1325_fb["identity_projection_orbits"] == 0
    assert q1325_base["q1041_subset"]["subset_columns_verified"] == 24097
    assert math.isclose(math.comb(30977592, 4) / q1325_base[
        "curve"]["subgroup_order"], 15869.003181863845, rel_tol=1e-12)
    rows.append({"variant": "n83_q1325_full_weight5_base",
                 "receipt_sha256": sha(q1325_base_path),
                 "point_key_file_sha256": sha(q1325_key_path)})
    q1325_replay_path = HERE / "runs/n83_q1325_full_base_replay.json"
    q1325_replay = json.loads(q1325_replay_path.read_text())
    assert q1325_replay["status"] == "PASS"
    assert q1325_replay["actual_usable_points_B_before_folding"] == 30977592
    assert q1325_replay["signed_frobenius_columns"] == 186612
    assert q1325_replay["point_keys_replayed_on_curve_and_canonical"] == 186612
    assert q1325_replay["q1041_subset_columns_verified"] == 24097
    assert q1325_replay["q1302_weight4_subset_columns_verified"] == 11651
    assert q1325_replay["factor_base_enumerated_set_sha256"] == q1325_fb[
        "enumerated_set_sha256"]
    assert q1325_replay["base_receipt_sha256"] == sha(q1325_base_path)
    assert q1325_replay["point_key_file_sha256"] == sha(q1325_key_path)
    assert q1325_replay["runtime_info_sha256"] == sha(
        HERE / "q1325_sage_runtime_info.json")
    assert q1325_replay["source_sha256"] == sha(
        HERE / "verify_q1325_full_base.py")
    rows.append({"variant": "n83_q1325_full_base_replay",
                 "receipt_sha256": sha(q1325_replay_path)})
    from q1324_inputs import OrbitKey
    q1325_orbit = OrbitKey(onb)
    q1325_key_set = set(q1325_keys)
    for mode in ("planted_locked", "ordinary"):
        stem = f"n83_q1325_{mode}"
        receipt_path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["proposal_id"] == "Q1325"
        assert receipt["candidate_id"] is None and receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["curve_id"] == q1325_baseline["curve_id"]
        assert receipt["mode"] == mode
        assert receipt["oracle_assisted"] == (mode == "planted_locked")
        assert receipt["workload_id"] == (q1325_baseline["workload_id"]
                                         if mode == "ordinary" else None)
        assert receipt["factor_base_actual_B"] == 30977592
        assert receipt["factor_base_folded_columns"] == 186612
        assert receipt["factor_base_enumerated_set_sha256"] == q1325_fb[
            "enumerated_set_sha256"]
        assert receipt["base_receipt_sha256"] == sha(q1325_base_path)
        assert receipt["base_point_key_file_sha256"] == sha(q1325_key_path)
        assert receipt["ordinary_target_receipt_sha256"] == sha(
            q1325_baseline_path)
        assert receipt["protocol_sha256"] == sha(q1325_protocol_path)
        assert receipt["runtime_info_sha256"] == sha(
            HERE / "q1325_sage_runtime_info.json")
        assert receipt["runner_source_sha256"] == sha(
            HERE / "run_q1325_full_weight5_probe.py")
        assert receipt["projected_source_sha256"] == sha(
            HERE / "chain_s3_projected_sparse.py")
        assert receipt["solver_binary_sha256"] == sha(
            Path(receipt["solver_command"][0]))
        assert receipt["solver_stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.stderr.txt")
        digest = hashlib.sha256()
        size = 0
        with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
                size += len(chunk)
        assert digest.hexdigest() == receipt["xcnf_sha256"]
        assert size == receipt["xcnf_bytes"]
        relation = receipt["verified_relation"]
        assert receipt["observed_verified_relation_count"] == int(
            relation is not None)
        assert receipt["field_operations"] is None
        assert receipt["complete_solve_work_log2"] is None
        if relation is not None:
            target = tuple(map(int, receipt["public_target"]))
            points = [tuple(map(int, point)) for point in relation[
                "leaf_points"]]
            assert len(points) == 4
            total = None
            for point, sign in zip(points, relation["signs"]):
                assert curve.onCurve(point) and curve.mul(point, order) is None
                total = curve.add(total, point if sign == 1 else
                                  curve.neg(point))
                assert q1325_orbit.canonical(point)[0] in q1325_key_set
            assert total == target
            for raw, expected in zip(receipt["raw_leaf_x_coordinates"],
                                     receipt["projected_leaf_x_coordinates"]):
                assert raw and raw.bit_count() <= 5
                raw_point = curve.pointFromX(onb.fromCoords(raw))
                assert raw_point is not None
                projected = curve.mul(raw_point, 4)
                assert projected is not None
                assert onb.toCoords(projected[0]) == expected
        if mode == "planted_locked":
            assert receipt["status"] == "sat" and relation is not None
            assert receipt["target_pdp_wall_seconds"] is None
            assert receipt["oracle_control_wall_seconds"] > 0
        else:
            assert receipt["status"] == "external_timeout"
            assert receipt["target_pdp_wall_seconds"] > 0
            assert receipt["oracle_control_wall_seconds"] is None
            assert relation is None
            assert receipt["public_target"] == list(map(
                int, q1325_baseline["public_subgroup_target"]))
        rows.append({"variant": stem, "receipt_sha256": sha(receipt_path),
                     "formula_sha256": digest.hexdigest(),
                     "formula_bytes": size,
                     "observed_verified_relation_count": receipt[
                         "observed_verified_relation_count"]})
    from run_q1326_nested_base_probe import frozen_protocol as q1326_frozen
    from run_q1326_nested_base_probe import inputs as q1326_inputs
    from run_q1326_nested_base_probe import selected_keys as q1326_keys
    from run_probe import curves as q1326_curves, field as q1326_field
    q1326_protocol_path = HERE / "q1326_protocol.json"
    q1326_protocol = json.loads(q1326_protocol_path.read_text())
    assert q1326_protocol == q1326_frozen()
    assert q1326_protocol["proposal_id"] == "Q1326"
    assert q1326_protocol["candidate_id"] is None
    assert q1326_protocol["isogeny"] == "none"
    (q1326_baseline_path, q1326_baseline, q1326_base_path,
     q1326_base, q1326_all_keys, q1326_stages) = q1326_inputs()
    assert q1326_protocol["ordinary_workload_id"] == q1326_baseline[
        "workload_id"] == "74f2979b3e68"
    assert q1326_protocol["search_restrictions"] == q1326_stages
    assert q1326_protocol["parent_factor_base"][
        "actual_usable_points_B_before_folding"] == 24062
    assert q1326_protocol["parent_factor_base"][
        "signed_frobenius_columns"] == 227
    q1326_runtime_path = HERE / "q1326_sage_runtime_info.json"
    assert json.loads(q1326_runtime_path.read_text())["status"] == "verified"
    q1326_onb = q1326_field.Onb(53)
    q1326_curve = q1326_curves.Curve(q1326_onb)
    q1326_order = q1326_base["curve"]["subgroup_order"]

    def q1326_replay_relation(relation, target, stage):
        allowed_x = {q1326_onb.toCoords(q1326_onb.frob(
            q1326_onb.fromCoords(key), shift))
            for key in q1326_keys(q1326_all_keys, stage)
            for shift in range(53)}
        points = [tuple(map(int, point)) for point in relation["leaf_points"]]
        assert len(points) == 4 and len(relation["signs"]) == 4
        total = None
        for point, sign in zip(points, relation["signs"]):
            assert q1326_curve.onCurve(point)
            assert q1326_curve.mul(point, q1326_order) is None
            assert q1326_onb.toCoords(point[0]) in allowed_x
            assert sign in (-1, 1)
            total = q1326_curve.add(total, point if sign == 1 else
                                     q1326_curve.neg(point))
        assert total == target

    def q1326_check_formula(receipt, stem):
        assert receipt["solver_binary_sha256"] == sha(
            Path(receipt["solver_command"][0]))
        assert receipt["solver_stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.stderr.txt")
        digest = hashlib.sha256()
        size = 0
        with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
                size += len(chunk)
        assert receipt["xcnf_sha256"] == digest.hexdigest()
        assert receipt["xcnf_bytes"] == size
        return digest.hexdigest(), size

    planted_path = HERE / "runs/n53_q1326_planted_locked.json"
    planted = json.loads(planted_path.read_text())
    assert planted["proposal_id"] == "Q1326"
    assert planted["candidate_id"] is None
    assert planted["workload_id"] is None
    assert planted["oracle_assisted"] is True
    assert planted["eligible_actual_B_before_folding"] == 6784
    assert planted["eligible_folded_columns"] == 64
    assert planted["eligible_set_sha256"] == q1326_stages[0][
        "eligible_set_sha256"]
    assert planted["status"] == "locked_sat_verified_public_relation"
    assert planted["protocol_sha256"] == sha(q1326_protocol_path)
    assert planted["runtime_info_sha256"] == sha(q1326_runtime_path)
    assert planted["runner_source_sha256"] == sha(
        HERE / "run_q1326_nested_base_probe.py")
    assert planted["base_chain_source_sha256"] == sha(
        HERE / "chain_s3_base_orbit.py")
    assert planted["control"]["witness_receipt_sha256"] == sha(
        q1326_protocol_path)
    planted_target = tuple(map(int, planted["public_target"]))
    q1326_replay_relation(planted["control"]["relation"], planted_target,
                          q1326_stages[0])
    rows.append({"variant": "n53_q1326_planted_locked",
                 "receipt_sha256": sha(planted_path),
                 "verified_relation_count": 1,
                 "oracle_assisted": True})

    q1326_attempts = []
    for stage in q1326_stages:
        stem = f"n53_q1326_ordinary_{stage['stage']}"
        path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(path.read_text())
        assert receipt["proposal_id"] == "Q1326"
        assert receipt["candidate_id"] is None
        assert receipt["workload_id"] == q1326_baseline["workload_id"]
        assert receipt["oracle_assisted"] is False
        assert receipt["curve_id"] == q1326_baseline["curve_id"]
        assert receipt["isogeny"] == "none"
        assert receipt["stage"] == stage["stage"]
        assert receipt["parent_base_actual_B"] == 24062
        assert receipt["parent_base_folded_columns"] == 227
        assert receipt["parent_base_enumerated_set_sha256"] == q1326_base[
            "factor_base"]["enumerated_set_sha256"]
        assert receipt["eligible_actual_B_before_folding"] == stage[
            "eligible_actual_B_before_folding"]
        assert receipt["eligible_folded_columns"] == stage[
            "eligible_folded_columns"]
        assert receipt["eligible_set_sha256"] == stage[
            "eligible_set_sha256"]
        assert receipt["uniform_target_mean_distinct_four_subsets_exact"] == (
            stage["uniform_target_mean_distinct_four_subsets_exact"])
        assert receipt["public_target"] == list(map(
            int, q1326_baseline["public_subgroup_target"]))
        assert receipt["protocol_sha256"] == sha(q1326_protocol_path)
        assert receipt["runtime_info_sha256"] == sha(q1326_runtime_path)
        assert receipt["ordinary_target_receipt_sha256"] == sha(
            q1326_baseline_path)
        assert receipt["parent_base_archive_sha256"] == sha(
            q1326_base_path)
        assert receipt["runner_source_sha256"] == sha(
            HERE / "run_q1326_nested_base_probe.py")
        assert receipt["base_chain_source_sha256"] == sha(
            HERE / "chain_s3_base_orbit.py")
        assert receipt["verified_relation"] is None
        assert receipt["observed_verified_relation_count"] == 0
        assert receipt["field_operations"] is None
        assert receipt["complete_solve_work_log2"] is None
        assert receipt["target_pdp_wall_seconds"] > 0
        assert receipt["target_relation_check_wall_seconds"] >= 0
        digest, size = q1326_check_formula(receipt, stem)
        q1326_attempts.append((path, receipt))
        rows.append({"variant": stem, "receipt_sha256": sha(path),
                     "formula_sha256": digest, "formula_bytes": size,
                     "verified_relation_count": 0})
    assert [receipt["status"] for _, receipt in q1326_attempts] == [
        "external_timeout", "censored", "censored"]
    assert [receipt["solver_conflicts_reported"]
            for _, receipt in q1326_attempts][1:] == [1000001, 1000001]
    summary_path = HERE / "runs/n53_q1326_ordinary_summary.json"
    summary = json.loads(summary_path.read_text())
    assert summary["status"] == "censored"
    assert summary["verified_stage"] is None
    assert summary["observed_verified_relation_count"] == 0
    assert summary["workload_id"] == q1326_baseline["workload_id"]
    assert summary["protocol_sha256"] == sha(q1326_protocol_path)
    assert summary["runner_source_sha256"] == sha(
        HERE / "run_q1326_nested_base_probe.py")
    assert summary["stage_attempts"] == [{
        "stage": receipt["stage"], "receipt_sha256": sha(path),
        "status": receipt["status"],
        "verified_relation_count": 0,
        "target_pdp_wall_seconds": receipt["target_pdp_wall_seconds"],
        "target_relation_check_wall_seconds": receipt[
            "target_relation_check_wall_seconds"],
    } for path, receipt in q1326_attempts]
    assert math.isclose(summary["total_target_pdp_wall_seconds"], sum(
        receipt["target_pdp_wall_seconds"]
        for _, receipt in q1326_attempts), rel_tol=1e-12)
    rows.append({"variant": "n53_q1326_ordinary_summary",
                 "receipt_sha256": sha(summary_path),
                 "verified_relation_count": 0})

    unpinned_stem = "n53_q1326_planted_unpinned"
    unpinned_path = HERE / "runs" / f"{unpinned_stem}.json"
    unpinned = json.loads(unpinned_path.read_text())
    assert unpinned["planted_target"] is True
    assert unpinned["oracle_assisted_solver"] is False
    assert unpinned["workload_id"] is None
    assert unpinned["public_target"] == list(planted_target)
    assert unpinned["eligible_set_sha256"] == q1326_stages[0][
        "eligible_set_sha256"]
    assert unpinned["status"] == "censored"
    assert 1000000 <= unpinned["solver_conflicts_reported"] <= 1000010
    assert unpinned["verified_relation"] is None
    assert unpinned["observed_verified_relation_count"] == 0
    assert unpinned["planted_control_receipt_sha256"] == sha(planted_path)
    assert unpinned["protocol_sha256"] == sha(q1326_protocol_path)
    assert unpinned["runtime_info_sha256"] == sha(q1326_runtime_path)
    assert unpinned["runner_source_sha256"] == sha(
        HERE / "diagnose_q1326_planted_unpinned.py")
    digest, size = q1326_check_formula(unpinned, unpinned_stem)
    rows.append({"variant": unpinned_stem,
                 "receipt_sha256": sha(unpinned_path),
                 "formula_sha256": digest, "formula_bytes": size,
                 "verified_relation_count": 0})

    support_path = HERE / "runs/n53_q1326_k128_support_diagnostic.json"
    support = json.loads(support_path.read_text())
    assert support["proposal_id"] == "Q1326"
    assert support["candidate_id"] is None
    assert support["workload_id"] == q1326_baseline["workload_id"]
    assert support["curve_id"] == q1326_baseline["curve_id"]
    assert support["isogeny"] == "none"
    assert support["eligible_actual_B_before_folding"] == 13568
    assert support["eligible_folded_columns"] == 128
    assert support["eligible_set_sha256"] == q1326_stages[-1][
        "eligible_set_sha256"]
    assert support["status"] == "budget"
    assert support["relation"] is None
    assert support["observed_verified_relation_count"] == 0
    assert support["total_logical_pair_samples"] == 2000000
    assert support["protocol_sha256"] == sha(q1326_protocol_path)
    assert support["runtime_info_sha256"] == sha(q1326_runtime_path)
    assert support["ordinary_target_receipt_sha256"] == sha(
        q1326_baseline_path)
    assert support["parent_base_archive_sha256"] == sha(
        q1326_base_path)
    assert support["runner_source_sha256"] == sha(
        HERE / "diagnose_q1326_subset_support.py")
    pair_path = HERE.parent / "koblitz-pair-claw-20260929"
    assert support["prior_pair_search_source_sha256"] == sha(
        pair_path / "probe_n53_table.py")
    assert support["prior_base_source_sha256"] == sha(
        pair_path / "probe_n53_relation.py")
    assert support["orbit_key_source_sha256"] == sha(
        pair_path / "orbit_key.py")
    rows.append({"variant": "n53_q1326_k128_support_diagnostic",
                 "receipt_sha256": sha(support_path),
                 "verified_relation_count": 0})
    for n, expected_curve, expected_reps in (
        (53, "EC1N53Ckb1hf77aab617904", 227),
        (83, "EC1N83Ckb1h876c2921cb64", 186612),
    ):
        bridge_path = HERE / "field_bridges" / f"n{n}_onb_poly.json"
        bridge = json.loads(bridge_path.read_text())
        replay_path = HERE / "runs" / f"n{n}_onb_poly_bridge_replay.json"
        replay = json.loads(replay_path.read_text())
        bridge_runtime_path = HERE / "bridge_sage_runtime_info.json"
        assert json.loads(bridge_runtime_path.read_text())[
            "status"] == "verified"
        assert bridge["status"] == replay["status"] == "PASS"
        assert bridge["field_degree"] == replay["field_degree"] == n
        assert bridge["curve_id"] == replay["curve_id"] == expected_curve
        assert bridge["isogeny"] == replay["isogeny"] == "none"
        assert bridge["changes_curve_identity"] is False
        assert len(bridge["onb_to_poly_basis_images"]) == n
        assert len(bridge["poly_to_onb_basis_images"]) == n
        assert bridge["multiplication_square_inverse_controls"] == 128
        assert bridge["group_addition_controls"] == 9
        assert bridge["runtime_info_sha256"] == sha(bridge_runtime_path)
        assert bridge["field_source_sha256"] == sha(
            HERE.parent.parent / "ecc2k130/codegen/field.py")
        assert bridge["curve_source_sha256"] == sha(
            HERE.parent.parent / "ecc2k130/codegen/curves.py")
        assert bridge["source_sha256"] == sha(
            HERE / "derive_onb_poly_bridge.py")
        assert replay["bridge_sha256"] == sha(bridge_path)
        assert replay["all_basis_products_checked"] == n * n
        assert replay[
            "factor_base_representatives_checked_on_polynomial_curve"] == (
                expected_reps)
        assert replay["ordinary_target_checked_on_polynomial_curve"] is True
        assert replay["runtime_info_sha256"] == sha(bridge_runtime_path)
        assert replay["field_source_sha256"] == bridge[
            "field_source_sha256"]
        assert replay["orbit_source_sha256"] == sha(
            HERE.parent / "koblitz-pair-claw-20260929/orbit_key.py")
        assert replay["source_sha256"] == sha(
            HERE / "verify_onb_poly_bridge.py")
        source_base = HERE / "bases" / (
            f"n{n}_weight{3 if n == 53 else 4}_orbits.json.gz")
        checked_base = (source_base if n == 53 else
                        HERE / "bases/n83_weight5_full_orbits.json")
        assert bridge["base_archive_sha256"] == sha(source_base)
        assert replay["bridge_source_base_archive_sha256"] == sha(
            source_base)
        assert replay["base_archive_sha256"] == sha(checked_base)
        assert bridge["baseline_receipt_sha256"] == replay[
            "baseline_receipt_sha256"] == sha(
                HERE / "runs" / f"n{n}_ordinary_frozen.json")
        rows.append({"variant": f"n{n}_onb_poly_bridge",
                     "receipt_sha256": sha(bridge_path),
                     "status": "PASS"})
        rows.append({"variant": f"n{n}_onb_poly_bridge_replay",
                     "receipt_sha256": sha(replay_path),
                     "all_basis_products_checked": n * n,
                     "factor_base_representatives_checked": expected_reps})
    native_protocol_path = HERE / "q1327_q1328_native_root_protocol.json"
    native_protocol = json.loads(native_protocol_path.read_text())
    assert native_protocol["kind"] == (
        "bounded_native_four_summand_s3_root_stage_protocol")
    assert native_protocol["candidate_id"] is None
    assert native_protocol["isogeny"] == "none"
    assert native_protocol["point_decomposition"]["stage_code"] == (
        "PDP4root")
    assert len(native_protocol["profiles"]) == 2
    rows.append({"variant": "q1327_q1328_native_root_protocol",
                 "receipt_sha256": sha(native_protocol_path)})
    native_runtime_path = HERE / "native_root_sage_runtime_info.json"
    assert json.loads(native_runtime_path.read_text())[
        "status"] == "verified"
    native_build_path = HERE / "native_build_receipt.json"
    native_build = json.loads(native_build_path.read_text())
    assert native_build["status"] == "PASS"
    assert native_build["source_sha256"] == sha(
        HERE / "native_s3_root.rs")
    assert native_build["build_script_sha256"] == sha(
        HERE / "build_native_s3_root.py")
    rows.append({"variant": "native_s3_root_window_build",
                 "receipt_sha256": sha(native_build_path),
                 "source_sha256": native_build["source_sha256"]})
    legacy_build_path = HERE / "native_legacy_scalar_build_receipt.json"
    legacy_build = json.loads(legacy_build_path.read_text())
    assert legacy_build["status"] == "PASS"
    assert legacy_build["source_sha256"] == sha(
        HERE / "native_s3_root_scalar.rs")
    assert legacy_build["binary_sha256"] == (
        "6ea85faa454eabe0a2a811a4045fe74dedb85f53ccdd51d62038a5ee159403c5")
    rows.append({"variant": "native_s3_root_historical_scalar_build",
                 "receipt_sha256": sha(legacy_build_path),
                 "source_sha256": legacy_build["source_sha256"]})
    native_batch_build_path = native_build_path
    native_batch_build = native_build
    for (n, proposal, parent, expected_curve, expected_workload, b, k, cap,
         expected_status) in (
        (53, "Q1327", "Q1301", "EC1N53Ckb1hf77aab617904",
         "74f2979b3e68", 24062, 227, 2731037,
         "native_relation_found"),
        (83, "Q1328", "Q1325", "EC1N83Ckb1h876c2921cb64",
         "bab50a1e5f66", 30977592, 186612, 2000000,
         "state_cap_no_relation"),
    ):
        stage_profile = next(profile for profile in native_protocol[
            "profiles"] if profile["field_degree"] == n)
        manifest_path = HERE / "native_inputs" / f"n{n}_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        reps_path = HERE / "native_inputs" / f"n{n}_x_representatives.bin"
        assert manifest["proposal_id"] == stage_profile[
            "proposal_id"] == proposal
        assert manifest["parent_factor_base_proposal_id"] == (
            stage_profile["parent_factor_base_proposal_id"])
        assert manifest["parent_factor_base_proposal_id"] == parent
        assert manifest["curve_id"] == stage_profile[
            "curve_id"] == expected_curve
        assert manifest["workload_id"] == stage_profile[
            "workload_id"] == expected_workload
        assert manifest["actual_usable_points_B"] == (
            stage_profile["factor_base_actual_B"])
        assert manifest["actual_usable_points_B"] == b
        assert manifest["representative_count_K"] == (
            stage_profile["factor_base_folded_columns_K"])
        assert manifest["representative_count_K"] == k
        assert manifest["pair_state_cap"] == stage_profile[
            "pair_state_cap"] == cap
        assert manifest["peak_rss_cap_mib"] == stage_profile[
            "peak_rss_cap_mib"] == 1024
        assert manifest["stage_protocol_sha256"] == sha(
            native_protocol_path)
        assert manifest["runtime_info_sha256"] == sha(
            native_runtime_path)
        assert manifest["source_sha256"] == sha(
            HERE / "export_native_root_inputs.py")
        assert manifest["bridge_sha256"] == sha(
            HERE / "field_bridges" / f"n{n}_onb_poly.json")
        assert manifest["target_source_receipt_sha256"] == sha(
            HERE / "runs" / f"n{n}_ordinary_frozen.json")
        assert manifest["representatives_file_sha256"] == sha(reps_path)
        assert reps_path.stat().st_size == 16 * k
        base_path = HERE / "bases" / (
            "n53_weight3_orbits.json.gz" if n == 53
            else "n83_weight5_full_orbits.json")
        assert manifest["source_base_archive_sha256"] == sha(base_path)
        rows.append({"variant": f"n{n}_native_root_input",
                     "receipt_sha256": sha(manifest_path),
                     "representatives_sha256": sha(reps_path),
                     "factor_base_B": b, "folded_columns_K": k})
        stage_path = HERE / "runs" / (
            "n53_native_root_full.json" if n == 53
            else "n83_native_root_capped_2m.json")
        stage = json.loads(stage_path.read_text())
        assert stage["proposal_id"] == proposal
        assert stage["parent_factor_base_proposal_id"] == parent
        assert stage["curve_id"] == expected_curve
        assert stage["workload_id"] == expected_workload
        assert stage["status"] == expected_status
        assert stage["native_source_sha256"] == native_build[
            "source_sha256"]
        assert stage["cargo_manifest_sha256"] == native_build[
            "cargo_manifest_sha256"]
        assert stage["stage_protocol_sha256"] == sha(
            native_protocol_path)
        assert stage["input_representatives_sha256"] == sha(reps_path)
        assert stage["actual_usable_points_B"] == b
        assert stage["folded_columns_K"] == k
        assert stage["limits"]["pair_state_cap"] == cap
        assert stage["limits"]["peak_rss_cap_bytes"] == 1024 ** 3
        assert stage["peak_rss_bytes"] <= 1024 ** 3
        assert stage["index_pair_states_examined"] == cap
        assert stage["operation_counts"]["index_build"][
            "s3_root_calls"] == cap
        assert stage["sampling"]["orientations_per_state"] == 1
        assert stage["target_state_orientations_tested"] == stage[
            "target_states_scanned"]
        assert stage["native_s3_generator_target_control"][
            "status"] == "PASS"
        assert stage["verified_single_target_dlp"] is False
        assert stage["complete_work_log2"] is None
        if n == 53:
            assert stage["relation"] is not None
            assert stage["target_states_scanned"] == 49228
        else:
            assert stage["relation"] is None
            assert stage["target_states_scanned"] == cap
        rows.append({"variant": f"n{n}_native_root_stage",
                     "receipt_sha256": sha(stage_path),
                     "status": expected_status,
                     "peak_rss_bytes": stage["peak_rss_bytes"]})
        replay_path = HERE / "runs" / (
            f"n{n}_native_root_independent_replay.json")
        replay = json.loads(replay_path.read_text())
        assert replay["status"] == "PASS"
        assert replay["proposal_id"] == proposal
        assert replay["parent_factor_base_proposal_id"] == parent
        assert replay["curve_id"] == expected_curve
        assert replay["workload_id"] == expected_workload
        assert replay["native_stage_status"] == expected_status
        assert replay["native_receipt_sha256"] == sha(stage_path)
        assert replay["native_build_receipt_sha256"] == sha(
            native_build_path)
        assert replay["native_input_manifest_sha256"] == sha(
            manifest_path)
        assert replay["native_input_representatives_sha256"] == sha(
            reps_path)
        assert replay["stage_protocol_sha256"] == sha(
            native_protocol_path)
        assert replay["source_sha256"] == sha(
            HERE / "verify_native_s3_root.py")
        assert replay["ordinary_relation_independently_verified"] is (n == 53)
        if n == 53:
            assert replay["subgroup_points_checked"] == 4
            assert replay["rank_of_native_and_matched_pair_rows"] == 2
        else:
            assert replay["censored_ordinary_query"] is True
            assert replay["proves_target_unsupported"] is False
        rows.append({"variant": f"n{n}_native_root_independent_replay",
                     "receipt_sha256": sha(replay_path),
                     "verified_relation_count": int(n == 53)})
    control_fixture_path = HERE / "runs/n83_q1329_planted_fixture.json"
    control_fixture = json.loads(control_fixture_path.read_text())
    control_manifest_path = HERE / "native_inputs/n83_planted_control_manifest.json"
    control_manifest = json.loads(control_manifest_path.read_text())
    control_stage_path = HERE / "runs/n83_q1329_planted_unpinned.json"
    control_stage = json.loads(control_stage_path.read_text())
    control_replay_path = HERE / "runs/n83_q1329_planted_independent_replay.json"
    control_replay = json.loads(control_replay_path.read_text())
    ordinary_manifest_path = HERE / "native_inputs/n83_manifest.json"
    reps_path = HERE / "native_inputs/n83_x_representatives.bin"
    base_path = HERE / "bases/n83_weight5_full_orbits.json"
    assert control_fixture["proposal_id"] == control_manifest[
        "proposal_id"] == control_stage["proposal_id"] == control_replay[
            "proposal_id"] == "Q1329"
    assert control_fixture["parent_solver_proposal_id"] == control_manifest[
        "parent_solver_proposal_id"] == "Q1328"
    assert control_fixture["parent_factor_base_proposal_id"] == (
        control_manifest["parent_factor_base_proposal_id"])
    assert control_fixture["parent_factor_base_proposal_id"] == (
        control_stage["parent_factor_base_proposal_id"])
    assert control_fixture["parent_factor_base_proposal_id"] == "Q1325"
    assert control_fixture["curve_id"] == control_manifest[
        "curve_id"] == control_stage["curve_id"] == control_replay[
            "curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert control_fixture["workload_id"] == control_manifest[
        "workload_id"] == control_stage["workload_id"] == control_replay[
            "workload_id"] == "c530b6f0b4dd"
    assert control_fixture["candidate_id"] is control_manifest[
        "candidate_id"] is control_stage["candidate_id"] is control_replay[
            "candidate_id"] is None
    assert control_fixture["run_id"] is control_manifest[
        "run_id"] is control_stage["run_id"] is control_replay[
            "run_id"] is None
    assert control_fixture["isogeny"] == control_manifest[
        "isogeny"] == control_stage["isogeny"] == control_replay[
            "isogeny"] == "none"
    assert control_fixture["source_sha256"] == sha(
        HERE / "make_n83_native_planted_control.py")
    assert control_fixture["ordinary_input_manifest_sha256"] == sha(
        ordinary_manifest_path)
    assert control_fixture["representatives_file_sha256"] == sha(reps_path)
    assert control_fixture["factor_base_actual_B"] == control_manifest[
        "actual_usable_points_B"] == control_stage[
            "actual_usable_points_B"] == 30977592
    assert control_fixture["factor_base_folded_columns_K"] == (
        control_manifest["representative_count_K"])
    assert control_fixture["factor_base_folded_columns_K"] == (
        control_stage["folded_columns_K"])
    assert control_fixture["factor_base_folded_columns_K"] == 186612
    assert control_manifest["source_base_archive_sha256"] == sha(base_path)
    assert control_manifest["runtime_info_sha256"] == sha(native_runtime_path)
    assert control_manifest["target_source_receipt_sha256"] == sha(
        control_fixture_path)
    assert control_manifest["stage_protocol_sha256"] == (
        control_stage["stage_protocol_sha256"])
    assert control_manifest["stage_protocol_sha256"] == sha(control_fixture_path)
    assert control_manifest["source_sha256"] == control_fixture[
        "source_sha256"]
    assert control_stage["native_source_sha256"] == native_build[
        "source_sha256"]
    assert control_stage["cargo_manifest_sha256"] == native_build[
        "cargo_manifest_sha256"]
    assert control_stage["input_representatives_sha256"] == sha(reps_path)
    assert control_stage["status"] == "native_relation_found"
    assert control_stage["relation"]["native_group_sum_verified"] is True
    assert control_stage["index_pair_states_examined"] == 2000000
    assert control_stage["sampling"]["orientations_per_state"] == 83
    assert control_stage["target_states_scanned"] == 1
    assert 1 <= control_stage["target_state_orientations_tested"] <= 83
    assert control_stage["peak_rss_bytes"] <= 1024 ** 3
    assert control_fixture["solver_receives_witness_or_index_positions"] is False
    assert control_fixture["is_natural_yield_measurement"] is False
    assert control_replay["status"] == "PASS"
    assert control_replay["is_natural_yield_measurement"] is False
    assert control_replay["native_relation_independently_verified"] is True
    assert control_replay["four_recovered_points_in_exact_q1325_factor_base"] is True
    assert control_replay["recovered_signed_frobenius_columns"] == 4
    assert control_replay["native_receipt_sha256"] == sha(control_stage_path)
    assert control_replay["native_build_receipt_sha256"] == sha(
        native_build_path)
    assert control_replay["fixture_sha256"] == sha(control_fixture_path)
    assert control_replay["manifest_sha256"] == sha(control_manifest_path)
    assert control_replay["source_sha256"] == sha(
        HERE / "verify_n83_q1329_native_control.py")
    assert control_stage["verified_single_target_dlp"] is False
    assert control_replay["verified_single_target_dlp"] is False
    assert control_stage["complete_work_log2"] is None
    assert control_replay["complete_work_log2"] is None
    for variant, path in (
        ("n83_q1329_planted_fixture", control_fixture_path),
        ("n83_q1329_planted_input", control_manifest_path),
        ("n83_q1329_planted_stage", control_stage_path),
        ("n83_q1329_planted_independent_replay", control_replay_path),
    ):
        rows.append({"variant": variant, "receipt_sha256": sha(path),
                     "is_natural_yield_measurement": False})
    batch_protocol_path = HERE / "q1330_q1331_batch_root_protocol.json"
    batch_protocol = json.loads(batch_protocol_path.read_text())
    assert batch_protocol["kind"] == (
        "bounded_native_four_summand_s3_batch_inversion_stage_protocol")
    assert batch_protocol["candidate_id"] is None
    assert batch_protocol["isogeny"] == "none"
    assert batch_protocol["parent_stage_protocol_sha256"] == sha(
        native_protocol_path)
    assert batch_protocol["native_source_sha256"] == native_batch_build[
        "source_sha256"]
    assert batch_protocol["point_decomposition"]["stage_code"] == "PDP4root"
    assert len(batch_protocol["profiles"]) == 2
    rows.append({"variant": "q1330_q1331_batch_root_protocol",
                 "receipt_sha256": sha(batch_protocol_path)})
    for n, proposal, parent, expected_status, stage_name in (
        (53, "Q1330", "Q1327", "native_relation_found",
         "n53_batch_root_full.json"),
        (83, "Q1331", "Q1328", "state_cap_no_relation",
         "n83_batch_root_capped_2m.json"),
    ):
        profile = next(row for row in batch_protocol["profiles"]
                       if row["field_degree"] == n)
        manifest_path = HERE / "native_inputs" / f"n{n}_batch_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        scalar_manifest_path = HERE / "native_inputs" / f"n{n}_manifest.json"
        scalar_path = HERE / "runs" / (
            "n53_native_root_full.json" if n == 53
            else "n83_native_root_capped_2m.json")
        scalar = json.loads(scalar_path.read_text())
        stage_path = HERE / "runs" / stage_name
        stage = json.loads(stage_path.read_text())
        replay_path = HERE / "runs" / f"n{n}_batch_root_independent_replay.json"
        replay = json.loads(replay_path.read_text())
        assert profile["proposal_id"] == manifest["proposal_id"] == (
            stage["proposal_id"])
        assert profile["proposal_id"] == replay["proposal_id"] == proposal
        assert profile["parent_solver_proposal_id"] == manifest[
            "parent_solver_proposal_id"] == replay[
                "parent_solver_proposal_id"] == parent
        assert manifest["ordinary_input_manifest_sha256"] == profile[
            "ordinary_input_manifest_sha256"] == sha(scalar_manifest_path)
        assert manifest["stage_protocol_sha256"] == stage[
            "stage_protocol_sha256"] == sha(batch_protocol_path)
        assert manifest["source_sha256"] == sha(
            HERE / "freeze_batch_root_protocol.py")
        assert manifest["runtime_info_sha256"] == sha(native_runtime_path)
        assert manifest["s3_batch_size"] == stage[
            "s3_batch_size"] == profile["s3_batch_size"] == 4096
        assert manifest["candidate_id"] is stage["candidate_id"] is None
        assert manifest["run_id"] is stage["run_id"] is None
        assert manifest["isogeny"] == stage["isogeny"] == "none"
        assert stage["native_source_sha256"] == native_batch_build[
            "source_sha256"]
        assert stage["cargo_manifest_sha256"] == native_batch_build[
            "cargo_manifest_sha256"]
        assert stage["status"] == replay[
            "native_stage_status"] == expected_status
        assert stage["verified_single_target_dlp"] is False
        assert stage["complete_work_log2"] is None
        assert stage["peak_rss_bytes"] <= 1024 ** 3
        assert stage["target_states_prepared"] >= stage[
            "target_states_scanned"]
        assert stage["target_state_orientations_prepared"] >= stage[
            "target_state_orientations_tested"]
        assert stage["operation_counts"]["index_build"][
            "s3_root_calls"] == stage["index_pair_states_examined"]
        for key in ("curve_id", "workload_id", "actual_usable_points_B",
                    "folded_columns_K", "index_pair_states_examined",
                    "index_distinct_root_keys", "target_states_scanned",
                    "target_table_hits", "relation"):
            assert stage[key] == scalar[key]
        assert replay["status"] == "PASS"
        assert replay["native_receipt_sha256"] == sha(stage_path)
        assert replay["matched_scalar_stage_sha256"] == sha(scalar_path)
        assert replay["native_build_receipt_sha256"] == sha(
            native_batch_build_path)
        assert replay["source_sha256"] == sha(HERE / "verify_native_s3_root.py")
        assert replay["ordinary_relation_independently_verified"] is (n == 53)
        if n == 53:
            assert replay["rank_of_native_and_matched_pair_rows"] == 2
        else:
            assert replay["censored_ordinary_query"] is True
            assert replay["proves_target_unsupported"] is False
        for variant, path in (
            (f"n{n}_batch_root_input", manifest_path),
            (f"n{n}_batch_root_stage", stage_path),
            (f"n{n}_batch_root_independent_replay", replay_path),
        ):
            rows.append({"variant": variant, "receipt_sha256": sha(path),
                         "proposal_id": proposal})
    coverage_path = HERE / "runs/n83_q1331_uniform_target_coverage_bound.json"
    coverage = json.loads(coverage_path.read_text())
    base_protocol_path = HERE / "q1325_protocol.json"
    base_protocol = json.loads(base_protocol_path.read_text())
    q1331_stage_path = HERE / "runs/n83_batch_root_capped_2m.json"
    q1331_stage = json.loads(q1331_stage_path.read_text())
    n = base_protocol["field"]["n"]
    r = base_protocol["curve"]["subgroup_order"]
    m = q1331_stage["index_pair_states_examined"]
    pair_point_cap = 4 * n * m
    support_cap = min(r - 1, pair_point_cap * (pair_point_cap + 1) // 2)
    assert coverage["kind"] == "fixed_pair_state_uniform_target_support_upper_bound"
    assert coverage["proposal_id"] == q1331_stage["proposal_id"] == "Q1331"
    assert coverage["candidate_id"] is coverage["run_id"] is None
    assert coverage["curve_id"] == q1331_stage["curve_id"] == base_protocol[
        "curve"]["curve_id"]
    assert coverage["workload_id"] == q1331_stage["workload_id"]
    assert coverage["factor_base_enumerated_set_sha256"] == q1331_stage[
        "factor_base_enumerated_set_sha256"]
    assert coverage["field_degree_n"] == n == 83
    assert coverage["subgroup_order_r"] == r
    assert coverage["fixed_index_pair_states_M"] == m == 2_000_000
    assert coverage["pair_group_points_cap_4nM"] == pair_point_cap
    assert coverage["uniform_nonidentity_target_support_cap"] == support_cap
    assert coverage["uniform_nonidentity_target_count"] == r - 1
    assert coverage["q1325_protocol_sha256"] == sha(base_protocol_path)
    assert coverage["q1330_q1331_protocol_sha256"] == sha(batch_protocol_path)
    assert coverage["q1331_stage_receipt_sha256"] == sha(q1331_stage_path)
    assert coverage["source_sha256"] == sha(
        HERE / "screen_q1331_target_coverage.py")
    assert coverage["is_empirical_relation_yield"] is False
    assert coverage["is_complete_solve_projection"] is False
    for label, numerator, denominator in (("50_percent", 1, 2),
                                          ("95_percent", 19, 20)):
        threshold = coverage["necessary_state_count_thresholds"][label][
            "necessary_pair_state_count"]
        for checked_m, should_reach in ((threshold - 1, False),
                                        (threshold, True)):
            candidate_u = 4 * n * checked_m
            reaches = (denominator * candidate_u * (candidate_u + 1)
                       >= 2 * numerator * (r - 1))
            assert reaches is should_reach
    rows.append({"variant": "n83_q1331_uniform_target_coverage_bound",
                 "receipt_sha256": sha(coverage_path),
                 "is_natural_yield_measurement": False})
    primitives_path = HERE / "runs/n53_n83_s3_primitive_field_calls.json"
    primitives = json.loads(primitives_path.read_text())
    assert primitives["kind"] == (
        "source_level_primitive_field_call_expansion_for_s3_stages")
    assert primitives["candidate_id"] is primitives["run_id"] is None
    assert primitives["isogeny"] == "none"
    assert primitives["source_sha256"] == sha(
        HERE / "derive_s3_primitive_calls.py")
    assert primitives["native_build_receipt_sha256"] == sha(
        native_batch_build_path)
    assert primitives["native_source_sha256"] == native_batch_build[
        "source_sha256"]
    assert primitives["field_implementation_source_sha256"] == (
        native_batch_build["crypto_arithmetic_sources_sha256"][
            "src/cryptanalysis/semaev_decomp.rs"])
    assert primitives["is_common_weighted_field_operation_unit"] is False
    assert primitives["is_complete_solve_projection"] is False
    primitive_inputs = (
        (53, "Q1327", "n53_native_root_full.json"),
        (53, "Q1330", "n53_batch_root_full.json"),
        (83, "Q1328", "n83_native_root_capped_2m.json"),
        (83, "Q1331", "n83_batch_root_capped_2m.json"),
    )
    assert len(primitives["rows"]) == len(primitive_inputs)
    for row, (degree, proposal, stage_name) in zip(
            primitives["rows"], primitive_inputs):
        stage_path = HERE / "runs" / stage_name
        stage = json.loads(stage_path.read_text())
        assert row["proposal_id"] == stage["proposal_id"] == proposal
        assert row["n"] == stage["field_degree"] == degree
        assert row["curve_id"] == stage["curve_id"]
        assert row["workload_id"] == stage["workload_id"]
        assert row["stage_receipt_sha256"] == sha(stage_path)
        inner_mul = (degree - 1).bit_length() + (degree - 1).bit_count() - 2
        inner_sqr = degree - 1
        for phase, raw in stage["operation_counts"].items():
            expanded = row["phase_call_vectors"][phase]
            assert expanded["inner_mul_calls_per_nonzero_inv"] == inner_mul
            assert expanded["inner_sqr_calls_per_nonzero_inv"] == inner_sqr
            assert expanded["top_level_field_mul_calls"] == raw[
                "field_mul_calls"]
            assert expanded["top_level_field_sqr_calls"] == raw[
                "field_sqr_calls"]
            assert expanded["top_level_field_inv_calls"] == raw[
                "field_inv_calls"]
            assert expanded["expanded_primitive_field_mul_calls"] == (
                raw["field_mul_calls"] + inner_mul * raw["field_inv_calls"])
            assert expanded["expanded_primitive_field_sqr_calls"] == (
                raw["field_sqr_calls"] + inner_sqr * raw["field_inv_calls"])
    rows.append({"variant": "n53_n83_s3_primitive_field_calls",
                 "receipt_sha256": sha(primitives_path),
                 "is_complete_solve_projection": False})
    q1400_protocol_path = HERE / "q1400_pair_protocol.json"
    q1400_protocol = json.loads(q1400_protocol_path.read_text())
    q1400_input_path = HERE / "native_inputs/n83_q1400_pair_manifest.json"
    q1400_input = json.loads(q1400_input_path.read_text())
    q1400_build_path = HERE / "native_q1400_pair_build_receipt.json"
    q1400_build = json.loads(q1400_build_path.read_text())
    q1400_stage_path = HERE / "runs/n83_q1400_pair_comparator.json"
    q1400_stage = json.loads(q1400_stage_path.read_text())
    q1400_stdout_path = HERE / "runs/n83_q1400_pair_comparator.stdout.txt"
    q1400_stderr_path = HERE / "runs/n83_q1400_pair_comparator.stderr.txt"
    q1400_runtime_path = HERE / "q1400_sage_runtime_info.json"
    q1400_native_source = HERE / "native_q1400_pair_comparator.cpp"
    assert q1400_protocol["proposal_id"] == q1400_input[
        "proposal_id"] == q1400_build["proposal_id"] == q1400_stage[
            "proposal_id"] == "Q1400"
    assert q1400_protocol["candidate_id"] is q1400_input[
        "candidate_id"] is q1400_build["candidate_id"] is q1400_stage[
            "candidate_id"] is None
    assert q1400_protocol["isogeny"] == q1400_input[
        "isogeny"] == q1400_build["isogeny"] == q1400_stage[
            "isogeny"] == "none"
    assert q1400_protocol["curve_id"] == q1400_input[
        "curve_id"] == q1400_stage["curve_id"] == base_protocol[
            "curve"]["curve_id"]
    assert q1400_protocol["workload_id"] == q1400_input[
        "workload_id"] == q1400_stage["workload_id"] == base_protocol[
            "ordinary_workload_id"]
    assert (q1400_protocol["factor_base_enumerated_set_sha256"] ==
            q1400_input["factor_base_enumerated_set_sha256"] ==
            q1400_stage["factor_base_enumerated_set_sha256"] ==
            base_protocol["factor_base"]["enumerated_set_sha256"])
    assert q1400_protocol["point_decomposition"][
        "native_source_sha256"] == sha(q1400_native_source)
    for name, digest in q1400_protocol["point_decomposition"][
            "native_dependency_sha256"].items():
        assert sha(HERE.parents[1] / name) == digest
    assert q1400_protocol["checks"]["native_input_manifest_sha256"] == sha(
        q1400_input_path)
    assert q1400_protocol["checks"]["input_exporter_sha256"] == sha(
        HERE / "export_q1400_pair_inputs.py")
    assert q1400_input["checked_sage_runtime_info_sha256"] == sha(
        q1400_runtime_path)
    assert q1400_input["source_sha256"] == sha(
        HERE / "export_q1400_pair_inputs.py")
    q1400_point_keys_path = HERE / "bases/n83_weight5_full_point_orbits.bin"
    point_keys = q1400_point_keys_path.read_bytes()
    assert len(point_keys) == 21 * q1400_protocol[
        "factor_base_folded_columns_K"]
    padded_hash = hashlib.sha256()
    for offset in range(0, len(point_keys), 21):
        padded_hash.update(point_keys[offset:offset + 21] + b"\0" * 11)
    assert padded_hash.hexdigest() == q1400_input["base_binary_sha256"]
    assert q1400_input["base_binary_bytes"] == 32 * q1400_protocol[
        "factor_base_folded_columns_K"]
    onb83 = field.Onb(83)
    q1325_target = [int(value) for value in base_protocol[
        "ordinary_public_target"]]
    assert q1400_input["ordinary_public_target_onb_hex"] == [
        format(onb83.toCoords(value), "x") for value in q1325_target]
    assert q1400_build["stage_protocol_sha256"] == sha(q1400_protocol_path)
    assert q1400_build["native_source_sha256"] == sha(q1400_native_source)
    assert q1400_build["source_sha256"] == sha(
        HERE / "build_q1400_pair_comparator.py")
    assert q1400_stage["stage_protocol_sha256"] == sha(q1400_protocol_path)
    assert q1400_stage["input_manifest_sha256"] == sha(q1400_input_path)
    assert q1400_stage["native_build_receipt_sha256"] == sha(q1400_build_path)
    assert q1400_stage["source_sha256"] == sha(
        HERE / "run_q1400_pair_comparator.py")
    assert q1400_stage["raw_stdout_sha256"] == sha(q1400_stdout_path)
    assert q1400_stage["raw_stderr_sha256"] == sha(q1400_stderr_path)
    assert q1400_stage["native_output"] == json.loads(
        q1400_stdout_path.read_text())
    assert q1400_stage["status"] == "no_exact_hit_at_cap"
    assert q1400_stage["native_output"]["exact_hit_keys"] == 0
    assert q1400_stage["native_output"]["exact_hit_queries"] == 0
    assert q1400_stage["native_output"]["hits"] == []
    assert q1400_stage["native_output"]["table_descriptors"] == 2_000_000
    assert q1400_stage["native_output"]["lifted_query_pairs"] == 2_719_744
    assert q1400_stage["native_output"]["peak_rss_bytes"] <= 4096 * 1024 ** 2
    q1400_pdp = q1400_protocol["point_decomposition"]
    expected_common_args = [str(q1400_pdp[name]) for name in (
        "table_descriptors", "query_representatives", "table_batch",
        "table_step", "table_offset", "query_step", "query_offset",
        "bloom_bits_per_key", "bloom_hashes", "table_start",
        "query_start", "query_workers", "representative_batch")]
    assert len(q1400_stage["command"]) == 17
    assert q1400_stage["command"][2:4] == q1400_input[
        "ordinary_public_target_onb_hex"]
    assert q1400_stage["command"][4:] == expected_common_args
    assert q1400_stage["target_online_seconds_exploratory"] == (
        q1400_stage["native_output"]["query_seconds"] +
        q1400_stage["native_output"]["exact_replay_seconds"])
    assert q1400_stage["natural_relation_yield_rate_estimate"] is None
    assert q1400_stage["complete_work_log2"] is None
    q1401_protocol_path = HERE / "q1401_pair_control_protocol.json"
    q1401_protocol = json.loads(q1401_protocol_path.read_text())
    q1401_fixture_path = HERE / "runs/n83_q1401_pair_planted_fixture.json"
    q1401_fixture = json.loads(q1401_fixture_path.read_text())
    q1401_stage_path = HERE / "runs/n83_q1401_pair_planted_native.json"
    q1401_stage = json.loads(q1401_stage_path.read_text())
    q1401_stdout_path = HERE / "runs/n83_q1401_pair_planted_native.stdout.txt"
    q1401_stderr_path = HERE / "runs/n83_q1401_pair_planted_native.stderr.txt"
    q1401_replay_path = HERE / "runs/n83_q1401_pair_planted_independent_replay.json"
    q1401_replay = json.loads(q1401_replay_path.read_text())
    assert q1401_protocol["proposal_id"] == q1401_fixture[
        "proposal_id"] == q1401_stage["proposal_id"] == q1401_replay[
            "proposal_id"] == "Q1401"
    assert q1401_protocol["parent_solver_proposal_id"] == "Q1400"
    assert q1401_protocol["workload_id"] == q1401_fixture[
        "workload_id"] == q1401_stage["workload_id"] == q1401_replay[
            "workload_id"]
    assert q1401_protocol["planted_fixture_sha256"] == sha(q1401_fixture_path)
    assert q1401_protocol["fixture_source_sha256"] == sha(
        HERE / "make_q1401_pair_control.py")
    assert q1401_fixture["source_sha256"] == sha(
        HERE / "make_q1401_pair_control.py")
    canonical_workload = json.dumps(
        q1401_fixture["canonical_workload_record"], sort_keys=True,
        separators=(",", ":"), ensure_ascii=False).encode()
    assert hashlib.sha256(canonical_workload).hexdigest()[:12] == (
        q1401_fixture["workload_id"])
    assert q1401_stage["status"] == "native_hit_pending_independent_replay"
    assert q1401_stage["stage_protocol_sha256"] == sha(q1401_protocol_path)
    assert q1401_stage["planted_fixture_sha256"] == sha(q1401_fixture_path)
    assert q1401_stage["raw_stdout_sha256"] == sha(q1401_stdout_path)
    assert q1401_stage["raw_stderr_sha256"] == sha(q1401_stderr_path)
    assert q1401_stage["source_sha256"] == sha(
        HERE / "run_q1401_pair_control.py")
    assert q1401_stage["native_output"] == json.loads(
        q1401_stdout_path.read_text())
    assert len(q1401_stage["command"]) == 17
    assert q1401_stage["command"][2:4] == q1401_fixture[
        "target_onb_coordinate_hex"]
    assert q1401_stage["command"][4:] == expected_common_args
    assert q1401_stage["native_output"]["exact_hit_keys"] >= 1
    assert q1401_replay["status"] == "PASS"
    assert q1401_replay["native_receipt_sha256"] == sha(q1401_stage_path)
    assert q1401_replay["fixture_sha256"] == sha(q1401_fixture_path)
    assert q1401_replay["source_sha256"] == sha(
        HERE / "verify_q1401_pair_control.py")
    assert q1401_replay["verified_relation_count"] >= 1
    assert all(hit["target_sum_verified"] and hit[
        "four_distinct_signed_frobenius_columns"]
               for hit in q1401_replay["verified_hits"])
    assert q1401_replay["is_natural_relation_yield_measurement"] is False
    assert q1401_replay["verified_single_target_dlp"] is False
    for variant, path in (
        ("q1400_pair_protocol", q1400_protocol_path),
        ("q1400_checked_sage_runtime", q1400_runtime_path),
        ("q1400_native_input", q1400_input_path),
        ("q1400_native_build", q1400_build_path),
        ("q1400_ordinary_stage", q1400_stage_path),
        ("q1400_ordinary_stdout", q1400_stdout_path),
        ("q1400_ordinary_stderr", q1400_stderr_path),
        ("q1401_control_protocol", q1401_protocol_path),
        ("q1401_planted_fixture", q1401_fixture_path),
        ("q1401_native_stage", q1401_stage_path),
        ("q1401_native_stdout", q1401_stdout_path),
        ("q1401_native_stderr", q1401_stderr_path),
        ("q1401_independent_replay", q1401_replay_path),
    ):
        rows.append({"variant": variant, "receipt_sha256": sha(path),
                     "is_natural_yield_measurement": False})
    from screen_q1402_fixed_pair_family import build as build_q1402_screen
    q1402_path = HERE / "runs/n83_n131_q1402_fixed_pair_family_screen.json"
    q1402 = json.loads(q1402_path.read_text())
    assert q1402 == build_q1402_screen()
    assert q1402["source_sha256"] == sha(
        HERE / "screen_q1402_fixed_pair_family.py")
    assert q1402["q1400_protocol_sha256"] == sha(q1400_protocol_path)
    assert q1402["q1400_ordinary_stage_sha256"] == sha(q1400_stage_path)
    assert q1402["proposal_id"] == "Q1402"
    assert q1402["candidate_id"] is q1402["run_id"] is None
    assert q1402["isogeny"] == "none"
    assert q1402["n83_exact_q1325_measured_rectangle"]["support_ceiling"][
        "uniform_nonidentity_target_support_numerator_cap"] == (
            4 * 83 * 83 * 2_000_000 * 16_384)
    n131_screen = q1402["n131_conditional_q1303_full_table"]
    assert n131_screen["exact_factor_base_B"] is None
    n131 = n131_screen["field_degree_n"]
    r131 = n131_screen["subgroup_order_r"]
    assert n131 == 131
    for case_name in ("estimated_K_case",
                      "upper_95_percent_K_case_not_hard_bound"):
        case = n131_screen[case_name]
        m = case["generous_full_table_descriptor_cap_M"]
        for threshold, numerator, denominator in (("one_percent", 1, 100),
                                                  ("fifty_percent", 1, 2)):
            necessary_r = case[
                "necessary_queries_for_uniform_target_support"][threshold][
                    "necessary_query_representatives"]
            capacity = denominator * 4 * n131 * n131 * m
            assert necessary_r * capacity >= numerator * (r131 - 1)
            assert (necessary_r - 1) * capacity < numerator * (r131 - 1)
        online_cap = n131_screen["query_representative_cap_for_screen"]
        assert online_cap == 1 << 31
        assert case["support_ceiling_at_2pow31_query_representatives"][
            "uniform_nonidentity_target_support_numerator_cap"] == (
                min(r131 - 1, 4 * n131 * n131 * m * online_cap))
    assert q1402["is_empirical_relation_yield"] is False
    assert q1402["is_complete_solve_projection"] is False
    assert q1402["challenge_dispatch_allowed"] is False
    rows.append({"variant": "q1402_fixed_pair_family_counting_screen",
                 "receipt_sha256": sha(q1402_path),
                 "is_natural_yield_measurement": False})
    from derive_q1400_primitive_calls import build as build_q1400_calls
    q1400_calls_path = HERE / "runs/n83_q1400_primitive_field_calls.json"
    q1400_calls = json.loads(q1400_calls_path.read_text())
    assert q1400_calls == build_q1400_calls()
    assert q1400_calls["source_sha256"] == sha(
        HERE / "derive_q1400_primitive_calls.py")
    assert q1400_calls["q1400_protocol_sha256"] == sha(q1400_protocol_path)
    assert q1400_calls["q1400_stage_receipt_sha256"] == sha(q1400_stage_path)
    assert q1400_calls["proposal_id"] == "Q1400"
    assert q1400_calls["candidate_id"] is q1400_calls["run_id"] is None
    assert q1400_calls["isogeny"] == "none"
    calls = q1400_calls["phase_call_vectors"]
    m = q1400_protocol["point_decomposition"]["table_descriptors"]
    r = q1400_protocol["point_decomposition"]["query_representatives"]
    table_batches = (m + 4095) // 4096
    query_batches = (r + 15) // 16
    assert calls["target_independent_base_orbit_expansion"][
        "expanded_primitive_field_sqr_calls"] == (
            2 * 83 * q1400_protocol["factor_base_folded_columns_K"])
    assert calls["target_independent_table_build"][
        "expanded_primitive_field_mul_calls"] == 5 * m + 8 * table_batches
    assert calls["target_independent_table_build"][
        "expanded_primitive_field_sqr_calls"] == m + 82 * table_batches
    assert calls["target_query_pair_build"][
        "expanded_primitive_field_mul_calls"] == 5 * r + 8 * query_batches
    assert calls["target_signed_complement"][
        "expanded_primitive_field_mul_calls"] == 5 * r * 83 + 8 * query_batches
    assert calls["target_signed_complement"][
        "expanded_primitive_field_sqr_calls"] == 2 * r * 83 + 82 * query_batches
    assert calls["target_frobenius_setup_untimed"][
        "expanded_primitive_field_sqr_calls"] == 2 * 83
    assert calls["target_exact_table_replay"] == calls[
        "target_independent_table_build"]
    assert q1400_calls["target_dependent_phase_sum_including_untimed_frobenius"][
        "expanded_primitive_field_mul_calls"] == 16_901_576
    assert q1400_calls["target_dependent_phase_sum_including_untimed_frobenius"][
        "expanded_primitive_field_sqr_calls"] == 4_944_328
    assert q1400_calls["wall_timing_boundary"][
        "all_target_dependent_wall_seconds"] is None
    assert q1400_calls["is_common_weighted_field_operation_unit"] is False
    assert q1400_calls["is_complete_solve_projection"] is False
    rows.append({"variant": "q1400_primitive_field_calls",
                 "receipt_sha256": sha(q1400_calls_path),
                 "is_natural_yield_measurement": False})
    planted_protocol_path = HERE / "q1332_batch_planted_control_protocol.json"
    planted_protocol = json.loads(planted_protocol_path.read_text())
    planted_manifest_path = HERE / "native_inputs/n83_batch_planted_manifest.json"
    planted_manifest = json.loads(planted_manifest_path.read_text())
    planted_stage_path = HERE / "runs/n83_q1332_batch_planted_unpinned.json"
    planted_stage = json.loads(planted_stage_path.read_text())
    planted_replay_path = HERE / "runs/n83_q1332_batch_planted_independent_replay.json"
    planted_replay = json.loads(planted_replay_path.read_text())
    assert planted_protocol["proposal_id"] == planted_manifest[
        "proposal_id"] == planted_stage["proposal_id"] == planted_replay[
            "proposal_id"] == "Q1332"
    assert planted_protocol["parent_solver_proposal_id"] == planted_manifest[
        "parent_solver_proposal_id"] == "Q1331"
    assert planted_protocol["parent_planted_control_proposal_id"] == (
        planted_manifest["parent_planted_control_proposal_id"])
    assert planted_protocol["parent_planted_control_proposal_id"] == "Q1329"
    assert planted_protocol["planted_fixture_sha256"] == planted_manifest[
        "planted_fixture_sha256"] == planted_replay["fixture_sha256"] == sha(
            control_fixture_path)
    assert planted_protocol["parent_manifest_sha256"] == planted_manifest[
        "parent_manifest_sha256"] == sha(control_manifest_path)
    assert planted_protocol["batch_protocol_sha256"] == sha(batch_protocol_path)
    assert planted_protocol["native_source_sha256"] == native_batch_build[
        "source_sha256"]
    assert planted_manifest["stage_protocol_sha256"] == planted_stage[
        "stage_protocol_sha256"] == planted_replay[
            "batch_protocol_sha256"] == sha(planted_protocol_path)
    assert planted_manifest["source_sha256"] == sha(
        HERE / "freeze_batch_planted_control.py")
    assert planted_stage["native_source_sha256"] == native_batch_build[
        "source_sha256"]
    assert planted_stage["s3_batch_size"] == planted_protocol[
        "s3_batch_size"] == 4096
    assert planted_stage["sampling"]["orientations_per_state"] == 83
    assert planted_stage["status"] == "native_relation_found"
    assert planted_stage["relation"] == control_stage["relation"]
    assert planted_stage["target_states_scanned"] == 1
    assert planted_stage["target_state_orientations_tested"] == 34
    assert planted_stage["target_states_prepared"] == 4096
    assert planted_stage["peak_rss_bytes"] <= 1024 ** 3
    assert planted_replay["status"] == "PASS"
    assert planted_replay["is_natural_yield_measurement"] is False
    assert planted_replay["native_relation_independently_verified"] is True
    assert planted_replay["four_recovered_points_in_exact_q1325_factor_base"] is True
    assert planted_replay["native_receipt_sha256"] == sha(planted_stage_path)
    assert planted_replay["matched_unbatched_relation_receipt_sha256"] == sha(
        control_stage_path)
    assert planted_replay["source_sha256"] == sha(
        HERE / "verify_n83_q1329_native_control.py")
    assert planted_stage["verified_single_target_dlp"] is False
    assert planted_stage["complete_work_log2"] is None
    for variant, path in (
        ("q1332_batch_planted_protocol", planted_protocol_path),
        ("n83_q1332_batch_planted_input", planted_manifest_path),
        ("n83_q1332_batch_planted_stage", planted_stage_path),
        ("n83_q1332_batch_planted_independent_replay", planted_replay_path),
    ):
        rows.append({"variant": variant, "receipt_sha256": sha(path),
                     "is_natural_yield_measurement": False})
    q1403_protocol_path = HERE / "q1403_ordered_q1325_protocol.json"
    q1403_protocol = json.loads(q1403_protocol_path.read_text())
    q1403_runtime_path = HERE / "q1403_sage_runtime_info.json"
    assert json.loads(q1403_runtime_path.read_text())["status"] == "verified"
    assert q1403_protocol["proposal_id"] == "Q1403"
    assert q1403_protocol["candidate_id"] is None
    assert q1403_protocol["isogeny"] == "none"
    assert q1403_protocol["parent_factor_base_proposal_id"] == "Q1325"
    assert q1403_protocol["ordinary_workload_id"] == "bab50a1e5f66"
    assert q1403_protocol["factor_base_actual_B"] == 30_977_592
    assert q1403_protocol["factor_base_folded_columns"] == 186_612
    for source, digest in q1403_protocol["source_sha256"].items():
        assert digest == sha(HERE / source)
    for mode, expected_status, expected_hits in (
        ("planted_locked", "sat", 1),
        ("planted_unpinned", "external_timeout", 0),
        ("ordinary", "external_timeout", 0),
    ):
        stem = f"n83_q1403_{mode}"
        receipt_path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["proposal_id"] == "Q1403"
        assert receipt["candidate_id"] is receipt["run_id"] is None
        assert receipt["curve_id"] == q1403_protocol["curve_id"]
        assert receipt["isogeny"] == "none"
        assert receipt["mode"] == mode
        assert receipt["status"] == expected_status
        assert receipt["observed_verified_relation_count"] == expected_hits
        assert receipt["factor_base_actual_B"] == q1403_protocol[
            "factor_base_actual_B"]
        assert receipt["factor_base_folded_columns"] == q1403_protocol[
            "factor_base_folded_columns"]
        assert receipt["factor_base_enumerated_set_sha256"] == (
            q1403_protocol["factor_base_enumerated_set_sha256"])
        assert receipt["protocol_sha256"] == sha(q1403_protocol_path)
        assert receipt["runtime_info_sha256"] == sha(q1403_runtime_path)
        assert receipt["source_sha256"] == q1403_protocol["source_sha256"]
        assert receipt["solver_stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.stderr.txt")
        assert receipt["complete_solve_work_log2"] is None
        assert receipt["natural_relation_yield_estimate"] is None
        if mode == "ordinary":
            assert receipt["workload_id"] == q1403_protocol[
                "ordinary_workload_id"]
            assert [str(v) for v in receipt["public_target"]] == (
                q1403_protocol["ordinary_public_target"])
            assert receipt["target_pdp_wall_seconds"] >= 120
        else:
            assert receipt["workload_id"] is None
            assert receipt["control_pdp_wall_seconds"] is not None
        formula_digest = hashlib.sha256()
        formula_bytes = 0
        with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                formula_digest.update(chunk)
                formula_bytes += len(chunk)
        assert formula_digest.hexdigest() == receipt["xcnf_sha256"]
        assert formula_bytes == receipt["xcnf_bytes"]
        rows.append({"variant": stem, "receipt_sha256": sha(receipt_path),
                     "formula_sha256": formula_digest.hexdigest(),
                     "is_natural_yield_measurement": False})
    q1403_replay_path = HERE / "runs/n83_q1403_ordered_control_replay.json"
    q1403_replay = json.loads(q1403_replay_path.read_text())
    assert q1403_replay["status"] == "PASS"
    assert q1403_replay["proposal_id"] == "Q1403"
    assert q1403_replay["protocol_sha256"] == sha(q1403_protocol_path)
    assert q1403_replay["source_sha256"] == sha(
        HERE / "verify_q1403_ordered_control.py")
    assert q1403_replay["locked_stage_sha256"] == sha(
        HERE / "runs/n83_q1403_planted_locked.json")
    assert q1403_replay["ordinary_stage_sha256"] == sha(
        HERE / "runs/n83_q1403_ordinary.json")
    assert q1403_replay["unpinned_stage_sha256"] == sha(
        HERE / "runs/n83_q1403_planted_unpinned.json")
    assert q1403_replay["verified_control_relation_count"] == 1
    assert q1403_replay["ordinary_relation_count"] == 0
    assert q1403_replay["complete_work_log2"] is None
    for variant, path in (
        ("q1403_ordered_protocol", q1403_protocol_path),
        ("q1403_checked_sage_runtime", q1403_runtime_path),
        ("q1403_independent_control_replay", q1403_replay_path),
    ):
        rows.append({"variant": variant, "receipt_sha256": sha(path),
                     "is_natural_yield_measurement": False})
    from build_q1403_stage_comparison import build as build_q1403_comparison
    q1403_comparison_path = HERE / "runs/n83_q1325_q1403_named_stage_comparison.json"
    q1403_comparison = json.loads(q1403_comparison_path.read_text())
    assert q1403_comparison == build_q1403_comparison()
    assert q1403_comparison["source_sha256"] == sha(
        HERE / "build_q1403_stage_comparison.py")
    assert [row["proposal_id"] for row in q1403_comparison[
        "stage_profiles"]] == ["Q1325", "Q1403"]
    assert len(set(row["stage_config_id"] for row in q1403_comparison[
        "stage_profiles"])) == 2
    for profile in q1403_comparison["stage_profiles"]:
        assert profile["candidate_id"] is None
        assert profile["run_id"] == (profile["stage_config_id"] + "W"
                                     + profile["workload_id"] + "R1")
        assert profile["complete_solve_work_log2"] is None
    rows.append({"variant": "q1325_q1403_named_stage_comparison",
                 "receipt_sha256": sha(q1403_comparison_path),
                 "is_natural_yield_measurement": False})
    q1404_protocol_path = HERE / "q1404_raw_preimage_w5_protocol.json"
    q1404_protocol = json.loads(q1404_protocol_path.read_text())
    q1404_runtime_path = HERE / "q1404_sage_runtime_info.json"
    assert json.loads(q1404_runtime_path.read_text())["status"] == "verified"
    assert q1404_protocol["proposal_id"] == "Q1404"
    assert q1404_protocol["candidate_id"] is None
    assert q1404_protocol["isogeny"] == "none"
    assert q1404_protocol["parent_factor_base_proposal_id"] == "Q1325"
    assert q1404_protocol["ordinary_workload_id"] == "bab50a1e5f66"
    assert q1404_protocol["factor_base_actual_B"] == 30_977_592
    assert q1404_protocol["factor_base_folded_columns"] == 186_612
    assert q1404_protocol["ordinary_coset_receipt_sha256"] == sha(
        HERE / "runs/n83_ordinary_raw_preimages.json")
    for source, digest in q1404_protocol["source_sha256"].items():
        assert digest == sha(HERE.parents[1] / source)
    for mode, expected_status, expected_hits in (
        ("planted_locked", "sat", 1),
        ("planted_unpinned", "external_timeout", 0),
        ("ordinary", "censored", 0),
    ):
        stem = f"n83_q1404_{mode}"
        receipt_path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["proposal_id"] == "Q1404"
        assert receipt["candidate_id"] is receipt["run_id"] is None
        assert receipt["curve_id"] == q1404_protocol["curve_id"]
        assert receipt["isogeny"] == "none"
        assert receipt["mode"] == mode
        assert receipt["status"] == expected_status
        assert receipt["observed_verified_relation_count"] == expected_hits
        assert receipt["factor_base_actual_B"] == q1404_protocol[
            "factor_base_actual_B"]
        assert receipt["factor_base_folded_columns"] == q1404_protocol[
            "factor_base_folded_columns"]
        assert receipt["factor_base_enumerated_set_sha256"] == (
            q1404_protocol["factor_base_enumerated_set_sha256"])
        assert receipt["raw_preimage_count"] == 4
        assert len(set(receipt["raw_preimage_x_coordinates"])) == 4
        assert receipt["protocol_sha256"] == sha(q1404_protocol_path)
        assert receipt["runtime_info_sha256"] == sha(q1404_runtime_path)
        assert receipt["source_sha256"] == q1404_protocol["source_sha256"]
        assert receipt["complete_solve_work_log2"] is None
        assert receipt["natural_relation_yield_rate_estimate"] is None
        assert len(receipt["attempts"]) == 1
        attempt = receipt["attempts"][0]
        assert attempt["status"] == expected_status
        assert attempt["solver_stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.attempt0.stdout.txt")
        assert attempt["solver_stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.attempt0.stderr.txt")
        formula_digest = hashlib.sha256()
        formula_bytes = 0
        with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                formula_digest.update(chunk)
                formula_bytes += len(chunk)
        assert formula_digest.hexdigest() == attempt["xcnf_sha256"]
        assert formula_bytes == attempt["xcnf_bytes"]
        if mode == "ordinary":
            assert receipt["workload_id"] == q1404_protocol[
                "ordinary_workload_id"]
            assert attempt["solver_conflicts_reported"] > 1_000_000
            assert receipt["target_preimage_wall_seconds"] > 0
            assert receipt["target_pdp_wall_seconds"] > 0
            assert receipt["target_dependent_stage_wall_seconds"] >= 0
            assert math.isclose(
                receipt["target_dependent_stage_wall_seconds"],
                receipt["target_preimage_wall_seconds"]
                + receipt["target_pdp_wall_seconds"]
                + receipt["target_relation_check_wall_seconds"],
                rel_tol=0, abs_tol=1e-9)
            assert receipt["artifact_instrument_wall_seconds_excluded"] > 0
            assert receipt["ordinary_coset_receipt_sha256"] == sha(
                HERE / "runs/n83_ordinary_raw_preimages.json")
        else:
            assert receipt["workload_id"] is None
            assert receipt["control_stage_wall_seconds"] > 0
        rows.append({"variant": stem, "receipt_sha256": sha(receipt_path),
                     "formula_sha256": formula_digest.hexdigest(),
                     "is_natural_yield_measurement": False})
    q1404_replay_path = HERE / "runs/n83_q1404_raw_control_replay.json"
    q1404_replay = json.loads(q1404_replay_path.read_text())
    assert q1404_replay["status"] == "PASS"
    assert q1404_replay["proposal_id"] == "Q1404"
    assert q1404_replay["protocol_sha256"] == sha(q1404_protocol_path)
    assert q1404_replay["source_sha256"] == sha(
        HERE / "verify_q1404_raw_control.py")
    assert q1404_replay["locked_stage_sha256"] == sha(
        HERE / "runs/n83_q1404_planted_locked.json")
    assert q1404_replay["ordinary_stage_sha256"] == sha(
        HERE / "runs/n83_q1404_ordinary.json")
    assert q1404_replay["unpinned_stage_sha256"] == sha(
        HERE / "runs/n83_q1404_planted_unpinned.json")
    assert q1404_replay["verified_control_relation_count"] == 1
    assert q1404_replay["ordinary_relation_count"] == 0
    assert q1404_replay["four_distinct_columns"] is True
    assert q1404_replay["complete_work_log2"] is None
    from build_q1404_stage_comparison import build as build_q1404_comparison
    q1404_comparison_path = HERE / "runs/n83_q1325_q1404_named_stage_comparison.json"
    q1404_comparison = json.loads(q1404_comparison_path.read_text())
    assert q1404_comparison == build_q1404_comparison()
    assert q1404_comparison["source_sha256"] == sha(
        HERE / "build_q1404_stage_comparison.py")
    assert [row["proposal_id"] for row in q1404_comparison[
        "stage_profiles"]] == ["Q1325", "Q1404"]
    for profile in q1404_comparison["stage_profiles"]:
        assert profile["candidate_id"] is None
        assert profile["run_id"] == (profile["stage_config_id"] + "W"
                                     + profile["workload_id"] + "R1")
        assert profile["complete_solve_work_log2"] is None
    for variant, path in (
        ("q1404_raw_preimage_protocol", q1404_protocol_path),
        ("q1404_checked_sage_runtime", q1404_runtime_path),
        ("q1404_independent_control_replay", q1404_replay_path),
        ("q1325_q1404_named_stage_comparison", q1404_comparison_path),
    ):
        rows.append({"variant": variant, "receipt_sha256": sha(path),
                     "is_natural_yield_measurement": False})
    q1408_protocol_path = HERE / "q1408_balanced_s3_w5_protocol.json"
    q1408_protocol = json.loads(q1408_protocol_path.read_text())
    q1408_runtime_path = HERE / "q1408_sage_runtime_info.json"
    assert json.loads(q1408_runtime_path.read_text())["status"] == "verified"
    assert q1408_protocol["proposal_id"] == "Q1408"
    assert q1408_protocol["candidate_id"] is None
    assert q1408_protocol["isogeny"] == "none"
    for field_name in ("curve_id", "factor_base_actual_B",
                       "factor_base_folded_columns",
                       "factor_base_enumerated_set_sha256",
                       "ordinary_workload_id"):
        assert q1408_protocol[field_name] == q1404_protocol[field_name]
    for source, digest in q1408_protocol["source_sha256"].items():
        assert digest == sha(HERE.parents[1] / source)
    for mode, expected_status, expected_hits in (
        ("planted_locked", "sat", 1),
        ("planted_unpinned", "external_timeout", 0),
        ("ordinary", "censored", 0),
    ):
        stem = f"n83_q1408_{mode}"
        path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(path.read_text())
        assert receipt["proposal_id"] == "Q1408"
        assert receipt["candidate_id"] is receipt["run_id"] is None
        assert receipt["curve_id"] == q1408_protocol["curve_id"]
        assert receipt["mode"] == mode
        assert receipt["status"] == expected_status
        assert receipt["observed_verified_relation_count"] == expected_hits
        assert receipt["protocol_sha256"] == sha(q1408_protocol_path)
        assert receipt["runtime_info_sha256"] == sha(q1408_runtime_path)
        assert receipt["source_sha256"] == q1408_protocol["source_sha256"]
        assert receipt["complete_solve_work_log2"] is None
        assert receipt["natural_relation_yield_rate_estimate"] is None
        assert len(receipt["attempts"]) == 1
        attempt = receipt["attempts"][0]
        assert attempt["status"] == expected_status
        assert attempt["solver_stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.attempt0.stdout.txt")
        assert attempt["solver_stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.attempt0.stderr.txt")
        formula_digest = hashlib.sha256()
        formula_bytes = 0
        with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                formula_digest.update(chunk)
                formula_bytes += len(chunk)
        assert formula_digest.hexdigest() == attempt["xcnf_sha256"]
        assert formula_bytes == attempt["xcnf_bytes"]
        if mode == "ordinary":
            assert receipt["workload_id"] == q1408_protocol[
                "ordinary_workload_id"]
            assert attempt["solver_conflicts_reported"] > 1_000_000
            assert math.isclose(
                receipt["target_dependent_stage_wall_seconds"],
                receipt["target_preimage_wall_seconds"]
                + receipt["target_pdp_wall_seconds"]
                + receipt["target_relation_check_wall_seconds"],
                rel_tol=0, abs_tol=1e-9)
        else:
            assert receipt["workload_id"] is None
        rows.append({"variant": stem, "receipt_sha256": sha(path),
                     "formula_sha256": formula_digest.hexdigest(),
                     "is_natural_yield_measurement": False})
    q1408_replay_path = HERE / "runs/n83_q1408_balanced_control_replay.json"
    q1408_replay = json.loads(q1408_replay_path.read_text())
    assert q1408_replay["status"] == "PASS"
    assert q1408_replay["proposal_id"] == "Q1408"
    assert q1408_replay["source_sha256"] == sha(
        HERE / "verify_q1408_balanced_control.py")
    assert q1408_replay["protocol_sha256"] == sha(q1408_protocol_path)
    assert q1408_replay["verified_control_relation_count"] == 1
    assert q1408_replay["ordinary_relation_count"] == 0
    assert q1408_replay["complete_work_log2"] is None
    from build_q1408_stage_comparison import build as build_q1408_comparison
    q1408_comparison_path = HERE / "runs/n83_q1404_q1408_named_stage_comparison.json"
    q1408_comparison = json.loads(q1408_comparison_path.read_text())
    assert q1408_comparison == build_q1408_comparison()
    assert [row["proposal_id"] for row in q1408_comparison[
        "stage_profiles"]] == ["Q1404", "Q1408"]
    for profile in q1408_comparison["stage_profiles"]:
        assert profile["candidate_id"] is None
        assert profile["run_id"] == (profile["stage_config_id"] + "W"
                                     + profile["workload_id"] + "R1")
    for variant, path in (
        ("q1408_balanced_protocol", q1408_protocol_path),
        ("q1408_checked_sage_runtime", q1408_runtime_path),
        ("q1408_independent_control_replay", q1408_replay_path),
        ("q1404_q1408_named_stage_comparison", q1408_comparison_path),
    ):
        rows.append({"variant": variant, "receipt_sha256": sha(path),
                     "is_natural_yield_measurement": False})
    q1409_protocol_path = HERE / "q1409_balanced_s3_n53_protocol.json"
    q1409_protocol = json.loads(q1409_protocol_path.read_text())
    q1409_failure_path = HERE / "runs/n53_q1409_planted_locked_verification_failure.json"
    q1409_failure = json.loads(q1409_failure_path.read_text())
    assert q1409_protocol["proposal_id"] == q1409_failure[
        "proposal_id"] == "Q1409"
    assert q1409_failure["status"] == "verification_failed"
    assert q1409_failure["verified_relation"] is None
    assert q1409_failure["protocol_sha256"] == sha(q1409_protocol_path)
    assert q1409_failure["runner_source_sha256"] == sha(
        HERE / "run_q1409_balanced_s3_n53.py")
    assert q1409_failure["runtime_info_sha256"] == sha(
        HERE / "q1409_sage_runtime_info.json")
    for source, digest in q1409_protocol["source_sha256"].items():
        assert digest == sha(HERE.parents[1] / source)
    assert q1409_failure["solver_stdout_sha256"] == sha(
        HERE / "runs/n53_q1409_planted_locked.attempt0.stdout.txt")
    assert "s SATISFIABLE" in (HERE / "runs/n53_q1409_planted_locked.attempt0.stdout.txt").read_text()
    assert q1409_failure["solver_stderr_sha256"] == sha(
        HERE / "runs/n53_q1409_planted_locked.attempt0.stderr.txt")
    q1409_digest = hashlib.sha256()
    q1409_bytes = 0
    with gzip.open(HERE / "runs" / q1409_failure["xcnf_archive"], "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            q1409_digest.update(chunk)
            q1409_bytes += len(chunk)
    assert q1409_digest.hexdigest() == q1409_failure["xcnf_sha256"]
    assert q1409_bytes == q1409_failure["xcnf_bytes"]
    q1410_protocol_path = HERE / "q1410_balanced_s3_n53_protocol.json"
    q1410_protocol = json.loads(q1410_protocol_path.read_text())
    q1410_runtime_path = HERE / "q1410_sage_runtime_info.json"
    assert json.loads(q1410_runtime_path.read_text())["status"] == "verified"
    assert q1410_protocol["proposal_id"] == "Q1410"
    assert q1410_protocol["candidate_id"] is None
    assert q1410_protocol["isogeny"] == "none"
    assert q1410_protocol["q1409_preflight_failure_sha256"] == sha(
        q1409_failure_path)
    for source, digest in q1410_protocol["source_sha256"].items():
        assert digest == sha(HERE.parents[1] / source)
    for mode, expected_status, expected_hits in (
        ("witness_locked", "sat", 1),
        ("ordinary", "censored", 0),
    ):
        stem = f"n53_q1410_{mode}"
        path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(path.read_text())
        assert receipt["proposal_id"] == "Q1410"
        assert receipt["candidate_id"] is receipt["run_id"] is None
        assert receipt["mode"] == mode
        assert receipt["status"] == expected_status
        assert receipt["observed_verified_relation_count"] == expected_hits
        assert receipt["curve_id"] == q1410_protocol["curve_id"]
        assert receipt["factor_base_actual_B"] == q1410_protocol[
            "factor_base_actual_B"]
        assert receipt["factor_base_folded_columns"] == q1410_protocol[
            "factor_base_folded_columns"]
        assert receipt["factor_base_enumerated_set_sha256"] == (
            q1410_protocol["factor_base_enumerated_set_sha256"])
        assert receipt["raw_preimage_count"] == 428
        assert receipt["protocol_sha256"] == sha(q1410_protocol_path)
        assert receipt["runtime_info_sha256"] == sha(q1410_runtime_path)
        assert receipt["source_sha256"] == q1410_protocol["source_sha256"]
        assert receipt["complete_solve_work_log2"] is None
        assert len(receipt["attempts"]) == 1
        attempt = receipt["attempts"][0]
        assert attempt["status"] == expected_status
        assert attempt["solver_stdout_sha256"] == sha(
            HERE / "runs" / f"{stem}.attempt0.stdout.txt")
        assert attempt["solver_stderr_sha256"] == sha(
            HERE / "runs" / f"{stem}.attempt0.stderr.txt")
        formula_digest = hashlib.sha256()
        formula_bytes = 0
        with gzip.open(HERE / "runs" / f"{stem}.xcnf.gz", "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                formula_digest.update(chunk)
                formula_bytes += len(chunk)
        assert formula_digest.hexdigest() == attempt["xcnf_sha256"]
        assert formula_bytes == attempt["xcnf_bytes"]
        if mode == "ordinary":
            assert receipt["workload_id"] == q1410_protocol[
                "ordinary_workload_id"]
            assert attempt["solver_conflicts_reported"] > 1_000_000
            assert math.isclose(
                receipt["target_dependent_stage_wall_seconds"],
                receipt["target_preimage_wall_seconds"]
                + receipt["target_pdp_wall_seconds"]
                + receipt["target_relation_check_wall_seconds"],
                rel_tol=0, abs_tol=1e-9)
        else:
            assert receipt["workload_id"] is None
            assert receipt["control_stage_wall_seconds"] > 0
            assert attempt["four_distinct_columns"] is True
        rows.append({"variant": stem, "receipt_sha256": sha(path),
                     "formula_sha256": formula_digest.hexdigest(),
                     "is_natural_yield_measurement": False})
    q1410_replay_path = HERE / "runs/n53_q1410_balanced_control_replay.json"
    q1410_replay = json.loads(q1410_replay_path.read_text())
    assert q1410_replay["status"] == "PASS"
    assert q1410_replay["proposal_id"] == "Q1410"
    assert q1410_replay["locked_control_distinct_columns"] == 4
    assert q1410_replay["ordinary_relation_count"] == 0
    assert q1410_replay["protocol_sha256"] == sha(q1410_protocol_path)
    assert q1410_replay["source_sha256"] == sha(
        HERE / "verify_q1410_n53_balanced.py")
    from build_q1410_stage_comparison import build as build_q1410_comparison
    q1410_comparison_path = HERE / "runs/n53_q1410_n83_q1408_balanced_stage_comparison.json"
    assert json.loads(q1410_comparison_path.read_text()) == build_q1410_comparison()
    for variant, path in (
        ("q1409_failed_protocol", q1409_protocol_path),
        ("q1409_verification_failure", q1409_failure_path),
        ("q1410_corrected_protocol", q1410_protocol_path),
        ("q1410_checked_sage_runtime", q1410_runtime_path),
        ("q1410_independent_control_replay", q1410_replay_path),
        ("q1410_cross_degree_named_stage_comparison", q1410_comparison_path),
    ):
        rows.append({"variant": variant, "receipt_sha256": sha(path),
                     "is_natural_yield_measurement": False})
    return rows


if __name__ == "__main__":
    print(json.dumps({"verified": verify()}, indent=2))
