#!/usr/bin/env python3
"""Replay the fifteen-window candidate and paired control on fixed scalars."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PANELS = (
    ("fresh4096", HERE / "fresh-fixture.json", 4096),
    ("edges", HERE.parent / "prime-j0-tau-bucket-two-x-20261010/edge-fixture.json", 10),
    ("fixed129", HERE.parent / "prime-j0-secp256k1-native/tau6-comb13-bench-fixture.json", 129),
)
MODES = {
    "frontier15_bound_budget": (
        "--check-scalar-unit-orbit-u256-tau-frontier15-budget-affine-solinas-xyzz-tau-fixed-fixture",
        "unit_orbit_u256_tau_frontier15_budget_affine_solinas_xyzz_tau_fixed"),
    "frontier16_beta_solinas": (
        "--check-scalar-unit-orbit-u256-tau-frontier16-bucket-affine-solinas-xyzz-tau-fixed-fixture",
        "unit_orbit_u256_tau_frontier16_bucket_affine_solinas_xyzz_tau_fixed"),
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
    for panel, fixture_path, expected_count in PANELS:
        fixture_raw = fixture_path.read_bytes()
        cases = json.loads(fixture_raw)["cases"]
        assert len(cases) == expected_count
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
              "binary_sha256": binary_hash,
              "retained_bytes_by_mode": source["retained_bytes_by_mode"],
              "panels": panels}
    (HERE / "replay-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
