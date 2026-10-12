#!/usr/bin/env python3
"""Check hash bindings and correctness receipts without rerunning long jobs."""

import gzip
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-power2-tau2-20261011"
FIXTURE_VERIFIER = HERE.parent / "prime-j0-power2-residual-20261010/verify_fixture.py"
SPEC = importlib.util.spec_from_file_location("exact_mode_fixture", FIXTURE_VERIFIER)
fixture_verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture_verifier)


def digest(raw):
    return sha256(raw).hexdigest()


def file_hash(name):
    return digest((HERE / name).read_bytes())


def receipt(name):
    return json.loads((HERE / name).read_bytes())


def verify_log(name, record):
    compressed = (HERE / name).read_bytes()
    raw = gzip.decompress(compressed)
    assert digest(compressed) == record["gzip_sha256"]
    assert digest(raw) == record["raw_sha256"]
    assert len(compressed) == record["gzip_bytes"]
    assert len(raw) == record["raw_bytes"]
    return raw


def main():
    screen = receipt("screen.json")
    plan = receipt("independent-check.json")
    assert screen["generator_sha256"] == file_hash("screen.py")
    assert screen["cover_plan_sha256"] == file_hash("cover-plan.bin")
    assert plan["status"] == "passed"
    assert plan["verifier_sha256"] == file_hash("verify_screen.py")
    assert plan["cover_plan_sha256"] == screen["cover_plan_sha256"]
    assert plan["full_seeds"] == screen["budgeted_full_seeds"] == 77_513
    assert plan["exponent_two_residues"] == 118_842

    atlas = receipt("atlas-receipt.json")
    atlas_check = receipt("atlas-independent-check.json")
    assert atlas["generator_sha256"] == file_hash("build_atlas.py")
    assert atlas_check["verifier_sha256"] == file_hash("verify_atlas.py")
    assert atlas_check["status"] == "passed"
    for kind, filename in (
        ("full", "atlas-r1024-full-cache-budget.bin"),
        ("terminal", "atlas-r1024-terminal-cache-budget.bin"),
    ):
        assert atlas[kind]["atlas_sha256"] == file_hash(filename)
        assert atlas_check[kind]["atlas_sha256"] == file_hash(filename)
    assert atlas["affine_slots"] == 939_444
    assert atlas_check["full"]["exponent_residues"]["2"] == 118_842

    input_check = receipt("input-check.json")
    group = receipt("group-check.json")
    assert input_check["status"] == group["status"] == "passed"
    assert input_check["verifier_sha256"] == file_hash("verify_inputs.py")
    assert input_check["input_sha256"] == file_hash("fresh-inputs.json")
    assert group["source_sha256"] == file_hash("verify_group.py")
    assert group["input_sha256"] == input_check["input_sha256"]
    assert group["atlas_sha256"]["budgeted"]["full"] == \
        atlas["full"]["atlas_sha256"]
    assert group["atlas_sha256"]["budgeted"]["terminal"] == \
        atlas["terminal"]["atlas_sha256"]
    assert group["atlas_sha256"]["minimum"]["full"] == digest(
        (PARENT / "atlas-r1024-full-tau2.bin").read_bytes())
    assert group["results"]["budgeted"]["output_sha256"] == \
        group["results"]["minimum"]["output_sha256"]

    materialization = receipt("native-materialization.json")
    targeted = receipt("native-targeted.json")
    suite = receipt("native-full-suite.json")
    edge = receipt("native-edge-check.json")
    assert materialization["materializer_sha256"] == file_hash("materialize_native.py")
    assert materialization["group_receipt_sha256"] == file_hash("group-check.json")
    assert targeted["status"] == suite["status"] == edge["status"] == "passed"
    assert targeted["materialization_sha256"] == suite["materialization_sha256"] \
        == edge["materialization_sha256"] == file_hash("native-materialization.json")
    assert targeted["assets_sha256"] == materialization["assets_sha256"]
    assert targeted["generated_sha256"] == materialization["generated_sha256"]
    assert targeted["group_receipt_sha256"] == file_hash("group-check.json")
    assert targeted["retained_bytes"] == screen["projected_retained_bytes"] \
        == 64_991_220
    assert targeted["mixed_additions"] == group["results"]["budgeted"][
        "mixed_additions"]
    assert targeted["gauge_rotations"] == group["results"]["budgeted"][
        "gauge_rotations"]
    assert suite["passed"] == 137 and suite["failed"] == 0
    targeted_raw = verify_log("native-targeted-tests.log.gz", targeted["raw_log"])
    suite_raw = verify_log("native-full-tests.log.gz", suite["raw_log"])
    assert b"test result: ok. 1 passed; 0 failed;" in targeted_raw
    assert b"test result: ok. 137 passed; 0 failed;" in suite_raw

    assert edge["verifier_sha256"] == file_hash("verify_edge.py")
    assert edge["generic_verifier_sha256"] == digest(FIXTURE_VERIFIER.read_bytes())
    compressed = (HERE / "native-edge.stdout.gz").read_bytes()
    assert digest(compressed) == edge["stdout_gzip_sha256"]
    stdout = gzip.decompress(compressed)
    fixture = HERE.parent / "prime-j0-tau-bucket-two-x-20261010/edge-fixture.json"
    checked = fixture_verifier.check_fixture(edge["mode"], "edge", fixture,
                                             stdout, 10)
    assert edge["stdout_sha256"] == checked["stdout_sha256"]
    assert edge["point_stream_sha256"] == checked["point_stream_sha256"]
    print(json.dumps({"status": "passed", "full_residues": 1_048_576,
                      "terminal_pairs": 80_521, "panel_cases": 4_096,
                      "native_tests": 137, "edge_cases": 10}, sort_keys=True))


if __name__ == "__main__":
    main()
