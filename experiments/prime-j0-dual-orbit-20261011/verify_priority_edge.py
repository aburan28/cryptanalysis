#!/usr/bin/env python3
"""Bind the priority-atlas edge replay to its native materialization."""

import gzip
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
VERIFIER = HERE.parent / "prime-j0-power2-residual-20261010/verify_fixture.py"
SPEC = importlib.util.spec_from_file_location("priority_edge_reference", VERIFIER)
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)
FIXTURE = HERE.parent / "prime-j0-tau-bucket-two-x-20261010/edge-fixture.json"
MODE = "unit_orbit_u256_tau_dual_rho0_folded_gauge_xyzz_tau_fixed"


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    assert len(sys.argv) == 3, \
        "usage: verify_priority_edge.py NATIVE_BINARY MATERIALIZATION_JSON"
    binary = Path(sys.argv[1]).resolve()
    materialization_path = Path(sys.argv[2]).resolve()
    assert (HERE / "priority-native-edge.stderr").read_bytes() == b""
    raw = (HERE / "priority-native-edge.stdout").read_bytes()
    checked = reference.check_fixture(MODE, "edge", FIXTURE, raw, 10)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    (HERE / "priority-native-edge.stdout.gz").write_bytes(compressed)
    assert gzip.decompress(compressed) == raw
    materialization = materialization_path.read_bytes()
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
    (HERE / "priority-native-edge-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
