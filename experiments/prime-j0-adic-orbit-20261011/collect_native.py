#!/usr/bin/env python3
"""Bind native direct-index results to generated source and raw logs."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
TARGET_LINE = re.compile(
    r"adic_orbit_cases=(\d+) retained_bytes=(\d+) additions=(\d+) "
    r"gauge_products=(\d+) direct_additions=(\d+) direct_gauge_products=(\d+)"
)


def digest(raw):
    return sha256(raw).hexdigest()


def archive_log(name):
    raw = (HERE / name).read_bytes()
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    archive = HERE / f"{name}.gz"
    archive.write_bytes(compressed)
    assert gzip.decompress(archive.read_bytes()) == raw
    return {"raw_sha256": digest(raw), "gzip_sha256": digest(compressed),
            "raw_bytes": len(raw), "gzip_bytes": len(compressed)}


def main():
    assert len(sys.argv) == 2, "usage: collect_native.py MATERIALIZED_CRATE"
    native = Path(sys.argv[1]).resolve()
    materialization_raw = (native / "materialization.json").read_bytes()
    materialization = json.loads(materialization_raw)
    assert materialization["timing_class"] == "correctness_only"
    for name, expected in materialization["generated_sha256"].items():
        assert digest((native / name).read_bytes()) == expected
    for name, expected in materialization["assets_sha256"].items():
        assert digest((native / name).read_bytes()) == expected
    for name, expected in materialization["included_assets_sha256"].items():
        assert digest((native / name).read_bytes()) == expected
    assert len(materialization["included_assets_sha256"]) >= 40
    (HERE / "native-materialization.json").write_bytes(materialization_raw)

    targeted_raw = (HERE / "native-targeted-tests.log").read_bytes()
    targeted_text = targeted_raw.decode()
    hits = TARGET_LINE.findall(targeted_text)
    assert len(hits) == 1
    cases, retained, additions, rotations, direct_additions, direct_rotations = \
        map(int, hits[0])
    assert (cases, retained, additions, rotations, direct_additions) == \
        (4_096, 65_596_552, 49_152, 16_539, 49_152)
    assert "test result: ok. 1 passed; 0 failed;" in targeted_text
    assert "138 filtered out" in targeted_text
    group_raw = (HERE / "group-check.json").read_bytes()
    group = json.loads(group_raw)
    assert (additions, rotations) == (
        group["results"]["adic"]["mixed_additions"],
        group["results"]["adic"]["gauge_rotations"])
    targeted = {"schema": 1, "status": "passed", "timing_class": "correctness_only",
                "cases": cases, "retained_bytes": retained,
                "mixed_additions": additions, "gauge_rotations": rotations,
                "direct_mixed_additions": direct_additions,
                "direct_gauge_rotations": direct_rotations,
                "group_receipt_sha256": digest(group_raw),
                "materialization_sha256": digest(materialization_raw),
                "generated_sha256": materialization["generated_sha256"],
               "assets_sha256": materialization["assets_sha256"],
                "included_assets_sha256": materialization["included_assets_sha256"],
                "raw_log": archive_log("native-targeted-tests.log")}
    (HERE / "native-targeted.json").write_text(
        json.dumps(targeted, indent=2, sort_keys=True) + "\n")

    suite_raw = (HERE / "native-full-tests.log").read_bytes()
    suite_text = suite_raw.decode()
    assert "test result: ok. 139 passed; 0 failed;" in suite_text
    assert "test result: FAILED" not in suite_text
    suite = {"schema": 1, "status": "passed", "timing_class": "correctness_only",
             "passed": 139, "failed": 0,
             "materialization_sha256": digest(materialization_raw),
             "raw_log": archive_log("native-full-tests.log")}
    (HERE / "native-full-suite.json").write_text(
        json.dumps(suite, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"targeted": targeted, "full_suite": suite}, sort_keys=True))


if __name__ == "__main__":
    main()
