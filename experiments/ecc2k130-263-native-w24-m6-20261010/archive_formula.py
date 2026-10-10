#!/usr/bin/env python3
"""Archive one Q1420 XCNF losslessly with deterministic gzip metadata."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import field as ref


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formula", type=Path, required=True)
    args = parser.parse_args()
    formula = args.formula
    receipt_path = formula.with_suffix(".json")
    archive_path = formula.with_suffix(formula.suffix + ".gz")
    archive_receipt = formula.with_suffix(".archive.json")
    if archive_path.exists() or archive_receipt.exists():
        parser.error("refusing to overwrite XCNF archive")
    receipt = ref.read(receipt_path)
    if (receipt["schema"] != "ecc2k130-263-native-w24-m6-xcnf-v1"
            or receipt["mode"] != "m6"
            or ref.sha(formula) != receipt["formula_sha256"]):
        raise ValueError("formula does not match frozen build receipt")
    with formula.open("rb") as source, archive_path.open("xb") as dest:
        with gzip.GzipFile(filename="", mode="wb", fileobj=dest, mtime=0,
                           compresslevel=9) as stream:
            for block in iter(lambda: source.read(1 << 20), b""):
                stream.write(block)
    result = {
        "schema": "ecc2k130-263-native-w24-m6-xcnf-archive-v1",
        "status": "PASS_LOSSLESS_ARCHIVE",
        "policy": receipt["policy"],
        "raw_formula_sha256": receipt["formula_sha256"],
        "raw_formula_bytes": formula.stat().st_size,
        "gzip_sha256": ref.sha(archive_path),
        "gzip_bytes": archive_path.stat().st_size,
        "build_receipt_sha256": ref.sha(receipt_path),
        "source_sha256": ref.sha(Path(__file__)),
    }
    archive_receipt.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({key: result[key] for key in
                      ("policy", "status", "raw_formula_bytes", "gzip_bytes")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
