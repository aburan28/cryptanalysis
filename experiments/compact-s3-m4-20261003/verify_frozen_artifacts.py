#!/usr/bin/env python3
"""Check source, solver logs, and gzip XCNF archives against frozen receipts."""

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
    for stem in ("n53_planted_multitarget_locked_verify",
                 "n53_ordinary_multitarget_locked_verify",
                 "n83_planted_multitarget_locked_verify"):
        path = HERE / "runs" / f"{stem}.json"
        receipt = json.loads(path.read_text())
        assert receipt["source_sha256"] == sha(
            HERE / "verify_multitarget_witness.py")
        assert receipt["relation"] is not None
        rows.append({"variant": stem, "receipt_sha256": sha(path)})
    return rows


if __name__ == "__main__":
    print(json.dumps({"verified": verify()}, indent=2))
