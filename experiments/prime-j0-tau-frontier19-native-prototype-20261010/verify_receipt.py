#!/usr/bin/env python3
"""Reconstruct the nineteen-window native source in a temporary Git index."""

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FRONTIER17 = HERE.parent / "prime-j0-tau-frontier-native-prototype-20261010"


def digest(data):
    return sha256(data).hexdigest()


def git(*args, env=None):
    return subprocess.run(["git", *args], cwd=ROOT, env=env, check=True,
                          capture_output=True).stdout


def main():
    record = json.loads((HERE / "receipt.json").read_text())
    prior = json.loads((FRONTIER17 / "receipt.json").read_text())
    first = FRONTIER17 / "native-frontier17.patch"
    second = HERE / "native-frontier19-delta.patch"
    assert record["base_commit"] == prior["base_commit"]
    assert record["frontier17_patch_sha256"] == prior["patch_sha256"] == digest(first.read_bytes())
    assert record["frontier19_delta_patch_sha256"] == digest(second.read_bytes())
    log = (HERE / "release-tests.log").read_bytes()
    assert digest(log) == record["release_test_log_sha256"]
    assert b"test result: ok. 102 passed; 0 failed;" in log
    targeted = (HERE / "targeted-tests.log").read_bytes()
    assert digest(targeted) == record["targeted_test_log_sha256"]
    assert b"frontier19_independent_nonzero_points=21930 retained_bytes=1512020" in targeted
    assert b"frontier19_table_slots=21949 retained_bytes=1512020" in targeted
    assert b"test result: ok. 2 passed; 0 failed;" in targeted
    assert (record["native_table_slots"],
            record["native_nonidentity_slots_independently_checked"],
            record["native_retained_bytes"]) == (21_949, 21_930, 1_512_020)
    assert record["prior_panel_cases_matched_native"] == 4096
    for name, expected in record["atlas_sha256"].items():
        path = HERE.parent / "prime-j0-tau-frontier-20261010" / name
        assert digest(path.read_bytes()) == expected

    with tempfile.TemporaryDirectory(prefix="frontier19-index-") as temporary:
        environment = os.environ.copy()
        environment["GIT_INDEX_FILE"] = str(Path(temporary) / "index")
        git("read-tree", record["base_commit"], env=environment)
        for path, hashes in record["source"].items():
            assert digest(git("show", f"{record['base_commit']}:{path}")) == hashes["base_sha256"]
        git("apply", "--cached", str(first), env=environment)
        for path, hashes in record["source"].items():
            assert digest(git("show", f":{path}", env=environment)) == hashes["frontier17_sha256"]
        git("apply", "--cached", str(second), env=environment)
        for path, hashes in record["source"].items():
            assert digest(git("show", f":{path}", env=environment)) == hashes["frontier19_sha256"]
    print("native_frontier19_receipt_verified=1")


if __name__ == "__main__":
    main()
