#!/usr/bin/env python3
"""Bind or restore the deterministic compressed W28 membership evidence."""

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path


RAW_NAMES = ("membership.bin",)
SMALL_NAMES = ("native.json", "summary.json", "verification.json",
               "enumerate", "build.stdout", "build.stderr",
               "run.stdout", "run.stderr")


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decompressed(path):
    with gzip.open(path, "rb") as stream:
        return stream.read()


def pack(folder):
    manifest = folder / "archive.json"
    if manifest.exists():
        raise FileExistsError(manifest)
    summary = json.loads((folder / "summary.json").read_text())
    assert summary["status"] == "completed_unverified"
    verification = json.loads((folder / "verification.json").read_text())
    assert verification["verified"] is True
    compressed = {}
    for name in RAW_NAMES:
        raw = folder / name
        gz = folder / f"{name}.gz"
        assert raw.is_file()
        assert sha(raw) == summary["artifacts_sha256"][name]
        if not gz.exists():
            with raw.open("rb") as source, gz.open("wb") as target:
                with gzip.GzipFile(fileobj=target, mode="wb", filename="",
                                   mtime=0, compresslevel=9) as compressor:
                    shutil.copyfileobj(source, compressor, 1 << 20)
        assert sha_bytes(decompressed(gz)) == summary["artifacts_sha256"][name]
        compressed[gz.name] = {"sha256": sha(gz), "raw_sha256": sha(raw),
                               "raw_bytes": raw.stat().st_size}
    small = {name: sha(folder / name) for name in SMALL_NAMES}
    result = {"schema": "ecc2k130-263-w28-evidence-archive-v1",
              "status": "COMPRESSED_RAW_BOUND",
              "compression": "gzip level 9, no stored filename or timestamp",
              "source_sha256": sha(Path(__file__)),
              "compressed": compressed, "small_files_sha256": small}
    with manifest.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"archive": str(manifest), "compressed": list(compressed)}))


def unpack(folder, out):
    if out.exists():
        raise FileExistsError(out)
    manifest = json.loads((folder / "archive.json").read_text())
    assert manifest["status"] == "COMPRESSED_RAW_BOUND"
    assert sha(Path(__file__)) == manifest["source_sha256"]
    for name, expected in manifest["small_files_sha256"].items():
        assert sha(folder / name) == expected, name
    out.mkdir(parents=True)
    for name in SMALL_NAMES:
        shutil.copy2(folder / name, out / name)
    summary = json.loads((out / "summary.json").read_text())
    for gz_name, record in manifest["compressed"].items():
        gz = folder / gz_name
        assert sha(gz) == record["sha256"]
        raw_name = gz_name[:-3]
        with gzip.open(gz, "rb") as source, (out / raw_name).open("xb") as target:
            shutil.copyfileobj(source, target, 1 << 20)
        assert (out / raw_name).stat().st_size == record["raw_bytes"]
        assert sha(out / raw_name) == record["raw_sha256"]
        assert sha(out / raw_name) == summary["artifacts_sha256"][raw_name]
    print(json.dumps({"restored": str(out), "status": "PASS_ARCHIVE_RAW_HASHES"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    pack_parser = sub.add_parser("pack")
    pack_parser.add_argument("--run-dir", type=Path, required=True)
    unpack_parser = sub.add_parser("unpack")
    unpack_parser.add_argument("--run-dir", type=Path, required=True)
    unpack_parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "pack":
        pack(args.run_dir)
    else:
        unpack(args.run_dir, args.out_dir)


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python disables required assertions")
    main()
