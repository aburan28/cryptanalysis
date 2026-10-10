#!/usr/bin/env python3
"""Replay the frozen independent point panel through fused and baseline formats."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MODES = {
    "frontier17_xyzz": ("--check-scalar-unit-orbit-u256-tau-frontier17-orbit-xyzz-fixed-fixture",
                        "unit_orbit_u256_tau_frontier17_orbit_xyzz_fixed"),
    "xyzz": ("--check-scalar-unit-orbit-u256-tau-frontier19-xyzz-fixed-fixture",
             "unit_orbit_u256_tau_frontier19_xyzz_fixed"),
}


def digest(data):
    return sha256(data).hexdigest()


def parse(line):
    return dict(item.split("=", 1) for item in line.split())


def main():
    binary = Path(sys.argv[1]).resolve(strict=True)
    input_path = HERE / "fresh-inputs.json"
    fixture_path = HERE / "fresh-fixture.json"
    inputs_raw, fixture_raw = input_path.read_bytes(), fixture_path.read_bytes()
    inputs, fixture = json.loads(inputs_raw), json.loads(fixture_raw)
    assert inputs["seed"] == 20261010144
    cases = fixture["cases"]
    assert len(cases) == inputs["count"] == 4096
    assert fixture["input_sha256"] == digest(inputs_raw)
    binary_hash = digest(binary.read_bytes())
    outputs = {}
    point_streams = {}
    for label, (flag, mode) in MODES.items():
        output = HERE / f"fresh4096-{label}.out.gz"
        assert not output.exists()
        run = subprocess.run([str(binary), flag, str(fixture_path)],
                             capture_output=True, text=True, timeout=600)
        assert run.returncode == 0, (label, run.returncode, run.stderr[-2000:])
        assert not run.stderr, (label, run.stderr[-2000:])
        lines = run.stdout.splitlines()
        assert len(lines) == 4096, (label, len(lines))
        points = []
        for index, (line, case) in enumerate(zip(lines, cases)):
            record = parse(line)
            expected = ("identity" if case["expected_identity"] else
                        case["expected_x_hex"] + ":" + case["expected_y_hex"])
            assert record["verified"] == "1" and record["curve"] == "secp256k1"
            assert record["mode"] == mode
            assert record["scalar"] == case["scalar_hex"] == inputs["scalars_hex"][index]
            assert record["point"] == expected, (label, index)
            points.append(record["point"])
        raw = (run.stdout.rstrip("\n") + "\n").encode()
        with output.open("wb") as stream:
            with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
                compressed.write(raw)
        outputs[label] = {"verified_cases": len(lines), "raw_sha256": digest(raw),
                          "compressed_sha256": digest(output.read_bytes())}
        point_streams[label] = points
        print(f"{label}_verified={len(lines)}", flush=True)
    assert point_streams["frontier17_xyzz"] == point_streams["xyzz"]
    assert digest(binary.read_bytes()) == binary_hash
    assert digest(input_path.read_bytes()) == digest(inputs_raw)
    assert digest(fixture_path.read_bytes()) == digest(fixture_raw)
    receipt = json.loads((HERE / "source-receipt.json").read_text())
    result = {"schema": 1, "source_freeze_commit": receipt["source_freeze_commit"],
              "timing_class": "correctness_only", "execution_method": "native_cli_whole_fixture",
              "cases": len(cases), "scalar_sha256": inputs["scalar_sha256"],
              "input_sha256": digest(inputs_raw), "fixture_sha256": digest(fixture_raw),
              "binary_sha256": binary_hash,
              "retained_bytes": receipt["retained_bytes"], "outputs": outputs}
    (HERE / "fresh-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("paired_replay_verified=1")


if __name__ == "__main__":
    main()
