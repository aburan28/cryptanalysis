#!/usr/bin/env python3
"""Check source, solver logs, and gzip XCNF archives against frozen receipts."""

import base64
import gzip
import hashlib
import json
from pathlib import Path

from run_probe import HERE, sha


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
    return rows


if __name__ == "__main__":
    print(json.dumps({"verified": verify()}, indent=2))
