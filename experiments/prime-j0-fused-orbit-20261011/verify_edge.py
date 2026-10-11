#!/usr/bin/env python3
"""Bind fused-orbit edge fixture output to native binary and source."""

import gzip
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
VERIFIER = HERE.parent / "prime-j0-power2-residual-20261010/verify_fixture.py"
SPEC = importlib.util.spec_from_file_location("exact_mode_fixture", VERIFIER)
fixture_verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture_verifier)
FIXTURE = HERE.parent / "prime-j0-tau-bucket-two-x-20261010/edge-fixture.json"
MODE = "unit_orbit_u256_tau_fused_orbit_gauge_xyzz_tau_fixed"


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    assert len(sys.argv) == 2, "usage: verify_edge.py NATIVE_BINARY"
    binary = Path(sys.argv[1]).resolve()
    assert (HERE / "native-edge.stderr").read_bytes() == b""
    raw = (HERE / "native-edge.stdout").read_bytes()
    checked = fixture_verifier.check_fixture(MODE, "edge", FIXTURE, raw, 10)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    (HERE / "native-edge.stdout.gz").write_bytes(compressed)
    assert gzip.decompress(compressed) == raw
    materialization = (HERE / "native-materialization.json").read_bytes()
    receipt = {"schema": 1, "status": "passed", "timing_class": "correctness_only",
               "mode": MODE, "cases": checked["cases"],
               "fixture_sha256": checked["fixture_sha256"],
               "stdout_sha256": checked["stdout_sha256"],
               "point_stream_sha256": checked["point_stream_sha256"],
               "stdout_gzip_sha256": digest(compressed),
               "binary_sha256": digest(binary.read_bytes()),
               "materialization_sha256": digest(materialization),
               "verifier_sha256": digest(Path(__file__).read_bytes()),
               "generic_verifier_sha256": digest(VERIFIER.read_bytes())}
    (HERE / "native-edge-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
