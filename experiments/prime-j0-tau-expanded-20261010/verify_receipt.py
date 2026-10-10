#!/usr/bin/env python3
"""Reconstruct the tau-preexpanded native source through four frozen patches."""

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
ORBIT_X = HERE.parent / "prime-j0-tau-orbit-x-20261010"
FREEZE = "4b563c866"


def digest(data):
    return sha256(data).hexdigest()


def git(*args, env=None):
    return subprocess.run(["git", *args], cwd=ROOT, env=env, check=True,
                          capture_output=True).stdout


def main():
    receipt = json.loads((HERE / "source-receipt.json").read_text())
    earliest = json.loads((F19 / "receipt.json").read_text())
    patches = [F17 / "native-frontier17.patch",
               F19 / "native-frontier19-delta.patch",
               ORBIT_X / "native-orbit-x-delta.patch",
               HERE / "native-tau-expanded-delta.patch"]
    assert digest(patches[-1].read_bytes()) == receipt["delta_patch_sha256"]
    assert receipt["reference_commit"] == git("rev-parse", f"{FREEZE}^").decode().strip()
    for name in ("source-receipt.json", "native-tau-expanded-delta.patch",
                 "make_inputs.py", "make_fresh_fixture.py", "verify_inputs.py",
                 "release-tests.log", "targeted-tests.log"):
        path = HERE / name
        relative = path.relative_to(ROOT)
        assert git("show", f"{FREEZE}:{relative}") == path.read_bytes(), name
    release = (HERE / "release-tests.log").read_bytes()
    targeted = (HERE / "targeted-tests.log").read_bytes()
    assert digest(release) == receipt["release_test_log_sha256"]
    assert digest(targeted) == receipt["targeted_test_log_sha256"]
    assert b"test result: ok. 106 passed; 0 failed;" in release
    assert b"frontier19_expanded_checked_tau_points=21930 retained_bytes=2916756" in targeted
    assert b"test result: ok. 2 passed; 0 failed;" in targeted
    ops = json.loads((HERE / "ops-diagnostic.json").read_text())
    diagnostic = HERE / "ops-diagnostic.patch"
    assert ops["base_source_sha256"] == receipt["prototype_source_sha256"][
        "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs"]
    assert digest(diagnostic.read_bytes()) == ops["diagnostic_patch_sha256"]
    assert digest((HERE / "ops-diagnostic.log").read_bytes()) == ops["diagnostic_log_sha256"]
    assert digest((HERE / "fresh-inputs.json").read_bytes()) == ops["fresh_input_sha256"]
    with tempfile.TemporaryDirectory(prefix="tau-expanded-index-") as temporary:
        environment = os.environ.copy()
        environment["GIT_INDEX_FILE"] = str(Path(temporary) / "index")
        git("read-tree", earliest["base_commit"], env=environment)
        for patch in patches[:3]:
            git("apply", "--cached", str(patch), env=environment)
        for path, expected in receipt["base_source_sha256"].items():
            assert digest(git("show", f":{path}", env=environment)) == expected
        git("apply", "--cached", str(patches[-1]), env=environment)
        for path, expected in receipt["prototype_source_sha256"].items():
            assert digest(git("show", f":{path}", env=environment)) == expected
        git("apply", "--cached", str(diagnostic), env=environment)
        path = "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs"
        assert digest(git("show", f":{path}", env=environment)) == ops[
            "instrumented_source_sha256"]
    assert receipt["retained_bytes"] == 2_916_756
    assert receipt["table_slots"] == 21_949
    assert receipt["checked_tau_points"] == 21_930
    print("tau_expanded_source_receipt_verified=1")


if __name__ == "__main__":
    main()
