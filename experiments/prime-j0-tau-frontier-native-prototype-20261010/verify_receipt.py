#!/usr/bin/env python3
"""Replay the native patch in a temporary index and verify frozen evidence."""

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def digest(data):
    return sha256(data).hexdigest()


def git(*args, env=None):
    return subprocess.run(["git", *args], cwd=ROOT, env=env, check=True,
                          capture_output=True).stdout


def main():
    record = json.loads((HERE / "receipt.json").read_text())
    patch = HERE / "native-frontier17.patch"
    assert digest(patch.read_bytes()) == record["patch_sha256"]
    assert digest((HERE / "release-tests.log").read_bytes()) == record["release_test_log_sha256"]
    assert digest((HERE / "fixture129.out").read_bytes()) == record["fixture_log_sha256"]
    fixture = (HERE / "fixture129.out").read_text().splitlines()
    assert len(fixture) == record["fixed_fixture_cases_verified"] == 129
    assert all(line.startswith("verified=1 ") and
               line.endswith("mode=unit_orbit_u256_tau_frontier17_fixed")
               for line in fixture)
    assert "test result: ok. 100 passed; 0 failed;" in (HERE / "release-tests.log").read_text()
    for name, expected in record["atlas_sha256"].items():
        path = ROOT / "experiments/prime-j0-tau-frontier-20261010" / name
        assert digest(path.read_bytes()) == expected

    with tempfile.TemporaryDirectory(prefix="frontier17-index-") as temporary:
        environment = os.environ.copy()
        environment["GIT_INDEX_FILE"] = str(Path(temporary) / "index")
        git("read-tree", record["base_commit"], env=environment)
        for path, hashes in record["source"].items():
            assert digest(git("show", f"{record['base_commit']}:{path}")) == hashes["base_sha256"]
        git("apply", "--cached", str(patch), env=environment)
        for path, hashes in record["source"].items():
            assert digest(git("show", f":{path}", env=environment)) == hashes["prototype_sha256"]
    print("native_frontier17_receipt_verified=1")


if __name__ == "__main__":
    main()
