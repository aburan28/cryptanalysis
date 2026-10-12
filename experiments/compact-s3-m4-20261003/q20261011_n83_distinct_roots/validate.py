#!/usr/bin/env python3
"""Check Q1479 source/log identity, branch replay, and exact root outcomes."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1478 = PARENT / "q20261011_n83_leaf_exposure"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT.parent.parent / "ecc2k130/codegen"))
from chain_s3 import evaluate_s3  # noqa: E402
from field import Onb  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exact_root_count(onb: Onb, a: int, b: int) -> int:
    if not a and not b:
        return 0
    if not a or not b or a == b:
        return 1
    product = onb.mul(a, b)
    total_sq = onb.sqr(onb.add(a, b))
    constant = onb.add(onb.sqr(product), onb.one())
    rhs = onb.mul(onb.mul(total_sq, constant), onb.sqr(onb.inv(product)))
    return 0 if onb.trace(rhs) else 2


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    analysis = json.loads((HERE / "analysis.json").read_text())
    samples_path = HERE / "root_samples.json"
    samples = json.loads(samples_path.read_text())
    assert {protocol["proposal_id"], frozen["proposal_id"], build["proposal_id"],
            drive["proposal_id"], analysis["proposal_id"]} == {"Q1479"}
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest
    for key, path in (("field_source_sha256",
                       PARENT.parent.parent / "ecc2k130/codegen/field.py"),
                      ("s3_oracle_source_sha256", PARENT / "s3_root_oracle.py"),
                      ("s3_polynomial_source_sha256", PARENT / "chain_s3.py"),
                      ("counted_onb_source_sha256",
                       PARENT / "q20261011_operation_account/counted_onb.py")):
        assert sha(path) == frozen[key]
    assert sha(Q1478 / "build_receipt.json") == frozen["q1478_build_sha256"]
    assert sha(Q1478 / "run.py") == frozen["q1478_run_source_sha256"]
    assert build["freeze_sha256"] == drive["freeze_sha256"] == analysis[
        "freeze_sha256"] == sha(HERE / "freeze.json")
    assert build["source_sha256"] == sha(HERE / "build.py")
    assert analysis["analysis_source_sha256"] == sha(HERE / "analyze.py")
    assert analysis["drive_sha256"] == sha(HERE / "drive_receipt.json")
    assert analysis["root_samples_sha256"] == sha(samples_path)
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    assert sha(HERE / "build.stdout.txt") == build["build_stdout_sha256"]
    assert sha(HERE / "build.stderr.txt") == build["build_stderr_sha256"]
    patcher = load("q1479_build_replay", HERE / "build.py")
    with tempfile.TemporaryDirectory(prefix="q1479_replay_") as temp:
        source = Path(temp)
        shutil.copy2(Path(frozen["parent_source_dir"]) / "wdsat.c",
                     source / "wdsat.c")
        assert patcher.patch(source) == build["patched_wdsat_c_sha256"]
    assert [item["input"] for item in drive["rows"]] == ["selected", "holdout"]
    assert drive["new_ordinary_attempts"] == 2
    onb = Onb(83)
    for item in drive["rows"]:
        name = item["input"]
        folder = HERE / "runs" / f"{name}_{protocol['branch_order']}"
        row_path = folder / "receipt.json"
        assert sha(row_path) == item["receipt_sha256"]
        row = json.loads(row_path.read_text())
        impl_path = folder / "implementation_receipt.json"
        assert sha(impl_path) == row["implementation_receipt_sha256"]
        impl = json.loads(impl_path.read_text())
        assert row["status"] == impl["status"] == "CHECKPOINT_TERMINATED"
        assert row["branch_lower_bound"] == protocol["branch_checkpoint"]
        assert row["binary_sha256"] == build["binary_sha256"]
        assert row["workload_id"] == frozen["inputs"][name]["workload_id"]
        assert sha(folder / "solver.stdout.txt") == row["stdout_sha256"]
        log_path = folder / "solver.stderr.txt"
        assert sha(log_path) == row["stderr_sha256"]
        log = log_path.read_text()
        bit_rows = [bits for _, bits in re.findall(
            r"^Q1479_PAIR1 (\d+) ([01]{166})$", log, re.M)]
        assert bit_rows == [item["leaf_bits"] for item in samples[name]]
        assert len(set(bit_rows)) == len(bit_rows)
        assert len(bit_rows) == analysis["points"][name]["sample_count"]
        cap_line = f"Q1479_SUMMARY {protocol['branch_checkpoint']} "
        assert sum(line.startswith(cap_line) for line in log.splitlines()) == 1
        prior = json.loads((Q1478 / "runs" /
                            f"{name}_{protocol['branch_order']}" /
                            "receipt.json").read_text())
        assert row["ready_checkpoints"] == prior["ready_checkpoints"]
        assert row["work_checkpoints"] == prior["work_checkpoints"]
        assert sha(Q1478 / "runs" /
                   f"{name}_{protocol['branch_order']}" /
                   "receipt.json") == analysis["points"][name][
                       "q1478_receipt_sha256"]
        total_entries = 0
        distribution = {"0": 0, "1": 0, "2": 0}
        for sample in samples[name]:
            bits = sample["leaf_bits"]
            a = onb.fromCoords(int(bits[:83][::-1], 2))
            b = onb.fromCoords(int(bits[83:][::-1], 2))
            assert sample["leaf0_weight"] == bits[:83].count("1") <= 5
            assert sample["leaf1_weight"] == bits[83:].count("1") <= 5
            assert sample["root_count"] == exact_root_count(onb, a, b)
            assert len(set(sample["root_coords"])) == sample["root_count"]
            for value in sample["root_coords"]:
                assert evaluate_s3(onb, a, b, onb.fromCoords(value)) == 0
            assert sum(sample["field_api_calls"].values()) == sample[
                "field_api_entries"]
            distribution[str(sample["root_count"])] += 1
            total_entries += sample["field_api_entries"]
        assert distribution == analysis["points"][name]["root_count_distribution"]
        assert total_entries == analysis["points"][name][
            "total_field_api_entries_stored_sample"]
    print("PASS Q1479", {name: analysis["points"][name][
        "root_count_distribution"] for name in ("selected", "holdout")})


if __name__ == "__main__":
    main()
