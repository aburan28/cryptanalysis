#!/usr/bin/env python3
"""Verify the promoted public-gate archive and the preserved v1 failure."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text())


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def unpacked(path):
    digest = hashlib.sha256()
    size = 0
    with gzip.open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def main():
    result = load("result.json")
    terminal = load("terminal_audit.json")
    protocol = load("protocol.json")
    failure = load("failure_v1.json")
    failure_archive = load("failure_v1_archive.json")
    support = load("support_count.json")
    support_audit = load("support_audit.json")
    assert result["status"] == terminal["query_status"] == "CENSORED_TIME"
    assert terminal["status"] == "PASS_UNRESTRICTED_FIVEPAIR_TERMINAL_AUDIT"
    assert terminal["sha256"]["auditor"] == sha(HERE / "audit.py")
    assert terminal["sha256"]["sage_prefix_audit"] == sha(HERE / "prefix_sage_audit.json")
    assert terminal["sha256"]["result"] == sha(HERE / "result.json")
    assert result["sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert protocol["sources_sha256"]["runner"] == sha(HERE / "run.py")
    assert protocol["sources_sha256"]["circuit"] == sha(HERE / "circuit.py")
    assert protocol["sources_sha256"]["group_lift"] == sha(HERE / "lift.py")
    assert protocol["sources_sha256"]["input"] == sha(HERE / "input.json")
    for key, name in (("control", "control.json"),
                      ("stdout", "solver.stdout.txt"),
                      ("stderr", "solver.stderr.txt"),
                      ("formula_gzip", "system.xcnf.gz")):
        assert result["sha256"][key] == terminal["sha256"][key]
        assert result["sha256"][key] == sha(HERE / name)
    digest, size = unpacked(HERE / "system.xcnf.gz")
    assert digest == result["formula"]["sha256"] == terminal["formula"]["sha256"]
    assert size == result["formula"]["bytes"] == terminal["formula"]["bytes"]
    assert support_audit["tuple_count"] == support["distinct_column_signed_unordered_fivepair_tuples"]
    assert support_audit["source_sha256"]["result"] == sha(HERE / "support_count.json")
    assert failure["status"] == "PRODUCER_PREFLIGHT_VARIABLE_COUNT_MISMATCH"
    assert not failure["solver_launched"]
    assert failure_archive["gzip_sha256"] == sha(HERE / "failure_v1.xcnf.gz")
    previous_digest, previous_size = unpacked(HERE / "failure_v1.xcnf.gz")
    assert previous_digest == failure_archive["decompressed_sha256"] == failure["formula"]["sha256"]
    assert previous_size == failure_archive["decompressed_bytes"] == failure["formula"]["bytes"]
    receipt = {"status": "PASS_PROMOTED_W15_FIVEPAIR_ARCHIVE",
               "public_query_status": result["status"],
               "public_formula_sha256": digest,
               "public_formula_bytes": size,
               "source_tuple_count": support_audit["tuple_count"],
               "preflight_failure_formula_sha256": previous_digest,
               "source_sha256": sha(Path(__file__))}
    with (HERE / "archive_receipt.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
