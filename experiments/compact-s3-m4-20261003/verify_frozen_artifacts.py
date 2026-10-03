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
    return rows


if __name__ == "__main__":
    print(json.dumps({"verified": verify()}, indent=2))
