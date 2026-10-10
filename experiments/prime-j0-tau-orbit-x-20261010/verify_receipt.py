#!/usr/bin/env python3
"""Reconstruct the orbit-X native source through the three frozen patches."""

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
F17 = HERE.parent / "prime-j0-tau-frontier-native-prototype-20261010"
F19 = HERE.parent / "prime-j0-tau-frontier19-native-prototype-20261010"


def digest(data):
    return sha256(data).hexdigest()


def git(*args, env=None):
    return subprocess.run(["git", *args], cwd=ROOT, env=env, check=True,
                          capture_output=True).stdout


def main():
    receipt = json.loads((HERE / "source-receipt.json").read_text())
    earlier = json.loads((F19 / "receipt.json").read_text())
    patches = [F17 / "native-frontier17.patch",
               F19 / "native-frontier19-delta.patch",
               HERE / "native-orbit-x-delta.patch"]
    assert digest(patches[-1].read_bytes()) == receipt["delta_patch_sha256"]
    assert receipt["reference_commit"] == git("rev-parse", "3326010dd^").decode().strip()
    for name in ("source-receipt.json", "native-orbit-x-delta.patch",
                 "make_inputs.py", "make_fresh_fixture.py", "verify_inputs.py",
                 "release-tests.log"):
        path = HERE / name
        relative = path.relative_to(ROOT)
        assert git("show", f"3326010dd:{relative}") == path.read_bytes(), name
    log = (HERE / "release-tests.log").read_bytes()
    assert b"test result: ok. 104 passed; 0 failed;" in log
    with tempfile.TemporaryDirectory(prefix="orbit-x-index-") as temporary:
        environment = os.environ.copy()
        environment["GIT_INDEX_FILE"] = str(Path(temporary) / "index")
        git("read-tree", earlier["base_commit"], env=environment)
        for patch in patches[:2]:
            git("apply", "--cached", str(patch), env=environment)
        for path, expected in receipt["base_source_sha256"].items():
            assert digest(git("show", f":{path}", env=environment)) == expected
        git("apply", "--cached", str(patches[-1]), env=environment)
        for path, expected in receipt["prototype_source_sha256"].items():
            assert digest(git("show", f":{path}", env=environment)) == expected
    assert receipt["retained_bytes"] == 2_916_756
    print("orbit_x_source_receipt_verified=1")


if __name__ == "__main__":
    main()
