#!/usr/bin/env python3
"""Check native boundary scalar points and classify the initial fixture error."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import edge_cases  # noqa: E402
import replay  # noqa: E402


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def run() -> dict:
    fixture = HERE / "edges.json"
    assert fixture.read_bytes() == edge_cases.make()
    tree = replay.verify(fixture, HERE / "edges-tree.jsonl")
    cases = json.loads(fixture.read_text())["cases"]
    serial_path = HERE / "edges-serial.jsonl"
    serial = [json.loads(line) for line in serial_path.read_text().splitlines()]
    assert len(serial) == len(cases) == 7
    for case, row in zip(cases, serial):
        expected = ("identity" if case["expected_identity"] else
                    f"{case['expected_x_hex']}:{case['expected_y_hex']}")
        assert row["index"] == case["index"]
        assert row["verified"] is True and row["point"] == expected
        assert row["retained_bytes"] == 11_505_936
    failed = HERE / "edges-invalid-fixture.json"
    assert all("base_x_hex" not in case for case in json.loads(failed.read_text())["cases"])
    for name in ("edges-tree.stderr", "edges-serial.stderr"):
        assert "assertion `left == right` failed" in (HERE / name).read_text()
    return {"schema": 1, "status": "edge_points_pass",
            "cases": 7, "verified_tree": tree["verified"], "verified_serial": len(serial),
            "fixture_sha256": digest(fixture),
            "tree_rows_sha256": tree["rows_sha256"],
            "serial_rows_sha256": digest(serial_path),
            "invalid_fixture_sha256": digest(failed),
            "initial_attempt_status": "fixture_schema_error_missing_base_coordinates"}


if __name__ == "__main__":
    result = run()
    output = HERE / "edge-receipt.json"
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if "--write" in sys.argv:
        assert not output.exists()
        output.write_text(data)
    else:
        assert output.read_text() == data
    print(json.dumps(result, sort_keys=True))
