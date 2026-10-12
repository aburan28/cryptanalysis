#!/usr/bin/env python3
"""Bind the complete native test log to swapped source and assets."""

import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--materialized", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    output = args.materialized.resolve()
    materialization_raw = (output / "swap-materialization.json").read_bytes()
    receipt = json.loads(materialization_raw)
    assert receipt["status"] == "materialized"
    for name, expected in receipt["generated_sha256"].items():
        assert digest((output / name).read_bytes()) == expected, name
    for name, expected in receipt["assets_sha256"].items():
        assert digest((output / name).read_bytes()) == expected, name
    assert receipt["assets_sha256"]["atlas-r1024-full-dual-rho0.bin"] == \
        json.loads((HERE / "native-atlas-check.json").read_bytes())["atlas_sha256"]
    log = args.log.read_bytes()
    match = re.search(rb"test result: ok\. (\d+) passed; (\d+) failed;", log)
    assert match and (int(match.group(1)), int(match.group(2))) == (143, 0)
    required = (b"swapped_rho_cases=4096", b"active_rho=2346",
                b"rho_terms=3240", b"additions=49152",
                b"gauge_products=19943", b"retained_bytes=54339936")
    assert all(item in log for item in required)
    compressed = gzip.compress(log, compresslevel=9, mtime=0)
    (HERE / "native-full-suite.log.gz").write_bytes(compressed)
    result = {"schema": 1, "status": "passed", "timing_class": "correctness_only",
              "passed": 143, "failed": 0,
              "materialization_sha256": digest(materialization_raw),
              "generated_sha256": receipt["generated_sha256"],
              "assets_sha256": receipt["assets_sha256"],
              "raw_log_sha256": digest(log), "raw_log_bytes": len(log),
              "gzip_log_sha256": digest(compressed),
              "collector_sha256": digest(Path(__file__).read_bytes())}
    (HERE / "native-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
