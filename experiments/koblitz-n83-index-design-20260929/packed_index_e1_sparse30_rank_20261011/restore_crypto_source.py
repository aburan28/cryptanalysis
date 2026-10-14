#!/usr/bin/env python3
"""Restore the pinned public crypto source used by the frozen N83 run."""

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


HERE = Path(__file__).resolve().parent
LINK = HERE / "crypto_source_snapshot"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_digest(root, paths):
    state = hashlib.sha256()
    for path in sorted(paths):
        state.update(str(path.relative_to(root)).encode())
        state.update(b"\0")
        state.update(bytes.fromhex(sha256(path)))
    return state.hexdigest()


def check_snapshot(root, expected):
    if sha256(root / "Cargo.toml") != expected["crypto_manifest"]:
        raise ValueError("crypto manifest differs from frozen receipt")
    if tree_digest(root, (p for p in root.rglob("*") if p.is_file())) != expected["crypto_source_tree"]:
        raise ValueError("crypto source tree differs from frozen receipt")
    if tree_digest(root, (root / "src").rglob("*.rs")) != expected["crypto_rust_source_tree"]:
        raise ValueError("crypto Rust source tree differs from frozen receipt")


def unpack_archive(archive, destination):
    seen = set()
    with tarfile.open(archive, "r:") as stream:
        for member in stream:
            relative = PurePosixPath(member.name)
            if (relative.is_absolute() or not relative.parts or
                    any(part in ("", ".", "..") for part in relative.parts)):
                raise ValueError("unsafe crypto archive path")
            if member.isdir():
                continue
            if not member.isfile() or member.name in seen:
                raise ValueError("unexpected crypto archive member")
            seen.add(member.name)
            path = destination.joinpath(*relative.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with stream.extractfile(member) as source, path.open("wb") as output:
                while chunk := source.read(1 << 20):
                    output.write(chunk)


def ensure_snapshot(crypto_repo=None):
    if LINK.is_symlink():
        raise ValueError("crypto source snapshot must be a local directory")
    expected = {
        "crypto_commit": "904f0f844f3c1e69e8d22ae5e60ecd56e6648611",
        "crypto_manifest": "8ca2e285ec80488674965e02d0504e499ba291c0f2a02dd11b546a975f6ed557",
        "crypto_source_tree": "f1f03c5a7c34b741c40a6b273c8211dd819e9e36a2db619d33e63938ae1c5268",
        "crypto_rust_source_tree": "271f28243601d3e378c0ede7703722d611dec1d68c014fedec146c2a1f613314",
    }
    target = LINK
    if target.exists():
        check_snapshot(target, expected)
        return target

    repo = Path(crypto_repo or os.environ.get("CRYPTO_REPO", "/Volumes/SSD990/crypto"))
    if not (repo / ".git").exists():
        raise FileNotFoundError(
            "clone https://github.com/aburan28/crypto and set CRYPTO_REPO to that checkout")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="n83-crypto-restore-", dir=target.parent) as folder:
        folder = Path(folder)
        archive = folder / "source.tar"
        staged = folder / "snapshot"
        staged.mkdir()
        subprocess.run(["git", "-C", str(repo), "archive", "--format=tar",
                        f"--output={archive}", expected["crypto_commit"],
                        "Cargo.toml", "src"], check=True)
        unpack_archive(archive, staged)
        check_snapshot(staged, expected)
        if target.exists():
            check_snapshot(target, expected)
        else:
            staged.rename(target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crypto-repo", type=Path)
    args = parser.parse_args()
    print("verified_crypto_source=" + str(ensure_snapshot(args.crypto_repo)))


if __name__ == "__main__":
    main()
