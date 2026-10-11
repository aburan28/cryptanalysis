#!/usr/bin/env python3
"""Bind the complete native test log to the generated source and assets."""

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
    parser.add_argument("--log", type=Path, default=HERE / "native-full-suite.log")
    args = parser.parse_args()
    output = args.materialized.resolve()
    receipt_raw = (output / "carry-materialization.json").read_bytes()
    materialized = json.loads(receipt_raw)
    assert materialized["status"] == "materialized"
    for name, expected in materialized["generated_sha256"].items():
        assert digest((output / name).read_bytes()) == expected, name
    for name, expected in materialized["assets_sha256"].items():
        assert digest((output / name).read_bytes()) == expected, name
    assert materialized["assets_sha256"]["offers-r1024-dual-priority.bin"] == \
        json.loads((HERE / "offer-index-check.json").read_bytes())["offer_index_sha256"]
    log = args.log.read_bytes()
    match = re.search(rb"test result: ok\. (\d+) passed; (\d+) failed;", log)
    assert match and (int(match.group(1)), int(match.group(2))) == (143, 0)
    required = (b"carry_width2_cases=4096", b"active_rho=2846",
                b"rho_terms=4679", b"gauge_products=20941",
                b"examined_offers=113623")
    assert all(term in log for term in required)
    compressed = gzip.compress(log, compresslevel=9, mtime=0)
    (HERE / "native-full-suite.log.gz").write_bytes(compressed)
    result = {"schema": 1, "status": "passed", "timing_class": "correctness_only",
              "passed": 143, "failed": 0,
              "materialization_sha256": digest(receipt_raw),
              "generated_sha256": materialized["generated_sha256"],
              "assets_sha256": materialized["assets_sha256"],
              "raw_log_sha256": digest(log), "raw_log_bytes": len(log),
              "gzip_log_sha256": digest(compressed),
              "collector_sha256": digest(Path(__file__).read_bytes())}
    (HERE / "native-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
