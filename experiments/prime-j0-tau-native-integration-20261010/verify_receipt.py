#!/usr/bin/env python3
"""Check integrated source, release logs, and the frozen three-mode point receipt."""

import gzip
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
REFERENCE = HERE.parent / "prime-j0-tau-expanded-20261010"
MODES = {
    "expanded": "unit_orbit_u256_tau_frontier19_expanded_fixed",
    "orbit_x": "unit_orbit_u256_tau_frontier19_orbit_x_fixed",
    "frontier19": "unit_orbit_u256_tau_frontier19_fixed",
}


def digest(data):
    return sha256(data).hexdigest()


def parse(line):
    return dict(item.split("=", 1) for item in line.split())


def main():
    result = json.loads((HERE / "integration-result.json").read_text())
    reference = json.loads((REFERENCE / "fresh-result.json").read_text())
    source = json.loads((REFERENCE / "source-receipt.json").read_text())
    assert result["base_commit"] == "49b61f23cf97333ef7016426c31cc7bfd9365cff"
    assert result["timing_class"] == "correctness_only"
    assert result["binary_sha256"] == reference["binary_sha256"]
    assert result["source_sha256"] == source["prototype_source_sha256"]
    for relative, expected in result["source_sha256"].items():
        assert digest((ROOT / relative).read_bytes()) == expected
    tests = (HERE / "release-tests.log").read_bytes()
    build = (HERE / "release-build.log").read_bytes()
    assert digest(tests) == "38370bf638505556f1f9301d1008e14480ebc4ef82a18a74c85f390882a42202"
    assert digest(build) == "68d61646ff8fc4927de2a645e3693f44226cfac38618d934e862fd0d4cda4f8d"
    assert b"test result: ok. 106 passed; 0 failed;" in tests
    assert b"Finished `release` profile" in build
    fixture_raw = (REFERENCE / "fresh-fixture.json").read_bytes()
    assert digest(fixture_raw) == result["fixture_sha256"] == reference["fixture_sha256"]
    cases = json.loads(fixture_raw)["cases"]
    assert len(cases) == 4096
    assert set(result["outputs"]) == set(MODES)
    for label, mode in MODES.items():
        raw = gzip.decompress((REFERENCE / f"fresh4096-{label}.out.gz").read_bytes())
        assert digest(raw) == result["outputs"][label]["raw_sha256"]
        assert digest(raw) == reference["outputs"][label]["raw_sha256"]
        lines = raw.decode().splitlines()
        assert len(lines) == result["outputs"][label]["verified_cases"] == 4096
        for line, case in zip(lines, cases):
            row = parse(line)
            expected = ("identity" if case["expected_identity"] else
                        case["expected_x_hex"] + ":" + case["expected_y_hex"])
            assert row["verified"] == "1" and row["curve"] == "secp256k1"
            assert row["mode"] == mode and row["scalar"] == case["scalar_hex"]
            assert row["point"] == expected
    print("native_tau_integration_receipt_verified=1 cases=4096 modes=3 tests=106")


if __name__ == "__main__":
    main()
