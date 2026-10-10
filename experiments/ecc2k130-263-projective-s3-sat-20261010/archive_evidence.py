#!/usr/bin/env python3
"""Losslessly archive control-base XCNFs and complete solver stdout."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import build_control as circuit


HERE = Path(__file__).resolve().parent
ref = circuit.ref


def compress(source, archive):
    if archive.exists():
        raise FileExistsError(archive)
    with source.open("rb") as inp, archive.open("xb") as out:
        with gzip.GzipFile(filename="", mode="wb", fileobj=out, mtime=0,
                           compresslevel=9) as stream:
            for block in iter(lambda: inp.read(1 << 20), b""):
                stream.write(block)


def archive_one(source, expected_sha, receipt_sha, kind):
    if ref.sha(source) != expected_sha:
        raise ValueError("raw evidence changed: " + str(source))
    compressed = source.with_suffix(source.suffix + ".gz")
    archive_receipt = source.with_suffix(".archive.json")
    if archive_receipt.exists():
        raise FileExistsError(archive_receipt)
    compress(source, compressed)
    result = {
        "schema": "ecc2k130-263-projective-s3-sat-archive-v1",
        "status": "PASS_LOSSLESS_ARCHIVE",
        "kind": kind,
        "raw_sha256": expected_sha,
        "raw_bytes": source.stat().st_size,
        "gzip_sha256": ref.sha(compressed),
        "gzip_bytes": compressed.stat().st_size,
        "input_receipt_sha256": receipt_sha,
        "source_sha256": ref.sha(Path(__file__)),
    }
    archive_receipt.write_text(json.dumps(result, sort_keys=True,
                                          indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=circuit.parent.POLICIES, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    stem = args.out_dir / (args.policy + "_control_base")
    build_receipt = stem.with_suffix(".json")
    build = ref.read(build_receipt)
    if build["status"] != "CONTROL_FORMULA_BUILT":
        raise ValueError("base formula build has not passed")
    base = archive_one(stem.with_suffix(".xcnf"), build["formula_sha256"],
                       ref.sha(build_receipt), "control_base_xcnf")
    logs = {}
    for mode in ("positive", "negative", "free"):
        prefix = args.out_dir / (args.policy + "_" + mode)
        receipt_path = prefix.with_suffix(".solver.json")
        receipt = ref.read(receipt_path)
        logs[mode] = archive_one(prefix.with_suffix(".stdout.txt"),
                                 receipt["stdout_sha256"],
                                 ref.sha(receipt_path), "solver_stdout")
    print(json.dumps({"policy": args.policy,
                      "base_gzip_bytes": base["gzip_bytes"],
                      "stdout_gzip_bytes": {m: r["gzip_bytes"]
                                            for m, r in logs.items()}},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
