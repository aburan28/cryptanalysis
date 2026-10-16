#!/usr/bin/env python3
"""Restore and check every pinned source this experiment builds.

* crypto 770f6a69 into `snapshots/r770/`, with the reconcile experiment's own
  extraction (`../koblitz-n83-reconcile-20261014/restore_sources.py`: library,
  B's IC producer plus B's `ic_log_cache.patch`, A's tuned rho worker and its
  config, the K600 base, Q0 and the pinned oracle), checked against the
  reconcile protocol's r770 digests (which are themselves checked against B's
  frozen digests). Then `make_online_source.py` derives the probe-pipeline
  producer with `make_probepipe_source.py` and `make_combined_source.py`
  (checked against `claude/n83-probe-pipeline`'s frozen digest), adds the
  root-table layout selector, and its digest is checked against
  `protocol.json`; `make_profile_source.py` derives the diagnostic profiler.
* every local source, manifest, lock file and input (including the
  two-limb `lift2` canonicalizer copied from `claude/n83-liftscan`) is
  checked against `protocol.json`.

The restore machinery of `claude/n83-probe-pipeline` (@ ddbb86a9c), itself
`claude/n83-combined`'s and `claude/n83-scan-order`'s; only the derived file
names and the local file list differ.
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
SNAPSHOT = HERE / "snapshots" / "r770"
DERIVED = SNAPSHOT / "examples" / "koblitz_orbit_dlp_fast_online_tablefilter.rs"
PROFILER = SNAPSHOT / "examples" / "koblitz_orbit_dlp_fast_online_tableprofile.rs"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def local_files():
    return {
        "online_manifest": HERE / "online/Cargo.toml",
        "online_lock": HERE / "online/Cargo.lock",
        "online_derivation": HERE / "make_online_source.py",
        "probepipe_derivation": HERE / "make_probepipe_source.py",
        "combined_derivation": HERE / "make_combined_source.py",
        "profile_derivation": HERE / "make_profile_source.py",
        "lift2_lib": HERE / "lift2/src/lib.rs",
        "lift2_tests": HERE / "lift2/tests/exhaustive.rs",
        "lift2_manifest": HERE / "lift2/Cargo.toml",
        "lift2_lock": HERE / "lift2/Cargo.lock",
        "arm_wrapper": HERE / "arm.py",
        "panels": HERE / "panels.py",
        "schedule_builder": HERE / "make_schedule.py",
        "schedule_runner": HERE / "run_schedule.py",
        "receipt_verifier": HERE / "verify_receipt.py",
        "targets_builder": HERE / "make_targets.py",
        "primary_targets": HERE / "inputs/primary_targets.json",
        "archived_identities": HERE / "inputs/archived_identities.json",
        "power_check": HERE / "power_check.py",
        "power_prior": HERE / "inputs/power_prior.json",
        "log_table_check": HERE / "check_log_table.py",
        "power_result": HERE / "analysis/power.json",
        "profile_table_builder": HERE / "analysis/make_profile_table.py",
        "profile_local": HERE / "analysis/profile_local.json",
    }


def restore(crypto_repo, check_pins=True):
    sys.path.insert(0, str(RECONCILE))
    import restore_sources as reconcile  # noqa: E402
    expected_r770 = json.loads((RECONCILE / "protocol.json").read_text())["sources"]["r770"]["sha256"]
    if SNAPSHOT.is_symlink():
        raise ValueError("snapshots/r770 must be a local directory")
    if not SNAPSHOT.exists():
        if crypto_repo is None:
            raise FileNotFoundError("pass --crypto-repo, a clone of https://github.com/aburan28/crypto")
        SNAPSHOT.parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="n83-tablefilter-restore-", dir=SNAPSHOT.parent) as folder:
            staged = Path(folder) / "r770"
            staged.mkdir()
            reconcile.extract("r770", crypto_repo, staged)
            reconcile.check("r770", staged, expected_r770)
            staged.rename(SNAPSHOT)
    for derived in (DERIVED, PROFILER):
        if derived.exists():
            derived.unlink()
    reconcile.check("r770", SNAPSHOT, expected_r770)
    subprocess.run([sys.executable, str(HERE / "make_online_source.py")], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(HERE / "make_profile_source.py")], check=True,
                   stdout=subprocess.DEVNULL)
    result = {"r770": str(SNAPSHOT), "online_source_sha256": sha256(DERIVED),
              "profile_source_sha256": sha256(PROFILER)}
    if check_pins:
        pins = json.loads((HERE / "protocol.json").read_text())["sources"]
        if sha256(DERIVED) != pins["online_source_sha256"]:
            raise ValueError("derived online producer differs from the frozen digest")
        if sha256(PROFILER) != pins["profile_source_sha256"]:
            raise ValueError("derived profiler differs from the frozen digest")
        wrong = [key for key, path in local_files().items() if sha256(path) != pins["local_sha256"][key]]
        if wrong:
            raise ValueError("local source differs from protocol.json: " + ", ".join(wrong))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crypto-repo", type=Path)
    parser.add_argument("--print-local-digests", action="store_true",
                        help="print the local digests (used once, to freeze the protocol)")
    parser.add_argument("--no-pin-check", action="store_true",
                        help="development only: restore and derive without checking protocol pins")
    args = parser.parse_args()
    if args.print_local_digests:
        print(json.dumps({key: sha256(path) for key, path in local_files().items()},
                         indent=2, sort_keys=True))
        return
    print(json.dumps(restore(args.crypto_repo, not args.no_pin_check), sort_keys=True))


if __name__ == "__main__":
    main()
