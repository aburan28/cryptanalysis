#!/usr/bin/env python3
"""Bind matched native operation counts to two atlases and one scalar panel."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
LINE = re.compile(
    r"dual_rho0_folded_cases=(\d+) retained_bytes=(\d+) "
    r"additions=(\d+) gauge_products=(\d+) "
    r"fused_additions=(\d+) fused_gauge_products=(\d+)"
)


def digest(raw):
    return sha256(raw).hexdigest()


def archive(name):
    raw = (HERE / name).read_bytes()
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    output = HERE / f"{name}.gz"
    output.write_bytes(compressed)
    assert gzip.decompress(output.read_bytes()) == raw
    return {"raw_sha256": digest(raw), "raw_bytes": len(raw),
            "gzip_sha256": digest(compressed), "gzip_bytes": len(compressed)}


def parse(name):
    raw = (HERE / name).read_bytes()
    text = raw.decode()
    hits = LINE.findall(text)
    assert len(hits) == 1
    assert "test result: ok. 1 passed; 0 failed;" in text
    assert "140 filtered out" in text
    cases, retained, additions, rotations, fused_additions, fused_rotations = \
        map(int, hits[0])
    assert (cases, retained, additions, fused_additions) == \
        (4096, 54_339_936, 49_152, 49_152)
    return {"cases": cases, "retained_bytes": retained,
            "mixed_additions": additions, "gauge_rotations": rotations,
            "fused_mixed_additions": fused_additions,
            "fused_gauge_rotations": fused_rotations,
            "raw_log": archive(name)}


def main():
    assert len(sys.argv) == 3, \
        "usage: collect_priority_native.py PRIORITY_CRATE CONTROL_CRATE"
    candidate = Path(sys.argv[1]).resolve()
    control = Path(sys.argv[2]).resolve()
    candidate_raw = (candidate / "materialization.json").read_bytes()
    control_raw = (control / "materialization.json").read_bytes()
    candidate_receipt = json.loads(candidate_raw)
    control_receipt = json.loads(control_raw)
    assert candidate_receipt["generated_sha256"] == control_receipt["generated_sha256"]
    for crate, receipt in ((candidate, candidate_receipt), (control, control_receipt)):
        for name, expected in receipt["generated_sha256"].items():
            assert digest((crate / name).read_bytes()) == expected
        for name, expected in receipt["assets_sha256"].items():
            assert digest((crate / name).read_bytes()) == expected
    assert candidate_receipt["assets_sha256"]["dual-rho0-fresh-inputs.json"] == \
        control_receipt["assets_sha256"]["dual-rho0-fresh-inputs.json"]
    assert candidate_receipt["assets_sha256"]["atlas-r1024-full-dual-rho0.bin"] != \
        control_receipt["assets_sha256"]["atlas-r1024-full-dual-rho0.bin"]
    priority = parse("priority-native-targeted.log")
    original = parse("priority-native-control.log")
    assert priority["fused_gauge_rotations"] == original["fused_gauge_rotations"]
    assert priority["gauge_rotations"] < original["gauge_rotations"]
    suite_raw = (HERE / "priority-native-full.log").read_bytes()
    assert "test result: ok. 141 passed; 0 failed;" in suite_raw.decode()
    assert "test result: FAILED" not in suite_raw.decode()
    suite = {"passed": 141, "failed": 0,
             "raw_log": archive("priority-native-full.log")}
    (HERE / "priority-native-materialization.json").write_bytes(candidate_raw)
    (HERE / "priority-control-materialization.json").write_bytes(control_raw)
    receipt = {"schema": 1, "status": "passed",
               "timing_class": "correctness_and_operation_counts_only",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "candidate_materialization_sha256": digest(candidate_raw),
               "control_materialization_sha256": digest(control_raw),
               "generated_sha256": candidate_receipt["generated_sha256"],
               "input_sha256": candidate_receipt["assets_sha256"][
                   "dual-rho0-fresh-inputs.json"],
               "priority": priority, "original": original,
               "gauge_rotations_saved": original["gauge_rotations"] - priority["gauge_rotations"],
               "full_suite": suite}
    (HERE / "priority-native-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": 4096,
                      "priority_gauge_rotations": priority["gauge_rotations"],
                      "original_gauge_rotations": original["gauge_rotations"],
                      "saved": receipt["gauge_rotations_saved"],
                      "suite_passed": suite["passed"]}, sort_keys=True))


if __name__ == "__main__":
    main()
