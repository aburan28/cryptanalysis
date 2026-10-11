#!/usr/bin/env python3
"""Build the isolated native S3 stage against the local crypto library."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args],
                                   text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--crypto-root", type=Path,
                        default=Path("/Volumes/SSD990/crypto"))
    parser.add_argument("--build-root", type=Path,
                        default=Path("/private/tmp/compact-s3-m4-native-20261003"))
    args = parser.parse_args()
    crypto = args.crypto_root.resolve()
    build = args.build_root.resolve()
    source = HERE / "native_s3_root.rs"
    assert source.is_file() and (crypto / "Cargo.toml").is_file()
    protected = ["Cargo.toml", "Cargo.lock", "src/binary_ecc/f2m.rs",
                 "src/cryptanalysis/semaev_decomp.rs",
                 "src/cryptanalysis/koblitz_fast_arith.rs"]
    assert not git(crypto, "status", "--porcelain", "--", *protected), (
        "crypto arithmetic dependency changed in place; freeze it first")
    build.mkdir(parents=True, exist_ok=True)
    manifest = build / "Cargo.toml"
    content = ("[package]\nname = \"compact_s3_root_probe\"\n"
               "version = \"0.1.0\"\nedition = \"2021\"\n\n"
               "[[bin]]\nname = \"native_s3_root\"\n"
               f"path = {json.dumps(str(source))}\n\n"
               "[dependencies]\n"
               f"crypto_lib = {{ package = \"crypto\", path = {json.dumps(str(crypto))} }}\n"
               "serde_json = { version = \"1.0\", features = [\"arbitrary_precision\"] }\n"
               "libc = \"0.2\"\n")
    manifest.write_text(content)
    log_path = build / "cargo-build.log"
    build_env = os.environ.copy()
    build_env["NATIVE_S3_SOURCE_SHA256"] = sha(source)
    build_env["NATIVE_S3_BUILD_MANIFEST_SHA256"] = sha(manifest)
    with log_path.open("w") as log:
        completed = subprocess.run(
            ["cargo", "build", "--release", "--offline", "--manifest-path",
             str(manifest)], stdout=log, stderr=subprocess.STDOUT,
            cwd=build, env=build_env, check=False)
    if completed.returncode:
        print(log_path.read_text()[-6000:])
        raise SystemExit(completed.returncode)
    binary = build / "target/release/native_s3_root"
    assert binary.is_file()
    record = {
        "kind": "isolated_native_s3_root_build",
        "status": "PASS",
        "source_sha256": sha(source),
        "build_script_sha256": sha(Path(__file__)),
        "cargo_manifest_sha256": sha(manifest),
        "crypto_git_head": git(crypto, "rev-parse", "HEAD"),
        "crypto_arithmetic_sources_sha256": {
            name: sha(crypto / name) for name in protected
        },
        "rustc_version": subprocess.check_output(["rustc", "--version"],
                                                  text=True).strip(),
        "cargo_version": subprocess.check_output(["cargo", "--version"],
                                                  text=True).strip(),
        "binary_sha256": sha(binary),
        "build_log_sha256": sha(log_path),
        "binary_path": str(binary),
    }
    output = HERE / "native_build_receipt.json"
    output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "binary_path": str(binary),
                      "binary_sha256": record["binary_sha256"]}))


if __name__ == "__main__":
    main()
