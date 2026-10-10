#!/usr/bin/env python3
"""Replay direct bucket merge on the frozen independent scalar fixtures."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "prime-j0-tau-bucket-two-x-20261010"
MODES = {
    "frontier17_direct": (
        "--check-scalar-unit-orbit-u256-tau-frontier17-bucket-two-x-direct-fixed-fixture",
        "unit_orbit_u256_tau_frontier17_bucket_two_x_direct_fixed"),
    "frontier18_direct": (
        "--check-scalar-unit-orbit-u256-tau-frontier18-bucket-two-x-direct-fixed-fixture",
        "unit_orbit_u256_tau_frontier18_bucket_two_x_direct_fixed"),
}


def digest(data):
    return sha256(data).hexdigest()


def parse(line):
    return dict(item.split("=", 1) for item in line.split())


def main():
    binary = Path(sys.argv[1]).resolve(strict=True)
    binary_hash = digest(binary.read_bytes())
    source = json.loads((HERE / "source-receipt.json").read_text())
    panels = {}
    for panel, fixture_name in (("fresh4096", "fresh-fixture.json"),
                                ("edges", "edge-fixture.json")):
        fixture_path = BASE / fixture_name
        fixture_raw = fixture_path.read_bytes()
        cases = json.loads(fixture_raw)["cases"]
        assert len(cases) == (4096 if panel == "fresh4096" else 10)
        outputs = {}
        for label, (flag, mode) in MODES.items():
            target = HERE / f"{panel}-{label}.out.gz"
            assert not target.exists(), target
            run = subprocess.run([str(binary), flag, str(fixture_path)],
                                 capture_output=True, timeout=600)
            assert run.returncode == 0 and not run.stderr, (label, run.stderr[-2000:])
            lines = run.stdout.decode().splitlines()
            assert len(lines) == len(cases), (label, len(lines))
            for index, (line, case) in enumerate(zip(lines, cases)):
                row = parse(line)
                expected = ("identity" if case["expected_identity"] else
                            case["expected_x_hex"] + ":" + case["expected_y_hex"])
                assert row["verified"] == "1" and row["curve"] == "secp256k1"
                assert row["mode"] == mode and row["scalar"] == case["scalar_hex"]
                assert row["point"] == expected, (panel, label, index)
            with target.open("wb") as stream:
                with gzip.GzipFile(filename="", mode="wb", fileobj=stream,
                                   mtime=0) as compressed:
                    compressed.write(run.stdout)
            outputs[label] = {"cases": len(lines), "raw_sha256": digest(run.stdout),
                              "compressed_sha256": digest(target.read_bytes())}
            print(f"{panel}_{label}_verified={len(lines)}", flush=True)
        panels[panel] = {"fixture_sha256": digest(fixture_raw), "outputs": outputs}
    assert digest(binary.read_bytes()) == binary_hash
    result = {"schema": 1, "timing_class": "correctness_only",
              "source_freeze_commit": source["source_freeze_commit"],
              "binary_sha256": binary_hash, "panels": panels}
    (HERE / "replay-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
