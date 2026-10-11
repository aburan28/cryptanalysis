#!/usr/bin/env python3
"""Check construction and native receipt bindings without long reruns."""

import gzip
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIXTURE_VERIFIER = ROOT / "prime-j0-power2-residual-20261010/verify_fixture.py"
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
    index = receipt("index-check.json")
    assert index["status"] == "passed"
    assert (index["residues"], index["classes"]) == (1_048_576, 174_764)
    assert index["index_source_sha256"] == file_hash("index.py")
    assert index["verifier_sha256"] == file_hash("verify_index.py")

    atlas = receipt("atlas-receipt.json")
    replay = receipt("atlas-check.json")
    assert atlas["status"] == "constructed" and replay["status"] == "passed"
    assert atlas["source_sha256"] == file_hash("build_atlas.py")
    assert atlas["index_source_sha256"] == file_hash("index.py")
    assert replay["verifier_sha256"] == file_hash("verify_atlas.py")
    assert atlas["full_atlas_sha256"] == replay["full_atlas_sha256"] \
        == file_hash("atlas-r1024-full-adic-orbit.bin")
    assert atlas["terminal_atlas_sha256"] == \
        file_hash("atlas-r1024-terminal-adic-orbit.bin")
    assert atlas["atlas_bytes_saved"] == 196_616
    assert replay["residues"] == 1_048_576
    assert set(replay["differences_from_lex_quotient"].values()) == {0}

    inputs = receipt("input-check.json")
    group = receipt("group-check.json")
    assert inputs["status"] == group["status"] == "passed"
    assert inputs["verifier_sha256"] == file_hash("verify_inputs.py")
    assert inputs["input_sha256"] == group["panel_sha256"] \
        == file_hash("fresh-inputs.json")
    assert group["source_sha256"] == file_hash("verify_group.py")
    assert group["index_source_sha256"] == file_hash("index.py")
    assert group["atlas_sha256"]["adic"] == atlas["full_atlas_sha256"]
    assert group["terminal_sha256"] == atlas["terminal_atlas_sha256"]
    assert group["results"]["adic"] == group["results"]["quotient"]
    assert group["results"]["adic"]["cases"] == 4_096

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
    assert targeted["included_assets_sha256"] == \
        materialization["included_assets_sha256"]
    assert targeted["generated_sha256"] == materialization["generated_sha256"]
    assert targeted["retained_bytes"] == 65_596_552
    assert (targeted["mixed_additions"], targeted["gauge_rotations"]) == (
        group["results"]["adic"]["mixed_additions"],
        group["results"]["adic"]["gauge_rotations"])
    assert suite["passed"] == 139 and suite["failed"] == 0
    targeted_raw = verify_log("native-targeted-tests.log.gz", targeted["raw_log"])
    suite_raw = verify_log("native-full-tests.log.gz", suite["raw_log"])
    assert b"test result: ok. 1 passed; 0 failed;" in targeted_raw
    assert b"test result: ok. 139 passed; 0 failed;" in suite_raw

    assert edge["verifier_sha256"] == file_hash("verify_edge.py")
    assert edge["generic_verifier_sha256"] == digest(FIXTURE_VERIFIER.read_bytes())
    compressed = (HERE / "native-edge.stdout.gz").read_bytes()
    assert digest(compressed) == edge["stdout_gzip_sha256"]
    fixture = ROOT / "prime-j0-tau-bucket-two-x-20261010/edge-fixture.json"
    checked = fixture_verifier.check_fixture(edge["mode"], "edge", fixture,
                                             gzip.decompress(compressed), 10)
    assert edge["stdout_sha256"] == checked["stdout_sha256"]
    assert edge["point_stream_sha256"] == checked["point_stream_sha256"]
    print(json.dumps({"status": "passed", "residues": 1_048_576,
                      "panel_cases": 4_096, "native_tests": 139,
                      "edge_cases": 10}, sort_keys=True))


if __name__ == "__main__":
    main()
