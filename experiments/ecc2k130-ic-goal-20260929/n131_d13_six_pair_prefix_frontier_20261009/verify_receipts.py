#!/usr/bin/env python3
"""Check archived preflight, corrected rate, and final bound receipts."""

import hashlib
import json
from fractions import Fraction
from pathlib import Path


HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text())


def main():
    p1, p2, p3 = (load(name) for name in
                  ("protocol_v1.json", "protocol_v2.json", "protocol.json"))
    failure = load("preflight_failure_v1.json")
    correction = load("correction_v2.json")
    old, new = load("result_v2.json"), load("result.json")
    old_audit, new_audit = load("audit_v2.json"), load("audit.json")
    assert p1["source_sha256"]["bound_source"] == digest(HERE / "bound_v1.py")
    assert p2["source_sha256"]["bound_source"] == digest(HERE / "bound_v2.py")
    assert p1["source_sha256"]["audit_source"] == digest(HERE / "audit_v2.py")
    assert p2["source_sha256"]["audit_source"] == digest(HERE / "audit_v2.py")
    assert p3["source_sha256"]["bound_source"] == digest(HERE / "bound.py")
    assert p3["source_sha256"]["audit_source"] == digest(HERE / "audit.py")
    assert failure["protocol_sha256"] == digest(HERE / "protocol_v1.json")
    assert failure["bound_source_sha256"] == digest(HERE / "bound_v1.py")
    for name, path in (("protocol.json", "protocol_v2.json"),
                       ("result.json", "result_v2.json"),
                       ("audit.json", "audit_v2.json")):
        assert correction["old_sha256"][name] == digest(HERE / path)
    assert old_audit["result_sha256"] == digest(HERE / "result_v2.json")
    assert new_audit["result_sha256"] == digest(HERE / "result.json")
    assert old["rows"][3]["free_pair_blocks"] == 4
    assert old["rows"][3]["whole_prefix_probes_per_second_necessary_within_600s"] == "415935"
    row = new["rows"][3]
    assert row["free_pair_blocks"] == 4
    assert row["prefixes_necessary_for_50_percent_union_bound"] == "249560561"
    rate = row["necessary_average_full_probes_per_second_exact"]
    assert Fraction(int(rate["numerator"]), rate["denominator"]) == Fraction(249560561, 600)
    assert new_audit["status"] == "PASS_EXACT_ARITHMETIC_AND_SOURCE_HASHES"
    print("PASS_ALL_RETAINED_RECEIPTS")


if __name__ == "__main__":
    main()
