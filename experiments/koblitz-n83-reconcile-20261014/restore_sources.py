#!/usr/bin/env python3
"""Restore the two pinned crypto revisions this reconciliation builds, and check them.

Two snapshots are extracted path by path with `git archive`:

* `snapshots/r770/` from crypto 770f6a69 (the B experiment's revision): the
  library, B's three-file IC/rho producers, A's strong-rho adapter, A's tuned
  rho worker, A's IC producer at this revision, the frozen inputs and the
  pinned pure-Python harness (`oracle.py` and the public-point law). The IC
  online producer gets B's `ic_log_cache.patch`, applied from B's directory and
  checked against the digest B froze.
* `snapshots/r819/` from crypto a8194d61 (the A experiment's source baseline):
  the library and A's IC producer. A's strong adapter was not committed at
  a8194d61; A built it from that tree plus the adapter file whose SHA-256
  (82bc92d2...) A's README records. The byte-identical file merged at 770f6a69
  is copied in, and its digest is checked against that value.

Every file is then checked against `protocol.json`; files shared with B are
also checked against B's frozen `tier1_protocol.json`. `--print-digests` prints
the digests of a fresh extraction (used once, to freeze the protocol).
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
SNAPSHOTS = HERE / "snapshots"
PROTOCOL = HERE / "protocol.json"
B_DIR = HERE.parent / "koblitz-single-target-n83-tier1-20261014"
B_PROTOCOL = B_DIR / "tier1_protocol.json"
B_PATCH = B_DIR / "ic_log_cache.patch"

A_COMMIT = "a8194d616ed8c04489ec46177d369f1b1670360a"
B_COMMIT = "770f6a6925a0d29b768bd79074f54a173e967fe7"
# The adapter's SHA-256 as A's README ("Strong adapter source") records it.
A_ADAPTER_SHA256 = "82bc92d24e096109d4c35288d034c02f63c08241ed87dc83c93655ed668c4cbf"

IC_ONLINE = "examples/koblitz_orbit_dlp_fast_online.rs"
IC_ONLINE_PATCHED = "examples/koblitz_orbit_dlp_fast_online_logcache.rs"
IC_FAST = "examples/koblitz_orbit_dlp_fast.rs"
RHO_RUNG3 = "examples/koblitz_rho_batch_ks_strong_online.rs"
RHO_ADAPTER = "examples/n83_strong_point_eval.rs"
RHO_TUNED = "examples/n83_rho_optimization_eval.rs"
TUNED_CONFIG = "research/n83_evaluation_20261012/optimization/selected_config.json"
INPUT_DIR = "experiments/koblitz-single-target-n83-20261006"
BASE = INPUT_DIR + "/base_n83_K600.jsonl"
Q0_FILE = INPUT_DIR + "/frozen/target_points.jsonl"
FIXTURE = INPUT_DIR + "/frozen/fixture.json"
AUTOLAB = "research/sat_factor_base_review_20260908/autolab"
HARNESS = [
    AUTOLAB + "/boundary_autolab.py",
    AUTOLAB + "/single_target_panel.py",
    AUTOLAB + "/op_accounting.py",
    AUTOLAB + "/protocol.json",
    "research/ic_candidate_tournament_20260915/identity.py",
    "research/ic_candidate_tournament_20260915/oracle.py",
    "tools/curve_identity.py",
    "research/ic_single_target_20260930/curve_ids.json",
    "docs/ic/boundary_targets.json",
]

REVISIONS = {
    "r770": {
        "commit": B_COMMIT,
        "archive": ["Cargo.toml", "Cargo.lock", "src", IC_ONLINE, IC_FAST, RHO_RUNG3, RHO_ADAPTER,
                    RHO_TUNED, TUNED_CONFIG, BASE, Q0_FILE, FIXTURE] + HARNESS,
        "keys": {
            "crypto_manifest": "Cargo.toml", "crypto_lock": "Cargo.lock",
            "ic_online_upstream": IC_ONLINE, "ic_online_patched": IC_ONLINE_PATCHED,
            "ic_fast": IC_FAST, "rho_rung3": RHO_RUNG3, "rho_adapter": RHO_ADAPTER,
            "rho_tuned": RHO_TUNED, "tuned_config": TUNED_CONFIG,
            "base_n83_K600": BASE, "target_points": Q0_FILE, "validation_fixture": FIXTURE,
            **{"harness:" + path: path for path in HARNESS},
        },
    },
    "r819": {
        "commit": A_COMMIT,
        "archive": ["Cargo.toml", "Cargo.lock", "src", IC_FAST],
        "keys": {"crypto_manifest": "Cargo.toml", "crypto_lock": "Cargo.lock",
                 "ic_fast": IC_FAST, "rho_adapter": RHO_ADAPTER},
    },
}
# Keys of r770 that B froze under the same or another name.
SHARED_WITH_B = {
    "crypto_manifest": "crypto_manifest", "crypto_lock": "crypto_lock",
    "ic_online_upstream": "ic_online_upstream", "ic_online_patched": "ic_online_patched",
    "rho_rung3": "rho_strong_online", "base_n83_K600": "base_n83_K600",
    "target_points": "target_points", "validation_fixture": "validation_fixture",
    "crypto_rust_source_tree": "crypto_rust_source_tree",
    **{"harness:" + path: "harness:" + path for path in HARNESS},
}


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


def digests(name, root):
    result = {key: sha256(root / rel) for key, rel in REVISIONS[name]["keys"].items()}
    result["crypto_rust_source_tree"] = tree_digest(root, (root / "src").rglob("*.rs"))
    result["snapshot_tree"] = tree_digest(root, (p for p in root.rglob("*") if p.is_file() and
                                                 "__pycache__" not in p.parts))
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
    with tempfile.TemporaryDirectory(prefix="n83-reconcile-archive-") as folder:
        archive = Path(folder) / "source.tar"
        subprocess.run(["git", "-C", str(repo), "archive", "--format=tar",
                        "--output=" + str(archive), commit] + paths, check=True)
        unpack(archive, destination)


def extract(name, repo, destination):
    spec = REVISIONS[name]
    git_archive(repo, spec["commit"], spec["archive"], destination)
    extra = [path for path in included_files(destination) if not (destination / path).exists()]
    if extra:
        git_archive(repo, spec["commit"], extra, destination)
    if name == "r770":
        if sha256(B_PATCH) != json.loads(B_PROTOCOL.read_text())["crypto_source"]["sha256"]["ic_log_cache_patch"]:
            raise ValueError("B's ic_log_cache.patch differs from B's frozen digest")
        shutil.copyfile(destination / IC_ONLINE, destination / IC_ONLINE_PATCHED)
        subprocess.run(["patch", "--no-backup-if-mismatch", "--forward", "-s", "-p1",
                        "-d", str(destination), "-i", str(B_PATCH)], check=True)
    else:
        # A's adapter: the merged file at 770f6a69, byte-identical to what A built.
        git_archive(repo, B_COMMIT, [RHO_ADAPTER], destination)
        if sha256(destination / RHO_ADAPTER) != A_ADAPTER_SHA256:
            raise ValueError("strong adapter differs from the source A's README records")


def check(name, root, expected):
    actual = digests(name, root)
    wrong = sorted(key for key, value in expected.items() if actual.get(key) != value)
    if wrong:
        raise ValueError(name + " snapshot differs from the frozen protocol: " + ", ".join(wrong))
    if name == "r770":
        frozen_b = json.loads(B_PROTOCOL.read_text())["crypto_source"]["sha256"]
        wrong = sorted(key for key, b_key in SHARED_WITH_B.items() if actual[key] != frozen_b[b_key])
        if wrong:
            raise ValueError("r770 files differ from B's frozen digests: " + ", ".join(wrong))
    if name == "r819" and actual["rho_adapter"] != A_ADAPTER_SHA256:
        raise ValueError("r819 adapter is not A's adapter")
    return actual


def ensure(name, crypto_repo=None):
    protocol = json.loads(PROTOCOL.read_text())
    pinned = protocol["sources"][name]
    if pinned["commit"] != REVISIONS[name]["commit"]:
        raise ValueError("protocol commit differs from the restore script")
    root = SNAPSHOTS / name
    if root.is_symlink():
        raise ValueError("snapshot must be a local directory")
    if root.exists():
        check(name, root, pinned["sha256"])
        return root
    if crypto_repo is None or not (Path(crypto_repo) / ".git").exists():
        raise FileNotFoundError("pass --crypto-repo, a clone of https://github.com/aburan28/crypto")
    SNAPSHOTS.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="n83-reconcile-restore-", dir=SNAPSHOTS) as folder:
        staged = Path(folder) / name
        staged.mkdir()
        extract(name, crypto_repo, staged)
        check(name, staged, pinned["sha256"])
        staged.rename(root)
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crypto-repo", type=Path)
    parser.add_argument("--print-digests", action="store_true")
    args = parser.parse_args()
    if args.print_digests:
        out = {}
        for name in REVISIONS:
            with tempfile.TemporaryDirectory(prefix="n83-reconcile-digests-") as folder:
                staged = Path(folder)
                extract(name, args.crypto_repo, staged)
                out[name] = digests(name, staged)
        print(json.dumps(out, indent=2, sort_keys=True))
        return
    for name in REVISIONS:
        print("verified_snapshot=" + str(ensure(name, args.crypto_repo)))


if __name__ == "__main__":
    main()
