#!/usr/bin/env python3
"""Independently verify direct-rho native edge-fixture stdout."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FIXTURE = ROOT / "experiments/prime-j0-tau-bucket-two-x-20261010/edge-fixture.json"
sys.path.insert(0, str(ROOT / "experiments/prime-j0-power2-residual-20261010"))
from verify_fixture import check_fixture


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def main() -> None:
    assert len(sys.argv) == 3, "usage: verify_edge.py NATIVE_BINARY MATERIALIZATION_JSON"
    binary = Path(sys.argv[1]).resolve()
    materialization = Path(sys.argv[2]).resolve()
    stdout = (HERE / "edge.stdout").read_bytes()
    assert (HERE / "edge.stderr").read_bytes() == b""
    result = check_fixture(
        "unit_orbit_u256_tau_dual_rho0_direct_gauge_xyzz_tau_fixed",
        "edge", FIXTURE, stdout, 10)
    compressed = gzip.compress(stdout, mtime=0)
    (HERE / "edge.stdout.gz").write_bytes(compressed)
    receipt = {"schema": 1, "status": "passed", "timing_class": "correctness_only",
               "cases": result["cases"], "point_stream_sha256": result["point_stream_sha256"],
               "stdout_sha256": digest(stdout),
               "stdout_gzip_sha256": digest(compressed),
               "fixture_sha256": digest(FIXTURE.read_bytes()),
               "binary_sha256": digest(binary.read_bytes()),
               "materialization_sha256": digest(materialization.read_bytes()),
               "verifier_sha256": digest(Path(__file__).read_bytes())}
    (HERE / "edge-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
