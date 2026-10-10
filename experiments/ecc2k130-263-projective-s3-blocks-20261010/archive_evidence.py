#!/usr/bin/env python3
"""Losslessly archive all block-isolation solver stdout streams."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import common


ref = common.ref


def compress(source, archive):
    with source.open("rb") as inp, archive.open("xb") as out:
        with gzip.GzipFile(filename="", mode="wb", fileobj=out, mtime=0,
                           compresslevel=9) as stream:
            for block in iter(lambda: inp.read(1 << 20), b""):
                stream.write(block)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=("source", "descendant_native"),
                        required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    config, _, _ = common.load_config()
    rows = {}
    for mode in config["modes"]:
        prefix = args.run_dir / (args.policy + "_" + mode)
        receipt_path = prefix.with_suffix(".solver.json")
        receipt = ref.read(receipt_path)
        stdout = prefix.with_suffix(".stdout.txt")
        compressed = prefix.with_suffix(".stdout.txt.gz")
        archive_receipt = prefix.with_suffix(".stdout.archive.json")
        if compressed.exists() or archive_receipt.exists():
            parser.error("refusing to overwrite archived solver evidence")
        if (receipt["policy"] != args.policy or receipt["mode"] != mode
                or receipt["stdout_sha256"] != ref.sha(stdout)
                or receipt["runner_sha256"] != ref.sha(
                    common.HERE / "run_cell.py")):
            raise ValueError("raw solver evidence differs")
        compress(stdout, compressed)
        result = {
            "schema": "ecc2k130-263-projective-s3-search-block-archive-v1",
            "status": "PASS_LOSSLESS_ARCHIVE",
            "kind": "solver_stdout",
            "raw_sha256": ref.sha(stdout),
            "raw_bytes": stdout.stat().st_size,
            "gzip_sha256": ref.sha(compressed),
            "gzip_bytes": compressed.stat().st_size,
            "solver_receipt_sha256": ref.sha(receipt_path),
            "source_sha256": ref.sha(Path(__file__)),
        }
        common.write_json(archive_receipt, result)
        rows[mode] = result["gzip_bytes"]
    print(json.dumps({"policy": args.policy, "gzip_bytes": rows},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
