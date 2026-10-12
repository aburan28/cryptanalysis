#!/usr/bin/env python3
"""Independently verify the tau-only native binary on boundary scalars."""

import argparse
import gzip
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIXTURE = ROOT / "prime-j0-tau-bucket-two-x-20261010/edge-fixture.json"
REFERENCE = ROOT / "prime-j0-power2-residual-20261010/verify_fixture.py"
SPEC = importlib.util.spec_from_file_location("tau_exact_edge_reference", REFERENCE)
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)
MODE = "unit_orbit_u256_tau_dual_rho0_direct_gauge_xyzz_tau_fixed"


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--materialized", type=Path, required=True)
    args = parser.parse_args()
    stdout = (HERE / "native-edge.stdout").read_bytes()
    stderr = (HERE / "native-edge.stderr").read_bytes()
    assert not stderr, stderr[:500]
    checked = reference.check_fixture(MODE, "edge", FIXTURE, stdout, 10)
    compressed = gzip.compress(stdout, compresslevel=9, mtime=0)
    (HERE / "native-edge.stdout.gz").write_bytes(compressed)
    materialization_raw = (args.materialized / "tau-materialization.json").read_bytes()
    result = {"schema": 1, "status": "passed", "timing_class": "correctness_only",
              "cases": checked["cases"], "mode": MODE,
              "point_stream_sha256": checked["point_stream_sha256"],
              "fixture_sha256": digest(FIXTURE.read_bytes()),
              "stdout_sha256": digest(stdout),
              "stdout_gzip_sha256": digest(compressed),
              "binary_sha256": digest(args.binary.read_bytes()),
              "materialization_sha256": digest(materialization_raw),
              "verifier_sha256": digest(Path(__file__).read_bytes()),
              "reference_sha256": digest(REFERENCE.read_bytes())}
    (HERE / "native-edge-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
