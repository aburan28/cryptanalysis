#!/usr/bin/env python3
"""Replay the integrated native binary against frozen independent point streams."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SOURCE = ROOT / "experiments/prime-j0-secp256k1-native/src/bin"
REFERENCE = ROOT / "experiments/prime-j0-tau-expanded-20261010"
MODES = {
    "expanded": ("--check-scalar-unit-orbit-u256-tau-frontier19-expanded-fixed-fixture",
                 "unit_orbit_u256_tau_frontier19_expanded_fixed"),
    "orbit_x": ("--check-scalar-unit-orbit-u256-tau-frontier19-orbit-x-fixed-fixture",
                "unit_orbit_u256_tau_frontier19_orbit_x_fixed"),
    "frontier19": ("--check-scalar-unit-orbit-u256-tau-frontier19-fixed-fixture",
                   "unit_orbit_u256_tau_frontier19_fixed"),
}


def digest(data):
    return sha256(data).hexdigest()


def parse(line):
    return dict(item.split("=", 1) for item in line.split())


def main():
    binary = Path(sys.argv[1]).resolve(strict=True)
    source_receipt = json.loads((REFERENCE / "source-receipt.json").read_text())
    fresh_result = json.loads((REFERENCE / "fresh-result.json").read_text())
    fixture_raw = (REFERENCE / "fresh-fixture.json").read_bytes()
    fixture = json.loads(fixture_raw)
    assert digest(fixture_raw) == fresh_result["fixture_sha256"]
    cases = fixture["cases"]
    assert len(cases) == 4096
    source_hashes = {}
    for relative, expected in source_receipt["prototype_source_sha256"].items():
        actual = digest((ROOT / relative).read_bytes())
        assert actual == expected, relative
        source_hashes[relative] = actual
    outputs = {}
    for label, (flag, mode) in MODES.items():
        run = subprocess.run([str(binary), flag, str(REFERENCE / "fresh-fixture.json")],
                             capture_output=True, text=True, timeout=600)
        assert run.returncode == 0, (label, run.returncode, run.stderr[-2000:])
        assert not run.stderr, (label, run.stderr[-2000:])
        raw = (run.stdout.rstrip("\n") + "\n").encode()
        expected_raw = gzip.decompress((REFERENCE / f"fresh4096-{label}.out.gz").read_bytes())
        assert raw == expected_raw, label
        lines = raw.decode().splitlines()
        assert len(lines) == 4096
        for index, (line, case) in enumerate(zip(lines, cases)):
            record = parse(line)
            expected = ("identity" if case["expected_identity"] else
                        case["expected_x_hex"] + ":" + case["expected_y_hex"])
            assert record["verified"] == "1" and record["curve"] == "secp256k1"
            assert record["mode"] == mode
            assert record["scalar"] == case["scalar_hex"]
            assert record["point"] == expected, (label, index)
        outputs[label] = {"verified_cases": len(lines), "raw_sha256": digest(raw)}
        assert outputs[label]["raw_sha256"] == fresh_result["outputs"][label]["raw_sha256"]
        print(f"integrated_{label}_verified=4096", flush=True)
    result = {"schema": 1, "base_commit": "49b61f23cf97333ef7016426c31cc7bfd9365cff",
              "timing_class": "correctness_only", "binary_sha256": digest(binary.read_bytes()),
              "fixture_sha256": digest(fixture_raw), "source_sha256": source_hashes,
              "outputs": outputs}
    output = HERE / "integration-result.json"
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output.exists():
        assert output.read_text() == serialized
    else:
        output.write_text(serialized)
    print("integrated_three_way_replay_verified=1")


if __name__ == "__main__":
    main()
