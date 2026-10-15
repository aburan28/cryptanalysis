#!/usr/bin/env python3
"""Restore and check every pinned source this experiment builds.

* crypto 770f6a69 into `snapshots/r770/`, with the reconcile experiment's own
  extraction (`../koblitz-n83-reconcile-20261014/restore_sources.py`: library,
  B's IC producer plus B's `ic_log_cache.patch`, A's tuned rho worker and its
  config, the K600 base, Q0 and the pinned oracle), checked against the
  reconcile protocol's r770 digests (which are themselves checked against B's
  frozen digests). Then `make_online_source.py` derives the lift_scan producer
  and its digest is checked against `protocol.json`.
* crypto 904f0f84 into the frozen E-1 experiment's `crypto_source_snapshot/`,
  with that experiment's Tier 1 restore (`restore_crypto_source.py`), for the
  stage crate.
* the stage source, the two-limb canonicalizer and both crates' manifests and
  lock files are checked against `protocol.json`.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent
RECONCILE = EXPERIMENTS / "koblitz-n83-reconcile-20261014"
E1_TIER1 = EXPERIMENTS / "koblitz-n83-index-design-20260929" / "packed_index_e1_canonical_tier1_20261014"
SNAPSHOT = HERE / "snapshots" / "r770"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def local_files():
    return {
        "lift2_lib": HERE / "lift2/src/lib.rs",
        "lift2_tests": HERE / "lift2/tests/exhaustive.rs",
        "lift2_manifest": HERE / "lift2/Cargo.toml",
        "stage_source": HERE / "stage/native_packed_index_liftscan.rs",
        "stage_manifest": HERE / "stage/Cargo.toml",
        "stage_lock": HERE / "stage/Cargo.lock",
        "online_manifest": HERE / "online/Cargo.toml",
        "online_lock": HERE / "online/Cargo.lock",
        "online_derivation": HERE / "make_online_source.py",
        "arm_wrapper": HERE / "arm.py",
        "schedule_builder": HERE / "make_schedule.py",
        "schedule_runner": HERE / "run_schedule.py",
        "receipt_verifier": HERE / "verify_receipt.py",
    }


def restore(crypto_repo):
    protocol = json.loads((HERE / "protocol.json").read_text())
    pins = protocol["sources"]
    sys.path.insert(0, str(RECONCILE))
    import restore_sources as reconcile  # noqa: E402
    expected_r770 = json.loads((RECONCILE / "protocol.json").read_text())["sources"]["r770"]["sha256"]
    if SNAPSHOT.is_symlink():
        raise ValueError("snapshots/r770 must be a local directory")
    if not SNAPSHOT.exists():
        if crypto_repo is None:
            raise FileNotFoundError("pass --crypto-repo, a clone of https://github.com/aburan28/crypto")
        SNAPSHOT.parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="n83-liftscan-restore-", dir=SNAPSHOT.parent) as folder:
            staged = Path(folder) / "r770"
            staged.mkdir()
            reconcile.extract("r770", crypto_repo, staged)
            reconcile.check("r770", staged, expected_r770)
            staged.rename(SNAPSHOT)
    derived = SNAPSHOT / "examples" / "koblitz_orbit_dlp_fast_online_liftscan.rs"
    if derived.exists():
        derived.unlink()
    reconcile.check("r770", SNAPSHOT, expected_r770)
    subprocess.run([sys.executable, str(HERE / "make_online_source.py")], check=True,
                   stdout=subprocess.DEVNULL)
    if sha256(derived) != pins["online_source_sha256"]:
        raise ValueError("derived online producer differs from the frozen digest")
    sys.path.insert(0, str(E1_TIER1))
    import restore_crypto_source as e1  # noqa: E402
    e1_root = e1.ensure_snapshot(crypto_repo)
    wrong = [key for key, path in local_files().items() if sha256(path) != pins["local_sha256"][key]]
    if wrong:
        raise ValueError("local source differs from protocol.json: " + ", ".join(wrong))
    return {"r770": str(SNAPSHOT), "e1_crypto_904f0f84": str(e1_root),
            "online_source_sha256": sha256(derived)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crypto-repo", type=Path)
    parser.add_argument("--print-local-digests", action="store_true",
                        help="print the local digests (used once, to freeze the protocol)")
    args = parser.parse_args()
    if args.print_local_digests:
        print(json.dumps({key: sha256(path) for key, path in local_files().items()},
                         indent=2, sort_keys=True))
        return
    print(json.dumps(restore(args.crypto_repo), sort_keys=True))


if __name__ == "__main__":
    main()
