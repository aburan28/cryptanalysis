#!/usr/bin/env python3
"""Restore the pinned crypto source and frozen inputs for the N83 one-target Tier 1 panel.

Extracts, with `git archive`, only the paths the panel builds or reads from the
pinned crypto commit, applies `ic_log_cache.patch` to a copy of the IC example,
and checks every file against the digests frozen in `tier1_protocol.json`.
Nothing else from crypto is copied. `--print-digests` prints the digests of a
fresh extraction (used once, to freeze the protocol) without checking them.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "crypto_source_snapshot"
PROTOCOL = HERE / "tier1_protocol.json"
PATCH = HERE / "ic_log_cache.patch"
UPSTREAM_IC = "examples/koblitz_orbit_dlp_fast_online.rs"
PATCHED_IC = "examples/koblitz_orbit_dlp_fast_online_logcache.rs"
STRONG_RHO = "examples/koblitz_rho_batch_ks_strong_online.rs"
PACKED_RHO = "examples/koblitz_rho_fixture.rs"
INPUT_DIR = "experiments/koblitz-single-target-n83-20261006"
AUTOLAB = "research/sat_factor_base_review_20260908/autolab"
TOURNAMENT = "research/ic_candidate_tournament_20260915"
# The n=61 isolated vs_rho harness: its claim builder, claim checker, replay
# oracle, identities and the boundary ledger they validate against.
HARNESS = [
    AUTOLAB + "/boundary_autolab.py",
    AUTOLAB + "/single_target_panel.py",
    AUTOLAB + "/op_accounting.py",
    AUTOLAB + "/protocol.json",
    TOURNAMENT + "/identity.py",
    TOURNAMENT + "/oracle.py",
    "tools/curve_identity.py",
    "research/ic_single_target_20260930/curve_ids.json",
    "docs/ic/boundary_targets.json",
]
ARCHIVE_PATHS = [
    "Cargo.toml", "Cargo.lock", "src", UPSTREAM_IC, STRONG_RHO, PACKED_RHO,
    INPUT_DIR + "/base_n83_K600.jsonl",
    INPUT_DIR + "/frozen/target_points.jsonl",
    INPUT_DIR + "/frozen/fixture.json",
] + HARNESS
FILE_KEYS = {
    "crypto_manifest": "Cargo.toml",
    "crypto_lock": "Cargo.lock",
    "ic_online_upstream": UPSTREAM_IC,
    "ic_online_patched": PATCHED_IC,
    "rho_strong_online": STRONG_RHO,
    "rho_packed_legacy": PACKED_RHO,
    "base_n83_K600": INPUT_DIR + "/base_n83_K600.jsonl",
    "target_points": INPUT_DIR + "/frozen/target_points.jsonl",
    "validation_fixture": INPUT_DIR + "/frozen/fixture.json",
}
FILE_KEYS.update({"harness:" + path: path for path in HARNESS})


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_digest(root, paths):
    state = hashlib.sha256()
    for path in sorted(paths):
        state.update(str(path.relative_to(root)).encode())
        state.update(b"\0")
        state.update(bytes.fromhex(sha256(path)))
    return state.hexdigest()


def digests(root):
    result = {key: sha256(root / rel) for key, rel in FILE_KEYS.items()}
    result["crypto_rust_source_tree"] = tree_digest(root, (root / "src").rglob("*.rs"))
    # Python bytecode the harness writes when imported is not source.
    result["snapshot_tree"] = tree_digest(root, (p for p in root.rglob("*") if p.is_file() and
                                                 "__pycache__" not in p.parts))
    result["ic_log_cache_patch"] = sha256(PATCH)
    return result


def unpack(archive, destination):
    seen = set()
    with tarfile.open(archive, "r:") as stream:
        for member in stream:
            relative = PurePosixPath(member.name)
            if (relative.is_absolute() or not relative.parts or
                    any(part in ("", ".", "..") for part in relative.parts)):
                raise ValueError("unsafe crypto archive path")
            if member.isdir() or member.name == "pax_global_header":
                continue
            if not member.isfile() or member.name in seen:
                raise ValueError("unexpected crypto archive member " + member.name)
            seen.add(member.name)
            path = destination.joinpath(*relative.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with stream.extractfile(member) as source, path.open("wb") as output:
                shutil.copyfileobj(source, output, 1 << 20)


INCLUDE = re.compile(r'include_(?:str|bytes)!\(\s*"([^"]+)"\s*\)')


def included_files(root):
    """Files outside src/ that the library compiles in with include_str!/include_bytes!."""
    found = set()
    for source in (root / "src").rglob("*.rs"):
        for literal in INCLUDE.findall(source.read_text(errors="replace")):
            target = Path(os.path.normpath(source.parent / literal))
            relative = target.relative_to(root)
            if relative.parts[0] != "src":
                found.add(relative.as_posix())
    return sorted(found)


def git_archive(repo, commit, paths, destination):
    with tempfile.TemporaryDirectory(prefix="n83-onetarget-archive-") as folder:
        archive = Path(folder) / "source.tar"
        subprocess.run(["git", "-C", str(repo), "archive", "--format=tar",
                        "--output=" + str(archive), commit] + paths, check=True)
        unpack(archive, destination)


def extract(repo, commit, destination):
    git_archive(repo, commit, ARCHIVE_PATHS, destination)
    extra = [path for path in included_files(destination) if not (destination / path).exists()]
    if extra:
        git_archive(repo, commit, extra, destination)
    shutil.copyfile(destination / UPSTREAM_IC, destination / PATCHED_IC)
    subprocess.run(["patch", "--no-backup-if-mismatch", "--forward", "-s", "-p1",
                    "-d", str(destination), "-i", str(PATCH)], check=True)


def check(root, expected):
    actual = digests(root)
    wrong = sorted(key for key, value in expected.items() if actual.get(key) != value)
    if wrong:
        raise ValueError("crypto snapshot differs from the frozen protocol: " + ", ".join(wrong))
    return actual


def ensure_snapshot(crypto_repo=None):
    protocol = json.loads(PROTOCOL.read_text())
    pinned = protocol["crypto_source"]
    expected = pinned["sha256"]
    if SNAPSHOT.is_symlink():
        raise ValueError("crypto source snapshot must be a local directory")
    if SNAPSHOT.exists():
        check(SNAPSHOT, expected)
        return SNAPSHOT
    if crypto_repo is None or not (Path(crypto_repo) / ".git").exists():
        raise FileNotFoundError("pass --crypto-repo, a clone of https://github.com/aburan28/crypto")
    with tempfile.TemporaryDirectory(prefix="n83-onetarget-restore-", dir=HERE) as folder:
        staged = Path(folder) / "snapshot"
        staged.mkdir()
        extract(crypto_repo, pinned["commit"], staged)
        check(staged, expected)
        staged.rename(SNAPSHOT)
    return SNAPSHOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crypto-repo", type=Path)
    parser.add_argument("--print-digests", action="store_true")
    args = parser.parse_args()
    if args.print_digests:
        commit = json.loads(PROTOCOL.read_text())["crypto_source"]["commit"]
        with tempfile.TemporaryDirectory(prefix="n83-onetarget-digests-") as folder:
            staged = Path(folder)
            extract(args.crypto_repo, commit, staged)
            print(json.dumps(digests(staged), indent=2, sort_keys=True))
        return
    print("verified_crypto_source=" + str(ensure_snapshot(args.crypto_repo)))


if __name__ == "__main__":
    main()
