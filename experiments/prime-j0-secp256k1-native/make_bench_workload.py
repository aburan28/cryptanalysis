#!/usr/bin/env python3
"""Reduce the frozen 64 one-use fixture to input/output only."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    destination = HERE / "bench-workload.json"
    if destination.exists():
        raise SystemExit("benchmark workload exists; refusing overwrite")
    source_path = HERE / "fixture.json"
    source = json.loads(source_path.read_text())
    assert source["schema"] == 1 and len(source["cases"]) == 64
    cases = []
    for item in source["cases"]:
        cases.append({
            "index": item["index"],
            "base_x_hex": item["base_x_hex"],
            "base_y_hex": item["base_y_hex"],
            "scalar_hex": item["scalar_hex"],
            "expected_identity": False,
            "expected_x_hex": item["expected_x_hex"],
            "expected_y_hex": item["expected_y_hex"],
        })
    assert len({(case["base_x_hex"], case["base_y_hex"])
                for case in cases}) == 64
    result = {
        "schema": 1, "kind": "native-single-use-scalar-format-workload",
        "curve": "secp256k1", "beta_hex": source["beta_hex"],
        "source_fixture_sha256": sha(source_path),
        "script_sha256": sha(Path(__file__)), "cases": cases,
    }
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases),
                      "workload_sha256": sha(destination)}, sort_keys=True))


if __name__ == "__main__":
    main()
