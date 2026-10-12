#!/usr/bin/env python3
"""Verify fifteen-window source binding and every native replay point."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from run_replay import HERE, MODES, PANELS, parse
from verify_inputs import main as verify_inputs

ROOT = HERE.parent.parent
SOURCES = (
    "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs",
    "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs",
    "experiments/prime-j0-tau-frontier-20261010/w8-d256/atlas-w8.bin",
    "experiments/prime-j0-tau-power16-20261010/atlas-w9.bin",
    "experiments/prime-j0-tau-power16-20261010/screen.py",
    "experiments/prime-j0-tau-power16-20261010/verify_group.py",
    "experiments/prime-j0-frontier16-compact-affine-20261010/fresh-inputs.json",
    "experiments/prime-j0-frontier16-beta-solinas-20261010/fresh-inputs.json",
    "experiments/prime-j0-bound-budget15-20261010/atlas-w9.bin",
    "experiments/prime-j0-bound-budget15-20261010/atlas-receipt.json",
    "experiments/prime-j0-bound-budget15-20261010/build_atlas.py",
    "experiments/prime-j0-bound-budget15-20261010/PROOF.md",
    "experiments/prime-j0-bound-budget15-20261010/make_inputs.py",
    "experiments/prime-j0-bound-budget15-20261010/verify_inputs.py",
    "experiments/prime-j0-bound-budget15-20261010/make_fresh_fixture.py",
    "experiments/prime-j0-bound-budget15-20261010/run_replay.py",
    "experiments/prime-j0-bound-budget15-20261010/verify.py",
)


def digest(data):
    return sha256(data).hexdigest()


def committed(commit, relative):
    return subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=ROOT,
                          check=True, capture_output=True).stdout


def main():
    source = json.loads((HERE / "source-receipt.json").read_text())
    result = json.loads((HERE / "replay-result.json").read_text())
    freeze = source["source_freeze_commit"]
    assert result["source_freeze_commit"] == freeze
    assert set(source["source_sha256"]) == set(SOURCES)
    for relative, expected in source["source_sha256"].items():
        assert digest(committed(freeze, relative)) == expected, relative
        assert digest((ROOT / relative).read_bytes()) == expected, relative
    verify_inputs()
    assert result["schema"] == 1 and result["timing_class"] == "correctness_only"
    assert source["retained_bytes_by_mode"] == {
        "frontier15_bound_budget": 17_511_596,
        "frontier16_beta_solinas": 8_336_624}
    assert result["retained_bytes_by_mode"] == source["retained_bytes_by_mode"]
    fresh_raw = (HERE / "fresh-fixture.json").read_bytes()
    fresh = json.loads(fresh_raw)
    assert fresh["input_sha256"] == digest((HERE / "fresh-inputs.json").read_bytes())
    reference = ROOT / "experiments/prime-j0-tau-power16-20261010/verify_group.py"
    assert fresh["reference_source_sha256"] == digest(reference.read_bytes())
    for panel, fixture_path, expected_count in PANELS:
        fixture_raw = fixture_path.read_bytes()
        assert digest(fixture_raw) == result["panels"][panel]["fixture_sha256"]
        cases = json.loads(fixture_raw)["cases"]
        assert len(cases) == expected_count
        for label, (_, mode) in MODES.items():
            output = HERE / f"{panel}-{label}.out.gz"
            compressed = output.read_bytes()
            raw = gzip.decompress(compressed)
            record = result["panels"][panel]["outputs"][label]
            assert digest(compressed) == record["compressed_sha256"]
            assert digest(raw) == record["raw_sha256"]
            lines = raw.decode().splitlines()
            assert len(lines) == record["cases"] == len(cases)
            for index, (line, case) in enumerate(zip(lines, cases)):
                row = parse(line)
                expected = ("identity" if case["expected_identity"] else
                            case["expected_x_hex"] + ":" + case["expected_y_hex"])
                assert row["verified"] == "1" and row["curve"] == "secp256k1"
                assert row["mode"] == mode and row["scalar"] == case["scalar_hex"]
                assert row["point"] == expected, (panel, label, index)
    print("frontier15_bound_budget_verified=1 cases=4096 edges=10 fixed=129 modes=2 source_frozen=1")


if __name__ == "__main__":
    main()
