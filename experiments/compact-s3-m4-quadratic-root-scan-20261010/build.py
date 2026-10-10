#!/usr/bin/env python3
"""Build and hash the isolated native fixed-output S3 scanner."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
CRYPTO = Path("/Volumes/SSD990/crypto")
TARGET = Path("/private/tmp/q20261010111900-cargo-target")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_tree():
    paths = [CRYPTO / name for name in ("Cargo.toml", "Cargo.lock", "build.rs")]
    paths += [path for path in (CRYPTO / "src").rglob("*")
              if path.is_file() and path.suffix in
              (".rs", ".c", ".cc", ".cpp", ".h", ".hpp", ".cu")]
    rows = {str(path.relative_to(CRYPTO)): sha(path)
            for path in sorted(set(paths)) if path.is_file()}
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest(), len(rows)


def main():
    assert not (HERE / "build_receipt.json").exists()
    manifest = HERE / "Cargo.toml"
    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = str(TARGET)
    env["CARGO_BUILD_JOBS"] = "2"
    commands = [
        ["cargo", "test", "--offline", "--release", "--manifest-path",
         str(manifest)],
        ["cargo", "build", "--offline", "--release", "--manifest-path",
         str(manifest)],
    ]
    log = HERE / "build.log"
    results = []
    with log.open("w") as stream:
        for command in commands:
            completed = subprocess.run(command, cwd=HERE, env=env,
                                       stdout=stream, stderr=subprocess.STDOUT,
                                       check=False)
            results.append({"command": command,
                            "exit_code": completed.returncode})
            if completed.returncode:
                raise RuntimeError(f"build failed: {command}")
    binary = TARGET / "release/compact_s3_fixed_output_scan"
    assert binary.is_file()
    tree_hash, tree_files = source_tree()
    receipt = {
        "schema": "q20261010111900-native-build-v1",
        "status": "PASS", "commands": results,
        "source_sha256": sha(HERE / "scan.rs"),
        "build_script_sha256": sha(Path(__file__)),
        "cargo_manifest_sha256": sha(manifest),
        "cargo_lock_sha256": sha(HERE / "Cargo.lock"),
        "crypto_source_tree_sha256": tree_hash,
        "crypto_source_file_count": tree_files,
        "crypto_git_head": subprocess.check_output(
            ["git", "-C", str(CRYPTO), "rev-parse", "HEAD"],
            text=True).strip(),
        "rustc_version": subprocess.check_output(
            ["rustc", "--version"], text=True).strip(),
        "binary_path": str(binary),
        "binary_sha256": sha(binary),
        "build_log_sha256": sha(log),
    }
    (HERE / "build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "binary_sha256": sha(binary),
                      "crypto_source_tree_sha256": tree_hash}))


if __name__ == "__main__":
    main()
