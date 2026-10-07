#!/usr/bin/env python3
"""Independently check every clause and XOR row of the archived XCNF."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WITNESS = HERE / "runs" / "witness"
FORMULA = HERE / "runs" / "planted" / "system.xcnf.gz"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def truth(packed, literal):
    wire = abs(literal)
    value = bool(packed[wire >> 3] & (1 << (wire & 7)))
    return not value if literal < 0 else value


def main():
    report = json.loads((WITNESS / "receipt.json").read_text())
    strict = json.loads((HERE / "runs" / "planted" / "receipt.json").read_text())
    assert report["status"] == "constructed_unverified"
    assert strict["status"] == "timeout" and strict["model"] is None
    assert report["xcnf_sha256"] == strict["xcnf_sha256"]
    assert report["packed_assignment_sha256"] == digest(
        WITNESS / "assignment.bin.gz")
    for name, expected in report["source_sha256"].items():
        assert digest(HERE / name) == expected
    assert report["config_sha256"] == digest(HERE / "CONFIG.json")
    assert report["witness_protocol_sha256"] == digest(
        HERE / "WITNESS_PROTOCOL.md")
    assert report["sage_runtime_info_sha256"] == digest(
        WITNESS / "runtime-info.json")
    packed = gzip.decompress((WITNESS / "assignment.bin.gz").read_bytes())
    assert hashlib.sha256(packed).hexdigest() == report[
        "packed_assignment_raw_sha256"]
    assert len(packed) == report["packed_assignment_bytes"]
    assert (packed[0] & 1) == 0
    n = report["variables"]
    assert len(packed) == (n + 8)//8
    formula_hash = hashlib.sha256()
    clause_count = xor_count = line_count = violation_count = 0
    first_failures = []
    with gzip.open(FORMULA, "rb") as stream:
        for raw in stream:
            formula_hash.update(raw)
            line_count += 1
            if raw.startswith(b"p "):
                fields = raw.split()
                assert fields[:2] == [b"p", b"cnf"]
                assert int(fields[2]) == n
                assert int(fields[3]) == report["cnf_clauses"] + report["xor_rows"]
                continue
            if raw.startswith(b"x "):
                values = [int(word) for word in raw[2:].split()]
                assert values[-1] == 0
                literals = values[:-1]
                assert all(0 < abs(lit) <= n for lit in literals)
                satisfied = bool(sum(truth(packed, lit) for lit in literals) & 1)
                xor_count += 1
            else:
                values = [int(word) for word in raw.split()]
                assert values[-1] == 0
                literals = values[:-1]
                assert all(0 < abs(lit) <= n for lit in literals)
                satisfied = any(truth(packed, lit) for lit in literals)
                clause_count += 1
            if not satisfied:
                violation_count += 1
                if len(first_failures) < 10:
                    first_failures.append(line_count)
    assert formula_hash.hexdigest() == report["xcnf_sha256"]
    assert clause_count == report["cnf_clauses"]
    assert xor_count == report["xor_rows"]
    result = {
        "schema": "ecc2k130-w24-functional-s3-xcnf-witness-check-v1",
        "status": "PASS_XCNF_WITNESS" if violation_count == 0 else "FAIL_XCNF_WITNESS",
        "variables": n,
        "cnf_clauses_checked": clause_count,
        "xor_rows_checked": xor_count,
        "violations": violation_count,
        "first_failure_lines": first_failures,
        "xcnf_sha256": report["xcnf_sha256"],
        "packed_assignment_sha256": report["packed_assignment_sha256"],
        "witness_receipt_sha256": digest(WITNESS / "receipt.json"),
        "verifier_sha256": digest(Path(__file__)),
        "natural_target_attempted": False,
        "candidate_id": None,
    }
    output = WITNESS / "verification.json"
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "cnf_clauses_checked", "xor_rows_checked",
                       "violations")}, sort_keys=True))
    if violation_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
