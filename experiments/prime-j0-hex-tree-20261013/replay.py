#!/usr/bin/env python3
"""Check every native tree row against independently generated point fixtures."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path


def verify(fixture_path: Path, rows_path: Path) -> dict:
    fixture_bytes = fixture_path.read_bytes()
    rows_bytes = rows_path.read_bytes()
    cases = json.loads(fixture_bytes)["cases"]
    lines = rows_bytes.splitlines()
    assert len(cases) == len(lines)
    assert len({case["scalar_hex"] for case in cases}) == len(cases)
    additions = rotations = 0
    retained = set()
    for index, (case, line) in enumerate(zip(cases, lines)):
        row = json.loads(line)
        expected = ("identity" if case["expected_identity"] else
                    f"{case['expected_x_hex']}:{case['expected_y_hex']}")
        assert row["index"] == case["index"] == index
        assert row["verified"] is True
        assert row["point"] == expected, index
        assert isinstance(row["additions"], int) and 0 <= row["additions"] <= 15
        assert isinstance(row["rotations"], int) and 0 <= row["rotations"] <= 16
        additions += row["additions"]
        rotations += row["rotations"]
        retained.add(row["retained_bytes"])
    assert retained == {11_552_448}
    return {"cases": len(cases), "verified": len(cases),
            "additions": additions, "rotations": rotations,
            "retained_bytes": next(iter(retained)),
            "fixture_sha256": sha256(fixture_bytes).hexdigest(),
            "rows_sha256": sha256(rows_bytes).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("rows", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.fixture, args.rows), sort_keys=True))


if __name__ == "__main__":
    main()
