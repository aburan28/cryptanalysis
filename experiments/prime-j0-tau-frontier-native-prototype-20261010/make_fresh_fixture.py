#!/usr/bin/env python3
"""Build independent secp256k1 point expectations for the frozen fresh panel."""

from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
REFERENCE = ROOT / "experiments/prime-j0-tau-power16-20261010/verify_group.py"
sys.path.insert(0, str(REFERENCE.parent))
import verify_group as group


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "fresh-fixture.json"
    if output.exists():
        raise SystemExit("fresh fixture already exists")
    input_path = HERE / "fresh-inputs.json"
    inputs = json.loads(input_path.read_text())
    scalars = [int(text, 16) for text in inputs["scalars_hex"]]
    assert len(scalars) == inputs["count"] == 4096
    cases = []
    for index, scalar in enumerate(scalars):
        point = group.multiply(scalar % group.ORDER, group.G)
        cases.append({"index": index, "scalar_hex": f"{scalar:064x}",
                      "base_x_hex": f"{group.G[0]:064x}",
                      "base_y_hex": f"{group.G[1]:064x}",
                      "expected_identity": point is None,
                      "expected_x_hex": None if point is None else f"{point[0]:064x}",
                      "expected_y_hex": None if point is None else f"{point[1]:064x}"})
    record = {"schema": 1, "kind": "frontier17_independent_binary_fixture",
              "curve": "secp256k1", "input_sha256": digest(input_path),
              "reference_source_sha256": digest(REFERENCE), "cases": cases}
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"fresh_fixture_cases={len(cases)} sha256={digest(output)}")


if __name__ == "__main__":
    main()
