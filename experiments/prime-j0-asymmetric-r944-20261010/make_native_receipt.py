#!/usr/bin/env python3
"""Record final native build and replay evidence after all commands pass."""

from hashlib import sha256
import gzip
import json
from pathlib import Path
import platform
import subprocess
import sys

from verify import HERE, check_fixture, digest


def main():
    assert len(sys.argv) == 3, "usage: make_native_receipt.py BINARY MATERIALIZED_CRATE"
    binary = Path(sys.argv[1]).resolve()
    crate = Path(sys.argv[2]).resolve()
    materialization = json.loads((HERE / "native-materialization.json").read_bytes())
    generated = materialization["generated_sha256"]
    for name, expected in generated.items():
        assert digest((crate / name).read_bytes()) == expected, name
    targeted = (HERE / "native-targeted-tests.log").read_bytes()
    full = (HERE / "full-release-tests.log").read_bytes()
    assert b"test result: ok. 2 passed; 0 failed;" in targeted
    assert b"test result: ok. 135 passed; 0 failed;" in full
    fixtures = {
        "prior4096": (HERE.parent / "prime-j0-bound-budget15-gauge-20261010/fresh-fixture.json",
                      gzip.decompress((HERE / "prior4096.stdout.gz").read_bytes()), 4096),
        "edge": (HERE.parent / "prime-j0-tau-bucket-two-x-20261010/edge-fixture.json",
                 (HERE / "edge.stdout").read_bytes(), 10),
    }
    cli = {}
    for label, (fixture, output, count) in fixtures.items():
        assert (HERE / f"{label}.stderr").read_bytes() == b""
        cli[label] = check_fixture(label, fixture, output, count)
    receipt = {
        "schema": 1,
        "status": "passed",
        "timing_class": "correctness_only",
        "machine": platform.machine(),
        "system": platform.system(),
        "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
        "binary_sha256": digest(binary.read_bytes()),
        "generated_sha256": generated,
        "materializer_sha256": digest((HERE / "materialize_native.py").read_bytes()),
        "base_patch_sha256": materialization["base_patch_sha256"],
        "delta_patch_sha256": materialization["delta_patch_sha256"],
        "targeted_log_sha256": digest(targeted),
        "full_log_sha256": digest(full),
        "build_log_sha256": digest((HERE / "release-build.log").read_bytes()),
        "cli": cli,
    }
    target = HERE / "native-receipt.json"
    assert not target.exists(), "native receipt already exists"
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
