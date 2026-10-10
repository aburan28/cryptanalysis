#!/usr/bin/env python3
"""Compute independent secp256k1 points at scalar reduction boundaries."""

from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
REFERENCE = ROOT / "experiments/prime-j0-tau-power16-20261010/verify_group.py"
sys.path.insert(0, str(REFERENCE.parent))
import verify_group as group


def digest(data):
    return sha256(data).hexdigest()


def main():
    target = HERE / "edge-fixture.json"
    if target.exists():
        raise SystemExit("edge fixture already exists")
    n = group.ORDER
    values = [0, 1, 2, 3, n - 2, n - 1, n, n + 1, 1 << 255, (1 << 256) - 1]
    assert len(set(values)) == len(values) and all(0 <= value < 1 << 256 for value in values)
    cases = []
    for index, scalar in enumerate(values):
        point = group.multiply(scalar % n, group.G)
        cases.append({"index": index, "scalar_hex": f"{scalar:064x}",
                      "base_x_hex": f"{group.G[0]:064x}",
                      "base_y_hex": f"{group.G[1]:064x}",
                      "expected_identity": point is None,
                      "expected_x_hex": None if point is None else f"{point[0]:064x}",
                      "expected_y_hex": None if point is None else f"{point[1]:064x}"})
    record = {"schema": 1, "kind": "frontier17_orbit_xyzz_edge_fixture",
              "curve": "secp256k1", "reference_source_sha256": digest(REFERENCE.read_bytes()),
              "cases": cases}
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"edge_fixture_cases={len(cases)} sha256={digest(target.read_bytes())}")


if __name__ == "__main__":
    main()
